# Infrastructure Design — U4 API Endpoints (actualizado 2026-05-24)

## Scope

U4 introduce **dos servicios AWS persistentes** que U0 NO crea (responsabilidad de IaC en Operations, pero documentados aquí porque U4 los consume):

1. **DynamoDB tabla `environments`** — persistencia del Environment Registry.
2. **DynamoDB tabla `runs`** — historial de runs (sprint 3+; MVP usa InMemoryBaselineStore).
3. **S3 bucket `testpilot-screenshots-{env}`** — almacenamiento de screenshots de pasos.
4. **AWS Secrets Manager** — credenciales `env_access` y `shopper` por ambiente.

Adicionalmente: configuración de FastAPI para servir el dashboard MD0 y aplicar security headers.

---

## 1. DynamoDB tabla `environments`

### Schema

| Atributo | Tipo | Notas |
|---|---|---|
| `environment_id` | S (string) | **Partition key** — Literal `sandbox`/`development`/`staging` |
| `display_name` | S | |
| `store_url` | S | HTTPS URL |
| `env_access_secret_path` | S | `testpilot/{env}/env-access` |
| `shopper_secret_path` | S | `testpilot/{env}/shopper` |
| `anti_bot_whitelisted` | BOOL | |
| `active` | BOOL | Soft delete flag |
| `created_at` | S | ISO 8601 |
| `updated_at` | S | ISO 8601 |

### Configuración

- **Capacity mode:** On-demand (baja escritura — solo cuando admin crea/edita).
- **Encryption at rest:** AWS-managed KMS.
- **Point-in-time recovery:** habilitado (35 días).
- **TTL:** No (los environments no expiran).
- **Backups:** snapshot diario por 30 días.

### Accesos

| Operación | Frecuencia | Quién |
|---|---|---|
| `get_item(environment_id)` | Alta (en cada `/v1/run` resolve, cacheado 60s) | U4 EnvironmentRegistry |
| `scan()` con `active=true` | Baja (poblar dropdown del dashboard) | U4 list_environments |
| `put_item` | Muy baja (creación de ambiente, ~5 veces total en proyecto) | U4 admin endpoints |
| `update_item` | Baja (edición ocasional) | U4 admin endpoints |

### Estimación de costo

3 environments × pocas operaciones/día → **< $1/mes** en On-demand.

---

## 2. DynamoDB tabla `runs` (sprint 3+)

### Schema

| Atributo | Tipo | Notas |
|---|---|---|
| `run_id` | S | **Partition key** — UUID v4 |
| `environment_id` | S | |
| `profile_name` | S | mobile-co/desktop-co/desktop-ec |
| `flow_name` | S | checkout-full/checkout-card-declined |
| `started_at` | S | ISO 8601 |
| `finished_at` | S | ISO 8601 |
| `duration_ms` | N | |
| `traffic_light` | S | green/yellow/red |
| `bootstrap_mode` | BOOL | |
| `orders_created` | N | siempre 0 |
| `status` | S | success/failed/error |
| `report` | M (Map) | ExecutionReport completo serializado |
| `expires_at` | N | Unix timestamp = finished_at + 90 days (TTL) |

### Índices GSI

#### GSI `by-env-profile-flow-date`
- PK: `env_profile_flow` (composite string `{env}#{profile}#{flow}`)
- SK: `started_at`
- **Uso:** `get_last_n_runs(environment_id, profile, flow)` → query directo con `Limit=10`, sin scan.

#### GSI `by-env-and-date`
- PK: `environment_id`
- SK: `started_at`
- **Uso:** historial filtrado por ambiente (P5 del dashboard).

#### GSI `by-traffic-light-and-date`
- PK: `traffic_light`
- SK: `started_at`
- **Uso:** dashboard filter "solo rojos".

### Configuración

- **Capacity mode:** On-demand.
- **TTL:** atributo `expires_at` → auto-delete tras 90 días (NFR de costo).
- **Encryption at rest:** AWS-managed KMS.
- **Point-in-time recovery:** habilitado.

### Estimación de costo

10 runs/día × 6 perfiles/run × ~10 KB/item × 30 días = ~18 MB/mes.
Reads via GSI cacheado → **~$5/mes** en On-demand.

