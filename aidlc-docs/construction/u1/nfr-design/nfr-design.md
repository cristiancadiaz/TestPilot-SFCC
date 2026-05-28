# NFR Design — U1 Executor Playwright (actualizado 2026-05-24)

Patrones concretos para satisfacer los NFR-* de U1.

---

## Patrón 1: Step Executor unificado con captura de screenshots según flags

Resuelve NFR-P3 (medición por paso) + NFR-S3 (error sin traceback) + BR-U1-04 (disciplina de screenshots).

```python
async def _execute_step(
    page: Page,
    name: str,
    action: Callable[[], Awaitable[None]],
    config: SyntheticUserConfig,
    run_id: str,
    profile_id: str,
    flow_name: str,
    is_final: bool = False,
) -> StepResult:
    start = time.monotonic()
    try:
        await action()
        duration_ms = int((time.monotonic() - start) * 1000)
        screenshot_url, screenshot_state = None, None
        if config.screenshot_on_success or is_final:
            screenshot_url = await _capture_and_upload(
                page, run_id, profile_id, flow_name, name, state="ok"
            )
            screenshot_state = "ok"
        return StepResult(
            name=name, status="success",
            duration_ms=duration_ms,
            screenshot_url=screenshot_url,
            screenshot_state=screenshot_state,
        )
    except InfrastructureError:
        raise  # propagar al runner
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        screenshot_url, screenshot_state = None, None
        if config.screenshot_on_error:  # siempre True (BR-U0-04)
            screenshot_url = await _capture_and_upload(
                page, run_id, profile_id, flow_name, name, state="fail"
            )
            screenshot_state = "fail"
        return StepResult(
            name=name, status="failed",
            duration_ms=duration_ms,
            error=str(exc),
            screenshot_url=screenshot_url,
            screenshot_state=screenshot_state,
        )
```

**Por qué este patrón:**
- Lógica de screenshot y medición en un solo lugar (DRY).
- Los flows quedan como listas de lambdas `async lambda: page.click(SEL)` sin boilerplate.
- `InfrastructureError` se re-lanza para que el runner la distinga.
- `_capture_and_upload` encapsula la decisión PNG vs WebP, S3 vs disco local.

---

## Patrón 2: BrowserContext con perfil + http_credentials (CAMBIO MAYOR)

Resuelve la autenticación a nivel ambiente sin tocar código de flows.

```python
async def _create_context(
    browser: Browser,
    profile: BrowserProfile,
    env_access: EnvironmentAccessCredentials,
    nav_timeout_ms: int,
    step_timeout_ms: int,
) -> BrowserContext:
    ctx = await browser.new_context(
        locale=profile.locale,
        user_agent=profile.user_agent,
        viewport={
            "width": profile.viewport_width,
            "height": profile.viewport_height,
        },
        is_mobile=profile.is_mobile,
        has_touch=profile.is_mobile,
        device_scale_factor=2 if profile.is_mobile else 1,
        http_credentials={
            "username": env_access.username,
            "password": env_access.password,
        },
    )
    ctx.set_default_timeout(step_timeout_ms)
    ctx.set_default_navigation_timeout(nav_timeout_ms)
    return ctx
```

**Por qué:**
- `http_credentials` aplica HTTP Basic Auth a TODOS los requests del context — no hay que recordar agregar header en cada `page.goto`.
- Sin acoplamiento entre flow y mecanismo de auth de ambiente.
- Cleanup automático al cerrar context.

---

## Patrón 3: Network allowlist (NFR-S5)

```python
ALLOWED_DOMAINS = {
    "ssl.fastly.net",          # CDN común SFCC
    "*.cquotient.com",         # Personalization SFCC
    "*.demandware.net",        # SFCC core
    # store domain se agrega dinámicamente
}

async def _setup_allowlist(context: BrowserContext, store_url: str) -> None:
    store_domain = urlparse(store_url).hostname
    allowed = ALLOWED_DOMAINS | {store_domain}
    
    async def route_handler(route, request):
        host = urlparse(request.url).hostname
        if any(_matches(host, pattern) for pattern in allowed):
            await route.continue_()
        else:
            logger.debug("blocked external request to %s", host)
            await route.abort()
    
    await context.route("**/*", route_handler)
```

