# Domain Entities — U2 Baseline Manager (actualizado 2026-05-24)

## Módulo: `src/baseline/baseline_manager.py`

U2 **consume** `RunRecord` (definido en U0) y **produce** `BaselineComparison` (definido en U0) + `TrafficLight` (enum de U0). No define entidades propias.

---

## BaselineStore (Protocol — definido en U2)

Interfaz de almacenamiento. Cambio vs versión anterior: agrega `environment_id` como parámetro en `get_last_n_runs`.

```python
from typing import Protocol, Literal

class BaselineStore(Protocol):
    def save_run(self, run: RunRecord) -> None: ...
    
    def get_last_n_runs(
        self,
        environment_id: str,
        profile: str,
        flow: str,
        n: int,
        status: Literal["success", "failed", "error"] | None = None,
    ) -> list[RunRecord]: ...
    
    def get_run(self, run_id: str) -> RunRecord | None: ...
    
    def list_runs(
        self,
        environment_id: str | None = None,
        traffic_light: Literal["green", "yellow", "red"] | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        flow: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[RunRecord], int]:  # (items, total_count)
        ...
```

**Cambios vs versión anterior:**
- `get_last_n_runs` recibe `environment_id` (clave compuesta).
- `get_last_n_runs` recibe `status` opcional para filtrar.
- **NUEVO:** `list_runs` para servir al dashboard P5 (historial filtrable) — paginación obligatoria.

---

## InMemoryBaselineStore (impl MVP)

```python
class InMemoryBaselineStore:
    def __init__(self) -> None:
        # Clave: (environment_id, profile_name, flow_name)
        self._runs: dict[tuple[str, str, str], list[RunRecord]] = defaultdict(list)
        self._index_by_id: dict[str, RunRecord] = {}
        self._all_runs: list[RunRecord] = []  # para list_runs
    
    # ... métodos según business-logic-model.md
```

**Limitaciones MVP:** no persiste entre reinicios del proceso. Aceptable en sprint 0-1 (no hay producción), inaceptable en sprint 3+ (migrar a DynamoDB).

---

## Funciones puras (BaselineCalculator)

Conceptual — no son una clase, son funciones módulo-level.

| Función | Input | Output | Invariante PBT |
|---|---|---|---|
| `calculate_p95(runs)` | `list[RunRecord]` | `int` (ms) | `min <= result <= max` (PBT-02) |
| `is_bootstrap_mode(runs)` | `list[RunRecord]` | `bool` | True iff len(success) < 14 (PBT-03) |
| `compute_traffic_light(current_ms, p95_ms, bootstrap)` | int, int, bool | `TrafficLight` | bootstrap → ¬YELLOW (PBT-07); current > p95*1.5 → RED (PBT-08) |

---

## Entidades consumidas (desde src.models — definidas en U0)

### RunRecord
```python
class RunRecord(BaseModel):
    run_id: str
    environment_id: EnvironmentId     # ★ NUEVO en versión actual
    profile_name: ProfileId
    flow_name: FlowName
    duration_ms: int
    status: Literal["success", "failed", "error"]
    created_at: datetime
```

**Cambio vs versión anterior:** `environment_id` ahora es campo obligatorio. Forma parte de la clave compuesta del baseline.

### BaselineComparison
```python
class BaselineComparison(BaseModel):
    p95_ms: int
    current_ms: int
    bootstrap_mode: bool
    runs_count: int
```

Sin cambios. U2 lo construye y se lo entrega a U3 (Reporter).

### TrafficLight
```python
class TrafficLight(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
```

Sin cambios.

---

## Constantes (módulo-level)

```python
BOOTSTRAP_MIN_RUNS = 14
BASELINE_WINDOW = 10
YELLOW_THRESHOLD = 1.2
RED_THRESHOLD = 1.5
```

**Política:** modificar requiere PR con justificación. No son env vars (no se cambian por deployment).

---

## Resumen

U2 es **pequeña por diseño**:
- 1 Protocol (`BaselineStore`)
- 1 impl concreta (`InMemoryBaselineStore`)
- 3 funciones puras (cálculo + decisión)
- 4 constantes

Esto la hace 100% testeable con PBT y trivial de migrar a DynamoDB en el futuro.
