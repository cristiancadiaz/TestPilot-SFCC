# Tech Stack Decisions — U1 Executor Playwright (actualizado 2026-05-24)

## Decisión D-U1-01: Playwright Python async

**Elegido:** `playwright==1.48.0` API async (`async_playwright`)

**Razones:**
- async es requerido para integración nativa con FastAPI (que es ASGI/async).
- Permite `asyncio.gather` para paralelizar 3 perfiles en el mismo proceso.
- `http_credentials` en `browser.new_context()` resuelve env_access (HTTP Basic) sin código adicional.

**Descartado:**
- API sync: incompatible con el modelo de concurrencia de FastAPI.

---

## Decisión D-U1-02: Solo Chromium en MVP

**Elegido:** Chromium únicamente.

**Razones:**
- SFCC/SFRA tiene mejor compatibilidad documentada con Chromium.
- Reduce overhead de browsers en imagen Docker (~500 MB ahorrados vs incluir Firefox y WebKit).
- 3 perfiles en Chromium con diferentes UAs cubre el caso de uso real (los clientes finales mayoritariamente usan Chrome).

**Cuándo agregar Firefox/Safari:** post-MVP, si una regresión específica solo aparece en esos engines.

---

## Decisión D-U1-03: Headless en producción, headful para debug local

**Elegido:** `headless=True` por default. Override vía env var `PLAYWRIGHT_HEADFUL=1` para debug local.

**Razones:**
- ECS Fargate no tiene display — headless obligatorio.
- Debugging local con headful permite ver lo que Playwright "ve".

---

## Decisión D-U1-04: HTTP Basic Auth via http_credentials (NUEVO)

**Elegido:** usar `http_credentials` nativo de Playwright en `browser.new_context()`.

**Alternativas consideradas:**
1. **`http_credentials` (Playwright nativo)** ✅ — un campo de configuración, Playwright lo aplica automáticamente a cualquier request.
2. **Header `Authorization: Basic ...` manual** — más control, pero requiere middleware en cada request.
3. **`page.set_extra_http_headers()`** — funciona pero contamina headers de todos los requests con la auth.

**Razón de elegir #1:**
- Playwright maneja el handshake transparentemente (incluyendo 401 → reauth automático).
- Las credenciales viven en el context, no en el código de cada flow.
- Cleanup automático al cerrar context — sin riesgo de leak.

---

## Decisión D-U1-05: shopper_login via form interactivo (no API)

**Contexto:** SFCC tiene tanto formularios de login como APIs (OCAPI/SCAPI). ¿Cuál usar?

**Elegido:** form interactivo (`page.fill` + `page.click`).

**Razones:**
- El propósito del executor es **validar la experiencia del shopper real**. Loguear via API saltaría la validación del form de login (que es parte del producto).
- Si SFCC cambia el flujo de login (ej. agrega captcha, MFA), el run detecta la regresión.
- Coherente con principio "el agente se comporta como un humano usuario".

**Trade-off:** más lento (~3 s adicionales) y más frágil ante cambios de selectores. Aceptado.

---

## Decisión D-U1-06: Submódulo auth/ separado de flows/

**Elegido:** `src/executor/auth/shopper_login.py` como submódulo dedicado.

**Razones:**
- Reutilizable: ambos flows lo necesitan.
- Testeable independientemente (un test puede mockear solo el login sin tocar el flow completo).
- Si en el futuro hay otros tipos de auth (ej. SAML, OAuth para B2B), tienen su lugar natural.

---

## Decisión D-U1-07: Screenshots vía `page.screenshot()` con buffer en memoria + upload async

**Elegido:** capturar screenshot a `bytes` en memoria, luego upload async a S3 (no escribir a disco temporal).

**Razones:**
- Evita IO innecesario en ECS Fargate (disk efímero).
- Upload async (`boto3` con `aioboto3` o ejecución en thread pool) no bloquea el siguiente paso del flow.
- En dev local: fallback a escribir a `/tmp/testpilot-screenshots/` para inspección manual.

**Tamaño típico:** ~280 KB por screenshot WebP (compresión 80%). PNG fallback ~600 KB. **MVP usa PNG por simplicidad**, migrar a WebP si el costo S3 lo justifica.

---

## Decisión D-U1-08: Sin nuevas dependencias

**Confirmado:** U1 usa solo dependencias ya declaradas en U0 (`playwright`, `pydantic`, stdlib).

**No se agrega:**
- `aiohttp` — Playwright maneja todo el HTTP.
- `httpx` — idem.
- `tenacity` (retries) — el patrón retry lo maneja el flow específico, no librería general.

---

## Stack final U1

| Componente | Versión / Configuración |
|---|---|
| Browser | Chromium (incluido en `mcr.microsoft.com/playwright/python:v1.48.0-jammy`) |
| API | Playwright Python async (`from playwright.async_api import async_playwright`) |
| Modo default | headless |
| Concurrencia | `asyncio.gather` con cap `MAX_CONCURRENT_PROFILES=3` |
| HTTP Auth | `http_credentials` en `browser.new_context()` |
| Shopper login | form interactivo (`page.fill` + `page.click`) |
| Screenshots | `page.screenshot()` → bytes → upload async S3 (o disco en dev) |
| Logging | `logging.getLogger(__name__)` + `RedactingJsonFormatter` (U0) |