---

## 3. S3 bucket de screenshots

### Configuración

- **Nombre:** `testpilot-screenshots-{aws-account-id}-{region}` (único globalmente).
- **Versionado:** disabled (storage cost mitigation).
- **Bloqueo de acceso público:** total (block all public access).
- **Encryption at rest:** AES-256 (S3-managed).
- **Lifecycle policy:**
  - Día 0–7: `STANDARD`
  - Día 8–30: `STANDARD_IA` (Infrequent Access)
  - Día 31–89: `GLACIER_INSTANT_RETRIEVAL`
  - Día 90: delete
- **Bucket policy:** solo ECS task role puede `PutObject` y `GetObject`.

### Estructura de keys

```
{run_id}/{profile_id}/{flow_name}/{step_name}-{ok|fail}.png
```

Ejemplo:
```
abc123-de45/mobile-co/checkout-full/shopper_login-ok.png
abc123-de45/mobile-co/checkout-full/checkout_payment-fail.png
```

### Estimación de costo

Con `screenshot_on_success=True` (cada paso):
- 10 runs/día × 3 perfiles × 2 flows × 10 pasos × 2 estados × 280 KB ≈ **3.4 GB/día**.
- 30 días en STANDARD → ~100 GB-mes → ~$2.3.
- Tras lifecycle (IA + Glacier) → cost trend bajo, pero requests también cuestan.
- **Total estimado: ~$15–20/mes** (alineado con prompt del proyecto: "~17 GB/mes" total post-IA).

Con `screenshot_on_success=False` (solo fallos + final):
- Reduce ~95% → **< $1/mes**.

**Recomendación PO:** mantener `screenshot_on_success=True` solo en sprint 0-2. A partir de sprint 3, default `False`.

---

## 4. AWS Secrets Manager

### Estructura de secrets

| Secret name | Contenido |
|---|---|
| `testpilot/sandbox/env-access` | `{"username": "...", "password": "..."}` |
| `testpilot/sandbox/shopper` | `{"email": "qa-sandbox@testpilot.internal", "password": "..."}` |
| `testpilot/development/env-access` | (idem) |
| `testpilot/development/shopper` | (idem) |
| `testpilot/staging/env-access` | (idem) |
| `testpilot/staging/shopper` | (idem) |
| `testpilot/api/api-key` | `{"value": "<TESTPILOT_API_KEY>"}` |
| `testpilot/api/anthropic-key` | `{"value": "sk-ant-..."}` |

### Configuración

- **Rotación:** manual en MVP. Automatizar en sprint 3+ con Lambda rotator.
- **Encryption:** AWS-managed KMS.
- **Acceso:** solo ECS task role.

### Estimación de costo

8 secrets × $0.40/mes = **$3.20/mes**.

---

## 5. ECS Fargate task definition

### Configuración

- **CPU:** 1 vCPU
- **RAM:** 2 GB
- **Imagen:** `{ecr-account}.dkr.ecr.{region}.amazonaws.com/testpilot-sfcc:{git-sha}`
- **Puerto:** 8000
- **Variables de entorno:**
  - `AWS_REGION`
  - `DYNAMODB_TABLE_ENVIRONMENTS=testpilot-environments`
  - `DYNAMODB_TABLE_RUNS=testpilot-runs` (sprint 3+)
  - `S3_BUCKET_SCREENSHOTS=testpilot-screenshots-{account}-{region}`
  - `SECRETS_MANAGER_PREFIX=testpilot/`
  - `MAX_CONCURRENT_PROFILES=3`
  - `RUN_TIMEOUT_SECONDS=1800`
  - `LOG_LEVEL=INFO`
  - `DOCS_ENABLED=false`
  - `GIT_SHA={injected-by-ci}`
- **Secrets (inyectados como env vars):**
  - `TESTPILOT_API_KEY` ← `testpilot/api/api-key`
  - `ANTHROPIC_API_KEY` ← `testpilot/api/anthropic-key`
- **Task role:** IAM role con permisos:
  - `dynamodb:GetItem`, `PutItem`, `UpdateItem`, `Scan`, `Query` en tablas testpilot-*
  - `s3:PutObject`, `GetObject` en bucket testpilot-screenshots-*
  - `secretsmanager:GetSecretValue` en `testpilot/*`
  - `cloudwatch:PutMetricData`
  - `logs:CreateLogStream`, `PutLogEvents`