**Trade-off MVP:** allowlist permisivo (3 dominios + store). Se refina en sprint 3+ basado en logs de bloqueos.

---

## Patrón 4: Finally garantizado para cierre de browser (NFR-R2)

```python
async def run_profile(
    profile: BrowserProfile,
    flow_name: FlowName,
    config: SyntheticUserConfig,
    env: ResolvedEnvironment,
    run_id: str,
) -> ProfileResult:
    # Pre-condiciones (NFR-R3, BR-U1-03, BR-U0-04)
    assert env.shopper.email.endswith("@testpilot.internal")
    assert config.screenshot_on_error is True
    
    playwright = await async_playwright().start()
    browser: Browser | None = None
    try:
        browser = await playwright.chromium.launch(headless=HEADLESS)
        context = await _create_context(browser, profile, env.env_access, ...)
        await _setup_allowlist(context, str(env.config.store_url))
        page = await context.new_page()
        
        # Step 1: env_access (handled by http_credentials in context)
        # Solo verificamos que goto al storefront da 200
        env_step = await _execute_step(
            page, "env_access_auth",
            lambda: page.goto(str(env.config.store_url), wait_until="domcontentloaded"),
            config, run_id, profile.name, flow_name,
        )
        if env_step.status == "failed":
            raise InfrastructureError(f"env_access rejected: {env_step.error}")
        
        # Step 2: shopper_login (form interactivo)
        login_step = await shopper_login(page, env.shopper, config, run_id, profile.name, flow_name)
        
        # Steps 3-10: flow funcional
        flow_module = {
            "checkout-full": checkout_full,
            "checkout-card-declined": checkout_card_declined,
        }[flow_name]
        flow_result = await flow_module.run(page, config, env, run_id, profile.name)
        
        # Prepender los pasos de auth al flow_result
        flow_result.steps = [env_step, login_step] + flow_result.steps
        
        # NFR-R3: invariante
        assert flow_result.orders_created == 0
        
        traffic_light = _initial_traffic_light(flow_result)
        return ProfileResult(profile=profile, flow_result=flow_result, traffic_light=traffic_light)
        
    except InfrastructureError as e:
        # Convertir a FlowResult error sin re-raise
        return ProfileResult(
            profile=profile,
            flow_result=FlowResult(
                flow_name=flow_name, status="error",
                steps=[], duration_ms=0, orders_created=0,
            ),
            traffic_light=TrafficLight.YELLOW,
        )
    finally:
        if browser is not None:
            await browser.close()
        await playwright.stop()
```

**Por qué:**
- `try/finally` garantiza `browser.close()` en cualquier escenario (éxito, error de app, InfraError) — sin leaks de procesos zombi en ECS.
- `InfrastructureError` se captura en `run_profile` y se convierte en `ProfileResult` válido con `traffic_light=YELLOW` — el caller no tiene que manejar excepciones.

---

## Patrón 5: Detección de infrastructure_error en env_access (NFR-R1)

```python
from playwright._impl._errors import TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

async def _step_env_access(page: Page, store_url: str) -> None:
    try:
        response = await page.goto(store_url, wait_until="domcontentloaded")
        if response is None:
            raise InfrastructureError(f"No response from {store_url}")
        if response.status == 401:
            raise InfrastructureError(f"env_access auth rejected (401) on {store_url}")
        if response.status >= 500:
            raise InfrastructureError(f"Storefront 5xx: {response.status} on {store_url}")
    except PlaywrightTimeoutError as exc:
        raise InfrastructureError(f"Storefront unreachable (timeout): {exc}") from exc
    except PlaywrightError as exc:
        # DNS, TLS, connection refused
        raise InfrastructureError(f"Storefront unreachable: {exc}") from exc
```

