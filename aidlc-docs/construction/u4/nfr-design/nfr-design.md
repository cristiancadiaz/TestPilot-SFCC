# NFR Design — U4 API Endpoints (actualizado 2026-05-24)

Patrones concretos para satisfacer los NFR-U4-* y BR-U4-*.

---

## Patrón 1: Auth dependency reutilizable

```python
# src/api/auth.py
import os, hmac
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    expected = os.environ.get("TESTPILOT_API_KEY", "")
    if not expected:
        raise HTTPException(503, detail={"error_code": "auth_misconfigured", "message": "Server auth not configured"})
    if not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(401, detail={"error_code": "unauthorized", "message": "Invalid API key"})
```

**Uso:**
```python
@router.get("/environments", dependencies=[Depends(verify_api_key)])
async def list_environments(): ...
```

**Por qué:**
- `hmac.compare_digest` previene timing attacks (NFR-U4-S5).
- `Depends(verify_api_key)` reutilizable en cada router.
- Sin lógica en cada endpoint.

---

## Patrón 2: Exception handler global estructurado

```python
# src/api/exceptions.py
from fastapi import Request
from fastapi.responses import JSONResponse

class TestPilotApiError(Exception):
    status_code: int = 500
    error_code: str = "internal_error"
    
    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details
        super().__init__(message)

async def testpilot_exception_handler(request: Request, exc: TestPilotApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.error_code, "message": exc.message, "details": exc.details},
    )

async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled exception in %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error_code": "internal_error", "message": "Internal server error"},
    )

# Registrar
app.add_exception_handler(TestPilotApiError, testpilot_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
```

**Por qué:**
- Garantiza que NUNCA se exponga un stack trace al cliente (NFR-U4-S9, BR-U4-19).
- Errores estructurados consistentes (BR-U4-20).
- Logger captura el stack trace para debugging interno.

---

## Patrón 3: Caché TTL para Environment Registry

```python
from cachetools import TTLCache
from threading import Lock

class EnvironmentRegistry:
    def __init__(self, table_name: str):
        self._table = boto3.resource("dynamodb").Table(table_name)
        self._cache: TTLCache[str, EnvironmentConfig] = TTLCache(maxsize=10, ttl=60)
        self._list_cache: TTLCache[bool, list] = TTLCache(maxsize=2, ttl=60)
        self._lock = Lock()
    
    def get(self, environment_id: str) -> EnvironmentConfig | None:
        with self._lock:
            if environment_id in self._cache:
                return self._cache[environment_id]
        item = self._table.get_item(Key={"environment_id": environment_id}).get("Item")
        if item is None:
            return None
        config = EnvironmentConfig.model_validate(item)
        with self._lock:
            self._cache[environment_id] = config
        return config
    
    def invalidate(self, environment_id: str) -> None:
        with self._lock:
            self._cache.pop(environment_id, None)
            self._list_cache.clear()  # cualquier list response es ahora stale
```

**Después de cualquier `create/update/deactivate`, llamar `invalidate()`.**

---

## Patrón 4: Resolver de credenciales con caché y propagación de errores

```python
class EnvironmentResolver:
    def __init__(self, registry: EnvironmentRegistry, secrets: SecretsManagerClient):
        self._registry = registry
        self._secrets = secrets
        self._cache: TTLCache[str, ResolvedEnvironment] = TTLCache(maxsize=10, ttl=300)
        self._lock = Lock()
    
    def resolve(self, environment_id: str) -> ResolvedEnvironment:
        with self._lock:
            if environment_id in self._cache:
                return self._cache[environment_id]
        
        config = self._registry.get(environment_id)
        if config is None:
            raise EnvironmentNotFoundError(f"Environment '{environment_id}' not found")
        if not config.active:
            raise EnvironmentInactiveError(f"Environment '{environment_id}' is inactive")
        
        try:
            env_access_dict = self._secrets.get_json(config.env_access_secret_path)
            shopper_dict = self._secrets.get_json(config.shopper_secret_path)
        except (ClientError, KeyError) as exc:
            raise SecretNotFoundError(
                f"Failed to resolve secrets for environment '{environment_id}'",
                details={"environment_id": environment_id},  # NO incluir paths
            ) from exc
        
        try:
            env = ResolvedEnvironment(
                config=config,
                env_access=EnvironmentAccessCredentials(**env_access_dict),
                shopper=ShopperCredentials(**shopper_dict),
            )
        except ValidationError as exc:
            raise InvalidSecretPathError(
                f"Secret content invalid for environment '{environment_id}'",
                details={"environment_id": environment_id, "validation_errors": exc.errors()},
            ) from exc
        
        with self._lock:
            self._cache[environment_id] = env
        return env
```

