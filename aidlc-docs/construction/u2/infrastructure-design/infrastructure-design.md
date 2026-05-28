# Infrastructure Design — U2 Baseline Manager (2026-05-28)

## Scope

U2 es la unidad con **menor huella de infraestructura** del sistema. En MVP opera completamente en memoria — sin I/O externo, sin servicios AWS propios.

| Sprint | Infraestructura de U2 | Notas |
|---|---|---|
| **MVP (0–2)** | Ninguna — `InMemoryBaselineStore` | Datos perdidos al reiniciar el task ECS |
| **Sprint 3+** | DynamoDB `testpilot-runs` | Migración transparente vía Protocol swap |

---

## 1. MVP — InMemoryBaselineStore (sin infraestructura)

U2 vive íntegramente dentro del proceso FastAPI como un objeto Python en memoria.

```
ECS task process
└── InMemoryBaselineStore (dict en RAM)
    ├── _runs: dict[(env, profile, flow), list[RunRecord]]
    └── _index_by_id: dict[run_id, RunRecord]
```

**Implicaciones operativas:**
- Los baselines se resetean con cada deploy o restart del task ECS.
- Durante Sprint 0–1, cada run parte siempre en `bootstrap_mode=True` (0 runs en historia).
- Esto es **aceptable en MVP**: el sistema necesita al menos 14 runs success por tuple `(env, profile, flow)` para emitir alertas — en desarrollo temprano ese historial no existe de todas formas.

**No hay nada que aprovisionar en AWS para U2 en MVP.**

---

## 2. Sprint 3+ — DynamoDB `testpilot-runs`

Cuando se requiera persistencia entre reinicios, se activa `DynamoDBBaselineStore` (ya diseñada en `nfr-design.md`). La tabla es aprovisionada por U4 infra y compartida.

### Schema DynamoDB (diseñado en U4, referenciado aquí)

| Atributo | Tipo | Rol |
|---|---|---|
| `run_id` | S | Partition Key (para `get_run`) |
| `environment_id` | S | Parte del GSI PK |
| `profile_name` | S | Parte del GSI PK |
| `flow_name` | S | Parte del GSI PK |
| `started_at` | S | Sort Key del GSI |
| `duration_ms` | N | Input de `calculate_p95` |
| `status` | S | Filtro en `get_last_n_runs` |
| `expires_at` | N | TTL — auto-delete a los 90 días |

### GSI para `get_last_n_runs` (O(log N) sin scan)

```
GSI: by-env-profile-flow-date
  PK  →  "{environment_id}#{profile_name}#{flow_name}"
  SK  →  started_at (ISO 8601 — orden cronológico natural)

Query:
  KeyConditionExpression: PK = "staging#mobile-co#checkout-full"
  FilterExpression: #status = :success
  ScanIndexForward: False   → más recientes primero
  Limit: 10
```

### Permisos IAM que U2 necesitará en Sprint 3+

```json
{
  "Effect": "Allow",
  "Action": [
    "dynamodb:PutItem",
    "dynamodb:GetItem",
    "dynamodb:Query"
  ],
  "Resource": [
    "arn:aws:s3:::testpilot-runs",
    "arn:aws:s3:::testpilot-runs/index/by-env-profile-flow-date"
  ]
}
```

Estos permisos ya están incluidos en el Task Role de U4 — no requieren cambio de IAM al migrar.

---

## 3. Variables de entorno

### MVP
Ninguna. `InMemoryBaselineStore` no consume env vars.

### Sprint 3+
| Variable | Propietario | Uso |
|---|---|---|
| `DYNAMODB_TABLE_RUNS` | U4 task definition | Nombre de la tabla de runs |
| `AWS_REGION` | ECS runtime | Región del cliente boto3 |

---

## 4. Mapa de servicios U2

| Componente | MVP | Sprint 3+ |
|---|---|---|
| Store de baselines | RAM (dict Python) | DynamoDB `testpilot-runs` |
| Cálculo p95 | CPU local (stdlib) | CPU local (sin cambio) |
| Logs | CloudWatch vía awslogs driver | Sin cambio |
| Permisos AWS adicionales | Ninguno | DynamoDB Query + PutItem |

---

## 5. Estimación de costo

| Escenario | Costo U2 |
|---|---|
| MVP (InMemory) | $0 — sin servicios adicionales |
| Sprint 3+ (DynamoDB) | ~$2–4/mes (ya incluido en estimación U4) |
