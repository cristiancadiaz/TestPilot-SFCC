# Infrastructure Design — U0 Setup Base (actualizado 2026-05-24)

## Scope
U0 no despliega servicios cloud — su contribución a infraestructura es:
1. Dockerfile multi-stage (Python runtime + Node builder para MD0).
2. `.dockerignore`.
3. Configuración de imagen para soportar las 3 tablas DynamoDB y los buckets S3 que U2/U4 consumirán (sin crearlas — solo dejar el cliente boto3 disponible).

---

## 1. Dockerfile — multi-stage

```dockerfile
# syntax=docker/dockerfile:1.6

# ============================================
# Stage 1: Build del dashboard MD0
# ============================================
FROM node:20-alpine AS dashboard-builder
WORKDIR /build

# Cache de dependencias separado del código
COPY src/dashboard/package.json src/dashboard/pnpm-lock.yaml ./
RUN corepack enable pnpm && pnpm install --frozen-lockfile

# Código del dashboard
COPY src/dashboard/ ./
RUN pnpm run build
# Output: /build/dist/

# ============================================
# Stage 2: Runtime Python + Playwright
# ============================================
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

# Crear usuario no-root (SECURITY-13)
RUN useradd --create-home --shell /bin/bash --uid 1001 appuser

WORKDIR /app

# Cache de pip separado del código
COPY --chown=appuser:appuser pyproject.toml .
RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir pip-audit && \
    pip-audit --strict || (echo "Dependency vulnerabilities found" && exit 1)

# Código backend
COPY --chown=appuser:appuser src/ src/
COPY --chown=appuser:appuser specs/ specs/

# Dashboard estático del stage 1
COPY --from=dashboard-builder --chown=appuser:appuser /build/dist /app/src/dashboard/dist

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Decisiones clave:**
- **`syntax=docker/dockerfile:1.6`**: habilita features modernos (cache mounts si los necesitamos en futuro).
- **`useradd --uid 1001`**: UID fijo para consistencia entre builds (útil para volumes con permisos).
- **`pip-audit` en build**: falla la imagen si hay vulnerabilidad HIGH/CRITICAL → SECURITY-08.
- **`HEALTHCHECK`**: ECS y Docker Compose lo usan para health probes. Usa `urllib` (stdlib) en lugar de `curl` para no requerir paquete adicional.
- **No `EXPOSE 80/443`**: solo 8000 — TLS termina en el ALB de AWS.

---

## 2. `.dockerignore`

```
# Secretos
.env
.env.*
.envrc
*.pem
*.key
secrets/

# Control de versiones
.git/
.gitignore

# Documentación AI-DLC (no necesaria en imagen runtime)
aidlc-docs/
construction-backup-*/
.aidlc/
.aidlc-rule-details/