**Por qué:**
- Cada error tiene un código específico (NFR-U4-S14).
- Detalles SIN paths de Secrets (defensa en profundidad).
- Caché 5 min reduce carga a Secrets Manager.
- `from exc` preserva chain para logging interno.

---

## Patrón 5: Run orchestrator con semaphore y watchdog

```python
class RunOrchestrator:
    def __init__(self, resolver, baseline_store, live_tracker, max_concurrent: int = 3):
        self._resolver = resolver
        self._baseline_store = baseline_store
        self._live_tracker = live_tracker
        self._sem = asyncio.Semaphore(max_concurrent)
    
    async def run(self, config: SyntheticUserConfig) -> ExecutionReport:
        env = self._resolver.resolve(config.environment_id)
        run_id = str(uuid4())
        started_at = datetime.now(timezone.utc)
        self._live_tracker.start(run_id, env.config.environment_id, started_at, config.profiles)
        
        try:
            return await asyncio.wait_for(
                self._execute(config, env, run_id, started_at),
                timeout=RUN_TIMEOUT_SECONDS,  # 1800
            )
        except asyncio.TimeoutError:
            self._live_tracker.fail(run_id, "watchdog timeout")
            raise RunTimeoutError("Run exceeded 30 minute watchdog timeout")
    
    async def _execute(self, config, env, run_id, started_at):
        profile_instances = [_resolve_profile(p) for p in config.profiles]
        
        async def _bounded(profile, flow_name):
            async with self._sem:
                self._live_tracker.update_profile(run_id, profile.name, state="running")
                result = await run_profile(profile, flow_name, config, env, run_id)
                self._live_tracker.update_profile(
                    run_id, profile.name,
                    state=result.flow_result.status,
                    steps_completed=len(result.flow_result.steps),
                )
                return result
        
        tasks = [_bounded(p, f) for p in profile_instances for f in config.flows]
        profile_results = await asyncio.gather(*tasks)
        
        report = generate_report(
            profile_results=profile_results,
            baseline_store=self._baseline_store,
            config=config,
            run_id=run_id,
            env=env,
            started_at=started_at,
        )
        
        self._save_report(report)
        self._live_tracker.complete(run_id, report.traffic_light)
        return report
```

**Por qué:**
- `asyncio.wait_for` garantiza watchdog (NFR-U4-R3).
- `Semaphore` cap respeta `MAX_CONCURRENT_PROFILES` (NFR-U4-P3).
- `live_tracker` actualizado en cada transición → dashboard P3 ve estado en vivo.

---

## Patrón 6: LiveStatusTracker thread-safe

