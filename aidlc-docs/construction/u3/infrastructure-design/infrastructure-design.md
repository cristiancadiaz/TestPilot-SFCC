# Infrastructure Design — U3 Reporter (2026-05-28)

## Scope

U3 es la unidad con **cero dependencias de infraestructura AWS**. Opera completamente dentro del proceso FastAPI como transformación pura en memoria — no hace I/O externo propio.

| Servicio AWS | Uso directo por U3 | Nota |
|---|---|---|
| S3 | ❌ No | Las URLs de screenshots llegan como strings en `ProfileResult` — U3 no hace GetObject |
| DynamoDB | ❌ No | U3 llama a `BaselineStore` (Protocol) — la impl concreta (InMemory o DynamoDB) es responsabilidad de U2 |
| Secrets Manager | ❌ No | Sin credenciales que resolver |
| CloudWatch Logs | ✅ Indirecto | Los logs de U3 salen por stdout → awslogs driver → CloudWatch (igual que todo el proceso) |

---

## 1. Dependencias en tiempo de ejecución

### specs/execution_report.schema.json — schema local

U3 valida el output de `to_json_dict` contra el JSON Schema del contrato. Este archivo **viaja dentro de la imagen Docker** (copiado en U0 como `COPY specs/ specs/`).

```
Docker image
└── /app/
    ├── src/reporter/report_generator.py
    └── specs/
        └── execution_report.schema.json   ← leído en memoria al primer uso
```

No hay I/O de red — la validación es local. Si el archivo falta en la imagen, `to_json_dict` lanza `FileNotFoundError` al primer call → U4 detecta startup failure.

### BaselineStore — inyectado, no acoplado

U3 recibe `baseline_store: BaselineStore` como parámetro. En MVP es `InMemoryBaselineStore` (U2, en RAM). En Sprint 3+ será `DynamoDBBaselineStore` (U2, en DynamoDB). U3 no sabe ni le importa cuál implementación recibe.

```python
# src/reporter/report_generator.py — ningún import de boto3 ni AWS aquí
def generate_report(
    profile_results: list[ProfileResult],
    baseline_store: BaselineStore,   # inyectado desde U4
    ...
) -> ExecutionReport:
    ...
```

---

## 2. Mapa de servicios U3

| Componente | Tipo | Dirección | Protocolo |
|---|---|---|---|
| `specs/execution_report.schema.json` | Archivo local (imagen Docker) | Local read | Filesystem |
| `BaselineStore.get_last_n_runs` | Python Protocol call | In-process | Función Python |
| `BaselineStore.save_run` | Python Protocol call | In-process | Función Python |
| Logs estructurados | stdout → awslogs → CloudWatch | Saliente | awslogs driver |

---

## 3. Variables de entorno

U3 no consume ninguna variable de entorno directamente.

El único comportamiento configurable es el nivel de log, heredado de `LOG_LEVEL` (propietario: U0 logging config).

---

## 4. Estimación de costo

| Escenario | Costo U3 |
|---|---|
| MVP | $0 — sin servicios propios |
| Sprint 3+ | $0 — sin cambios en U3 |

El único costo asociado indirectamente es CloudWatch Logs (compartido con todo el proceso, ~$5/mes en estimación de U4).