# Caches y builds locales
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Node (el build se hace dentro del stage 1)
src/dashboard/node_modules/
src/dashboard/dist/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
```

**Razón:** evita filtrar secrets, evita imágenes infladas con cache local, evita confusión entre versión del repo y versión dentro de la imagen.

---

## 3. Variables de entorno requeridas en runtime

U0 documenta cuáles env vars debe **recibir** la imagen al ejecutarse (no las define como `ENV` en el Dockerfile):

| Variable | Origen | Consumida por | Obligatoria |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Secrets Manager → ECS task definition | `src/agents/translator.py` | Sí (si translator activo) |
| `TESTPILOT_API_KEY` | Secrets Manager → ECS task definition | `src/api/main.py` (auth) | Sí |
| `AWS_REGION` | ECS env | boto3 clients | Sí (default us-east-1) |
| `DYNAMODB_TABLE_ENVIRONMENTS` | ECS env | U4 EnvironmentRegistry | Sí |
| `DYNAMODB_TABLE_RUNS` | ECS env | U4 + U2 baseline | Sí |
| `S3_BUCKET_SCREENSHOTS` | ECS env | U1 executor | Sí |
| `SECRETS_MANAGER_PREFIX` | ECS env (default `testpilot/`) | U4 EnvironmentResolver | No (default OK) |
| `LOG_LEVEL` | ECS env (default INFO) | logging | No |
| `MAX_CONCURRENT_PROFILES` | ECS env (default 3) | U1 | No |

**Regla:** Dockerfile NO declara `ENV` con valores reales. Solo el `ENV` de defaults técnicos sin sensibilidad (ej. `PYTHONUNBUFFERED=1`).

---

## 4. Recursos AWS que U0 NO crea, pero deja preparado el cliente

U0 no provisiona DynamoDB ni S3 — eso es responsabilidad de IaC (Terraform/CDK) en etapa Operations. Pero deja documentado el contrato que IaC debe cumplir para que U4 funcione:

### Tabla DynamoDB `environments`
- Partition key: `environment_id` (string)
- Atributos: `display_name`, `store_url`, `env_access_secret_path`, `shopper_secret_path`, `anti_bot_whitelisted` (bool), `active` (bool), `created_at`, `updated_at`
- Modo: On-demand (baja escritura)
- Encryption at rest: AWS-managed KMS

### Tabla DynamoDB `runs`
- Partition key: `run_id` (string UUID)
- Atributo `environment_id`, `started_at`, `finished_at`, `traffic_light`, `bootstrap_mode`, `orders_created` (siempre 0), `profile_results` (lista), `baseline_comparison`, `state`
- GSI `by-environment-and-date`: PK `environment_id`, SK `started_at`
- GSI `by-traffic-light`: PK `traffic_light`, SK `started_at`
- Modo: On-demand
- TTL en `expires_at` = `finished_at + 90 days`

### Bucket S3 `testpilot-screenshots-{env}`
- Versionado: disabled (storage cost)
- Lifecycle: delete después de 90 días
- Encryption at rest: AES-256
- Bloqueo de acceso público total
- Bucket policy: solo task role del ECS puede PUT/GET
- Estructura de keys: `{run_id}/{profile_id}/{flow_name}/{step_name}-{ok|fail}.png`

### Secrets Manager
- Prefijo: `testpilot/`
- Secrets esperados por ambiente:
  - `testpilot/{env}/env-access` → JSON `{"username": ..., "password": ...}`
  - `testpilot/{env}/shopper` → JSON `{"email": ..., "password": ...}`
- Rotación: manual en MVP (sprint 3+ automatizar)
- Encryption: AWS-managed KMS

**Estimación de costos AWS para MVP (3 ambientes, 10 runs/día):**
- DynamoDB: ~$5/mes (on-demand, bajo volumen)
- S3: ~$15/mes (con disciplina de screenshots — sin disciplina escalaría a $400+/mes — R3 mitigado)
- Secrets Manager: ~$2.50/mes (5 secrets × $0.40)
- ECS Fargate: ~$60/mes (1 task 1 vCPU/2GB, ~50% utilización)
- **Total estimado MVP: ~$80–100/mes**

---

## 5. Healthcheck — diseño

Endpoint `/health` (definido en U4) debe retornar:
- 200 OK si: FastAPI responde, conexión a DynamoDB OK (`describe_table`), conexión a Secrets Manager OK (`list_secrets` con max=1).
- 503 si: cualquier dependencia falla.

Healthcheck del Dockerfile lo invoca cada 30 s. ECS lo usa como readiness probe.

---

## 6. Logs y observabilidad (handoff a Operations)

U0 deja preparado el formato. La infraestructura de observabilidad la define Operations:
- **stdout/stderr** capturado por CloudWatch Logs (default ECS).
- Formato JSON (python-json-logger) → CloudWatch Insights queries fáciles.
- Logs structurados con campos: `level`, `timestamp`, `module`, `run_id` (cuando aplica), `environment_id`, `message`.
- **Sin** logs de password / API key — garantizado por `RedactingJsonFormatter` (D-U0-06).

---

## Resumen

U0 entrega:
- Dockerfile multi-stage testeable localmente con `docker build`.
- `.dockerignore` que evita filtraciones y mantiene imagen liviana.
- Contrato documentado de variables de entorno que la imagen espera recibir.
- Contrato documentado de recursos AWS que se asume existirán (creados por IaC en Operations).
- Cliente boto3 disponible para U2/U4 sin requerir instalación adicional.

**Sin** despliegue, **sin** IaC, **sin** secretos en imagen.