### Logging

- **Driver:** `awslogs`
- **Group:** `/ecs/testpilot-sfcc`
- **Stream prefix:** `{task-id}`
- **Format:** JSON (python-json-logger)
- **Retención:** 14 días

### Escalado

- **MVP:** 1 task (sin auto-scaling).
- **Post-MVP:** target tracking por CPU > 70%, min 1 / max 3 tasks.

### Estimación de costo

1 vCPU × 2 GB × 24h × 30 días = ~$60/mes en Fargate spot, ~$80 on-demand.

---

## 6. ALB (Application Load Balancer)

### Configuración

- **Tipo:** internal (no facing internet) — accesible solo desde VPN corporativa.
- **TLS:** ACM certificate, TLS 1.2+, perfect forward secrecy.
- **Target group:** ECS service en port 8000.
- **Health check:** `GET /health` cada 30 s, threshold 2 fallos.
- **WAF:** AWS WAF con reglas managed core rules + bot protection.

### Estimación de costo

ALB básico → ~$22/mes.

---

## 7. CloudWatch

### Logs

- Log group `/ecs/testpilot-sfcc` retención 14 días.

### Métricas custom

Publicadas por la app:
- `testpilot.run.count` (por traffic_light, environment_id)
- `testpilot.run.duration_ms` (por environment_id, profile, flow)
- `testpilot.api.request.count` (por endpoint, status)
- `testpilot.api.request.duration_ms` (por endpoint)
- `testpilot.invariant_violated.count` (CRÍTICO — alerta inmediata)

### Alarmas

| Alarma | Threshold | Acción |
|---|---|---|
| `invariant_violated > 0` | inmediato | PagerDuty/Slack crítico |
| `api.request.error_rate > 10%` | 5 min | Slack warning |
| `run.duration_ms.p95 > 25 min` | 1 hora | Slack info |
| `task health check failing` | 2 fallos consecutivos | Auto-replace task + Slack |

---

## 8. CI/CD (handoff a Operations)

### Pipeline esperado (GitHub Actions o similar)

```yaml
on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  backend-test:
    - pytest tests/
    - mypy src/
    - ruff check src/
    - pip-audit
  
  dashboard-test:
    - cd src/dashboard && pnpm install --frozen-lockfile
    - pnpm lint && pnpm test
    - pnpm audit --audit-level=high
  
  docker-build:
    needs: [backend-test, dashboard-test]
    if: github.ref == 'refs/heads/main'
    - docker build -t testpilot-sfcc:${SHA}
    - docker push to ECR
  
  deploy:
    needs: [docker-build]
    if: github.ref == 'refs/heads/main'
    - aws ecs update-service --task-definition testpilot-sfcc:${SHA}
```

---

## 9. Estimación total de costos AWS por mes

| Servicio | Costo |
|---|---|
| ECS Fargate (1 task on-demand) | ~$80 |
| ALB | ~$22 |
| DynamoDB (2 tablas on-demand) | ~$6 |
| S3 (con screenshots) | ~$15–20 |
| Secrets Manager (8 secrets) | ~$3 |
| CloudWatch (logs + métricas) | ~$5 |
| Data transfer | ~$3 |
| **TOTAL MVP** | **~$135/mes** |

**Trigger de revisión:** si excede $200/mes en sprint 2, revisar disciplina de screenshots (bajar `screenshot_on_success` a false por default).

---

## 10. Resumen de cambios infra vs versión anterior

| Componente | Antes | Ahora |
|---|---|---|
| DynamoDB tablas | 0 (todo in-memory) | 2 (`environments` desde día 1, `runs` sprint 3+) |
| S3 bucket | 0 (screenshots locales) | 1 (con lifecycle 90 días) |
| Secrets Manager | API key solo | 8 secrets (2 por ambiente + API + Anthropic) |
| Endpoints API | 3 | 13 (CRUD env + runs + status + history + screenshots + health) |
| ALB | TBD | Explícito + WAF + internal-only |
| Costo estimado | ~$80/mes | ~$135/mes (justificado por mayor superficie) |
