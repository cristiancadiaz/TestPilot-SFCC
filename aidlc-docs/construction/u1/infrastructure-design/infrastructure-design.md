# Infrastructure Design — U1 Executor Playwright (2026-05-28)

## Scope

U1 no introduce servicios AWS propios más allá de los definidos en U4. Comparte el ECS Fargate task y consume dos servicios ya aprovisionados por U4:

| Servicio AWS | Uso en U1 | Propietario del aprovisionamiento |
|---|---|---|
| **S3** `testpilot-screenshots-*` | `PutObject` — screenshots de steps (fail + final) | U4 infra |
| **ECS Fargate compute** | CPU/RAM para asyncio + Playwright Chromium | U4 infra |

U1 **NO** llama a Secrets Manager directamente. Las credenciales (`env_access`, `shopper`) llegan resueltas como objeto `ResolvedEnvironment` — U4 las obtiene antes de invocar U1.

---

## 1. S3 — Almacenamiento de screenshots

### Operaciones que realiza U1

| Operación | Frecuencia | Ruta |
|---|---|---|
| `s3:PutObject` | Por step fallido + paso final de cada flow | `{run_id}/{profile}/{flow}/{step}-{ok\|fail}.png` |

### Configuración relevante para U1

```python
# Variables de entorno consumidas por U1
S3_BUCKET_SCREENSHOTS = os.environ["S3_BUCKET_SCREENSHOTS"]
# Ejemplo: testpilot-screenshots-123456789-us-east-1

# Patrón de key
key = f"{run_id}/{profile_id}/{flow_name}/{step_name}-{state}.png"
# Ejemplo: abc123/mobile-co/checkout-full/shopper_login-ok.png
```

### Cliente S3 — patrón async (NFR-U1-P5 del nfr-design)

```python
# src/executor/screenshots.py
import asyncio
import boto3
from botocore.config import Config
from concurrent.futures import ThreadPoolExecutor

_s3 = boto3.client("s3", config=Config(max_pool_connections=20))
_executor = ThreadPoolExecutor(max_workers=4)

async def upload_screenshot(
    image_bytes: bytes,
    run_id: str,
    profile_id: str,
    flow_name: str,
    step_name: str,
    state: str,  # "ok" | "fail"
) -> str:
    key = f"{run_id}/{profile_id}/{flow_name}/{step_name}-{state}.png"
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

**Por qué ThreadPoolExecutor:** `boto3.put_object` es síncrono — ejecutarlo en un thread pool no bloquea el event loop de Playwright. Con 4 workers cubre 3 perfiles paralelos + 1 de margen.

---

## 2. Playwright — Runtime en ECS

### Requisito de imagen Docker

Playwright Chromium está preinstalado en la imagen base `mcr.microsoft.com/playwright/python:v1.48.0-jammy` (definida en U0). U1 no instala browsers en runtime.

```python
# src/executor/runner.py
from playwright.async_api import async_playwright

async def run_profile(...) -> ProfileResult:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        # ...
```

### Recursos de compute por run

| Recurso | Consumo estimado por run (3 perfiles paralelos) |
|---|---|
| CPU | ~0.6 vCPU pico (3 browsers × asyncio) |
| RAM | ~400–600 MB (3 Chromium headless) |
| Tiempo de ejecución | 3–15 min según ambiente y checkout |
| Ancho de banda saliente | ~50–100 MB (requests al storefront + screenshots) |

El ECS task está configurado con 1 vCPU / 2 GB RAM — suficiente para 3 perfiles paralelos con margen.

---

## 3. Network — Acceso al storefront SFCC

U1 hace requests HTTP salientes desde el ECS task hacia el storefront. Requiere:

| Requisito | Configuración |
|---|---|
| Salida HTTP/HTTPS a `*.tienda.com` | Permitida por security group del ECS task |
| IP del ECS task en whitelist anti-bot | Validado en Sprint 0 (R1 del proyecto) |
| HTTP Basic Auth (env_access) | Manejado por `BrowserContext.http_credentials` |
| DNS resolución de store_url | Resuelto via VPC DNS |

**R1 del proyecto (alto riesgo):** si Akamai/Cloudflare bloquea el IP del task ECS, U1 detectará `InfrastructureError` en el step `env_access_auth`. La validación con DevOps/Security debe ocurrir en Sprint 0 antes de escribir código de executor.

---

## 4. Variables de entorno que consume U1

| Variable | Propietario | Uso |
|---|---|---|
| `S3_BUCKET_SCREENSHOTS` | U4 task definition | Bucket destino de screenshots |
| `MAX_CONCURRENT_PROFILES` | U4 task definition | Semáforo asyncio (default: 3) |
| `RUN_TIMEOUT_SECONDS` | U4 task definition | Timeout global del run (default: 1800) |
| `STEP_TIMEOUT_MS` | U4 task definition | Timeout por step Playwright (default: 30000) |
| `NAV_TIMEOUT_MS` | U4 task definition | Timeout de navegación (default: 60000) |

Las credenciales (`env_access`, `shopper`) llegan como objeto Python — no como env vars.

---

## 5. Mapa de servicios U1

| Componente | Servicio | Dirección | Protocolo |
|---|---|---|---|
| Screenshot upload | S3 | Saliente | HTTPS (boto3) |
| Browser automation | SFCC Storefront | Saliente | HTTPS (Playwright) |
| Logs de ejecución | CloudWatch Logs | Saliente | awslogs driver |
| Código fuente | ECS task (mismo proceso) | Local | Python import |

---

## 6. Permisos IAM requeridos por U1

Subset del Task Role de U4 que U1 consume:

```json
{
  "Effect": "Allow",
  "Action": ["s3:PutObject", "s3:GetObject"],
  "Resource": "arn:aws:s3:::testpilot-screenshots-*/*"
}
```

No necesita permisos de Secrets Manager, DynamoDB ni CloudWatch directamente — esos los gestiona U4.