Solo este paso distingue `InfrastructureError`. Los pasos posteriores (search, PDP, checkout) que fallan son errores de app (selector roto, etc.) → `StepResult(status="failed")`.

---

## Patrón 6: shopper_login encapsulado

```python
# src/executor/auth/shopper_login.py
async def shopper_login(
    page: Page,
    credentials: ShopperCredentials,
    config: SyntheticUserConfig,
    run_id: str,
    profile_id: str,
    flow_name: str,
) -> StepResult:
    async def _do_login():
        await page.goto(LOGIN_URL_PATH, wait_until="domcontentloaded")
        await page.fill(LOGIN_EMAIL_INPUT, credentials.email)
        await page.fill(LOGIN_PASSWORD_INPUT, credentials.password)
        await page.click(LOGIN_SUBMIT_BUTTON)
        await page.wait_for_selector(LOGIN_MY_ACCOUNT_INDICATOR, state="visible")
    
    return await _execute_step(
        page, "shopper_login", _do_login,
        config, run_id, profile_id, flow_name,
    )
```

**Por qué función separada:**
- Testeable con un solo `pytest`: mock de `page.fill`, `page.click`, `page.wait_for_selector`.
- Reutilizable entre ambos flows sin duplicación.

---

## Patrón 7: Upload async de screenshots (NFR-P5 — no bloquear flow)

```python
import boto3
from botocore.config import Config

_s3 = boto3.client("s3", config=Config(max_pool_connections=20))
_executor = ThreadPoolExecutor(max_workers=4)

async def _capture_and_upload(
    page: Page,
    run_id: str,
    profile_id: str,
    flow_name: str,
    step_name: str,
    state: Literal["ok", "fail"],
) -> str:
    key = f"{run_id}/{profile_id}/{flow_name}/{step_name}-{state}.png"
    image_bytes = await page.screenshot(type="png", full_page=False)
    
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        _executor,
        lambda: _s3.put_object(
            Bucket=S3_BUCKET_SCREENSHOTS,
            Key=key,
            Body=image_bytes,
            ContentType="image/png",
            ServerSideEncryption="AES256",
        ),
    )
    return key
```

**Por qué:**
- `page.screenshot()` es async pero CPU-bound — devuelve bytes rápido.
- `boto3.put_object` es síncrono — ejecutarlo en thread pool no bloquea el event loop.
- ThreadPoolExecutor con 4 workers: suficiente para 3 perfiles × 1 screenshot ocasional cada uno.

---

## Patrón 8: Logging estructurado sin secretos

```python
logger = logging.getLogger(__name__)

# OK
logger.info("step completed", extra={
    "step_name": step_name,
    "profile_id": profile_id,
    "duration_ms": duration_ms,
    "status": status,
})

# Si necesitamos loggear el env, redactado:
logger.debug("env resolved", extra={
    "environment_id": env.config.environment_id,
    "store_url": str(env.config.store_url),
    "shopper_email": _redact_email(env.shopper.email),  # ej. q***@testpilot.internal
    # NUNCA: env.shopper.password, env.env_access.password
})

def _redact_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[0]}***@{domain}" if local else "***"
```

`RedactingJsonFormatter` (D-U0-06) además garantiza que cualquier campo con key `password|secret|token|api_key` sea reemplazado por `***REDACTED***` antes de salir.

---

## Resumen patrones → NFRs

| Patrón | NFRs satisfechos |
|---|---|
| 1. `_execute_step` | NFR-P3, NFR-S3, BR-U1-04 |
| 2. `_create_context` con http_credentials | BR-U1-09, D-U1-04 |
| 3. Allowlist de red | NFR-S5 |
| 4. `try/finally` en run_profile | NFR-R1, NFR-R2, NFR-R3 |
| 5. Detección InfraError en env_access | NFR-R1, BR-U1-08 |
| 6. `shopper_login` encapsulado | D-U1-05, D-U1-06 |
| 7. Upload async S3 | NFR-P5 |
| 8. Logging estructurado | NFR-S4 |
