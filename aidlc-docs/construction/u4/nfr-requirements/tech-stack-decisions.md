# Tech Stack Decisions — U4 API Endpoints (actualizado 2026-05-24)

## Decisión D-U4-01: FastAPI vs alternativas

**Elegido:** FastAPI 0.115.0

**Razones:**
- Async-first → integración natural con Playwright async (U1).
- OpenAPI auto-generado → contrato del API documentado sin esfuerzo extra.
- Pydantic integration nativa → validación de request/response sin boilerplate.
- Performance comparable a Node/Go en benchmarks (TechEmpower).
- Adopción amplia en el equipo PASH.

**Descartado:**
- **Flask:** síncrono por default; agregar async requiere extensions.
- **Django REST:** muy pesado para un API stateless.
- **Starlette puro:** sin Pydantic integration, más boilerplate.

---

## Decisión D-U4-02: boto3 sync vs aioboto3

**Elegido:** `boto3` (síncrono).

**Razones:**
- Mucho más maduro que aioboto3.
- Las operaciones AWS son rápidas (<100 ms cada una) — el costo de ejecutarlas en thread pool es negligible.
- `loop.run_in_executor()` permite usarlo sin bloquear el event loop.

**Implementación:**
```python
_executor = ThreadPoolExecutor(max_workers=8)
async def _run_sync(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, lambda: fn(*args, **kwargs))
```

**Cuándo reconsiderar:** si profiling muestra contention en el ThreadPool con >50 ops AWS/s sostenido.

---

## Decisión D-U4-03: Caché in-memory para Environment Registry

**Elegido:** `cachetools.TTLCache` con `maxsize=10` (3 ambientes + buffer) y `ttl=60` segundos.

**Razones:**
- 3 ambientes en MVP → tamaño negligible.
- 60 s permite que un cambio de configuración se propague rápido sin sobrecargar DynamoDB.
- TTLCache es thread-safe.

**Descartado:**
- **Redis:** overkill para 3 entradas.
- **functools.lru_cache:** sin TTL — un update no se reflejaría.

---

## Decisión D-U4-04: Caché de credenciales resueltas

**Elegido:** TTL 5 minutos para `ResolvedEnvironment`.

**Razones:**
- Reduce calls a Secrets Manager (que tiene rate limits estrictos).
- 5 min es suficientemente corto para soportar rotación manual de secrets.
- Caché por `environment_id` — invalidación granular.

**Trade-off aceptado:** si se rotan secrets, hay ventana de hasta 5 min con credenciales viejas. Aceptable en uso interno.

---

## Decisión D-U4-05: Servir screenshots vía proxy vs presigned URL

**Elegido MVP:** proxy directo desde FastAPI.

**Razones:**
- Simplicidad: un solo flujo de auth (X-API-Key).
- El cliente NO necesita conocer S3 ni manejar URLs presigned.
- Permite log de quién accede a qué screenshot.

**Trade-off:** carga el FastAPI con bandwidth de imágenes. Con disciplina de screenshots y dashboard lazy-load, esperado < 1 GB/día. Aceptable.

**Cuándo migrar a presigned:** si bandwidth supera 5 GB/día o si latencia degrada.

---

## Decisión D-U4-06: Live status tracker — in-memory ring buffer

**Elegido:** `OrderedDict` con max 100 entries, evict de los más viejos.

**Razones:**
- Simplicidad.
- Un task ECS no comparte estado con otros — pero en MVP solo hay 1 task.
- 100 runs × ~5 KB c/u = ~500 KB en memoria. Negligible.

**Trade-off:** si la task muere, se pierde estado vivo. Los runs ya completados están en baseline_store y son recuperables vía `GET /v1/runs/{id}`. El cliente que estaba en P3 viendo el run perdido recibe 404 y debe consultar el detalle.

**Post-MVP:** mover a DynamoDB con TTL.

---

## Decisión D-U4-07: Watchdog con `asyncio.wait_for` (no signals)

**Elegido:** `asyncio.wait_for(orchestrator.run(...), timeout=1800)`

**Razones:**
- Cooperativo, sin OS signals.
- Cancela las tasks correctamente (browsers Playwright responden a cancellation y cierran limpio).
- Sin race conditions vs SIGTERM.

**Cuidados:** asegurar que `run_profile` propaga `CancelledError` correctamente (Playwright lo soporta).

---

## Decisión D-U4-08: OpenAPI docs solo en dev

**Elegido:** `app = FastAPI(docs_url=None if not DOCS_ENABLED else "/docs", redoc_url=None)`

**Razones:**
- En prod, `/docs` expone superficie de ataque (info disclosure de endpoints).
- En dev, util para exploración manual.
- Toggle via env var `DOCS_ENABLED=true|false` (default false).

---

## Stack final U4

| Componente | Versión |
|---|---|
| FastAPI | 0.115.0 |
| Uvicorn | 0.30.6 |
| Pydantic | 2.9.2 |
| boto3 | 1.35.49 |
| cachetools | 5.5.0 (a agregar a pyproject.toml en U0) |
| python-json-logger | 2.0.7 |
| httpx (testing) | 0.27.2 |

**Cambio en pyproject.toml:** agregar `cachetools==5.5.0` (no estaba en versión anterior).