```python
from collections import OrderedDict
from threading import Lock

class LiveStatusTracker:
    def __init__(self, max_runs: int = 100):
        self._runs: OrderedDict[str, RunStatus] = OrderedDict()
        self._max = max_runs
        self._lock = Lock()
    
    def start(self, run_id, env_id, started_at, profile_ids):
        with self._lock:
            if len(self._runs) >= self._max:
                self._runs.popitem(last=False)  # evict oldest
            self._runs[run_id] = RunStatus(
                run_id=run_id,
                state=RunState.RUNNING,
                started_at=started_at,
                environment_id=env_id,
                profiles=[
                    ProfileLiveStatus(
                        profile_id=pid, state="pending",
                        current_step=None, steps_completed=0, steps_total=10, duration_ms=0,
                    )
                    for pid in profile_ids
                ],
            )
    
    def update_profile(self, run_id, profile_id, **kwargs):
        with self._lock:
            if run_id not in self._runs:
                return  # run ya evicted
            status = self._runs[run_id]
            for p in status.profiles:
                if p.profile_id == profile_id:
                    for k, v in kwargs.items():
                        if v is not None:
                            setattr(p, k, v)
                    break
    
    def get(self, run_id) -> RunStatus | None:
        with self._lock:
            return self._runs.get(run_id)
```

**Por qué:**
- `Lock` evita race conditions cuando múltiples tasks asyncio actualizan paralelo.
- `OrderedDict` con `popitem(last=False)` = FIFO eviction.

---

## Patrón 7: Security headers middleware

```python
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path == "/" or path.endswith(".html"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "img-src 'self' data: https://*.s3.amazonaws.com; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "connect-src 'self';"
            )
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
```

Cubre NFR-MD0-S6 + BR-U4-23.

---

## Patrón 8: Logging request/response middleware

```python
import time, hashlib

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.monotonic()
        api_key = request.headers.get("X-API-Key", "")
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:12] if api_key else "anon"
        
        try:
            response = await call_next(request)
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "request handled",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                    "api_key_hash": api_key_hash,
                },
            )
            return response
        except Exception:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "api_key_hash": api_key_hash,
                },
            )
            raise
```

**Por qué:**
- Log estructurado por request (NFR-U4-O1).
- `api_key_hash` permite atribución sin loggear la key (SECURITY-10).

---

## Patrón 9: Healthcheck con checks paralelos

```python
@router.get("/health", response_model=HealthResponse)
async def health():
    checks = await asyncio.gather(
        _check_dynamodb(),
        _check_secrets_manager(),
        return_exceptions=True,
    )
    results = {
        "dynamodb_environments": "ok" if checks[0] is None else "fail",
        "secrets_manager": "ok" if checks[1] is None else "fail",
        "live_tracker": "ok",  # in-memory, siempre OK si el proceso vive
    }
    all_ok = all(v == "ok" for v in results.values())
    response = HealthResponse(
        status="healthy" if all_ok else "unhealthy",
        checks=results,
        version=VERSION,
        git_sha=os.environ.get("GIT_SHA"),
    )
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content=response.model_dump(),
    )

async def _check_dynamodb():
    try:
        await _run_sync(lambda: dynamodb.describe_table(TableName=TABLE_ENVIRONMENTS))
    except Exception as exc:
        raise

async def _check_secrets_manager():
    try:
        await _run_sync(lambda: secrets.list_secrets(MaxResults=1))
    except Exception as exc:
        raise
```

Cubre NFR-U4-P4 + BR-U4-25.

---

## Resumen patrones → NFRs/BRs

| Patrón | Cubre |
|---|---|
| 1. Auth dependency | BR-U4-01, BR-U4-02, NFR-U4-S5 |
| 2. Exception handlers | NFR-U4-S9, BR-U4-19, BR-U4-20 |
| 3. Env Registry cache | NFR-U4-P1 |
| 4. Env Resolver | BR-U4-07, BR-U4-08, NFR-U4-R1, NFR-U4-S14 |
| 5. Run Orchestrator | BR-U4-09, BR-U4-10, NFR-U4-P3, NFR-U4-R3 |
| 6. Live Tracker | BR-U4-17, NFR-U4-P5 |
| 7. Security headers | BR-U4-23, NFR-MD0-S6 |
| 8. Request logging | NFR-U4-O1, NFR-U4-S10 |
| 9. Healthcheck | BR-U4-25, NFR-U4-P4 |
