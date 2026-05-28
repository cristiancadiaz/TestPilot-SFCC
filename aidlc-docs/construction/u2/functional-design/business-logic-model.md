# Business Logic Model — U2 Baseline Manager (actualizado 2026-05-24)

## Propósito desde la perspectiva del producto

U2 decide **cuándo un número es "lento"**. El producto tiene que distinguir un deploy que tarda 4.2 s en cargar la PDP (normal) de uno que tarda 6.8 s (regresión). Para eso necesita historia: U2 mantiene la ventana móvil de últimas 10 ejecuciones exitosas, calcula p95 y emite el **semáforo**.

**Outcomes de negocio:**
1. **Detección honesta de regresiones de performance** — Principio P4: nada de "verde por defecto" ni "rojo paranoico".
2. **Bootstrap honesto** — durante las primeras 14 runs success NO se emiten alertas amarillas (M12).
3. **Baseline por ambiente** (CAMBIO MAYOR vs versión anterior): el baseline de sandbox es independiente del de staging — sandbox es típicamente más lento por recursos compartidos.

**Cambio respecto a versión previa:** la clave del baseline pasa de `(profile_name, flow_name)` a `(environment_id, profile_name, flow_name)`. Mezclar baselines de ambientes distintos genera falsos positivos/negativos.

---

## Componentes de U2

```
src/baseline/
├── __init__.py
└── baseline_manager.py
    │
    ├── BaselineStore (Protocol)
    ├── InMemoryBaselineStore (impl MVP)
    ├── calculate_p95(runs)            # función pura
    ├── is_bootstrap_mode(runs)        # función pura
    └── compute_traffic_light(...)     # función pura
```

**Por qué Protocol + impl concreta:** permite swap a `DynamoDBBaselineStore` en sprint 3+ sin tocar U3/U4. Es Strategy pattern declarativo.

**Por qué funciones puras:** `calculate_p95` y `compute_traffic_light` sin side effects → fáciles de testear con hypothesis (PBT-02, PBT-03, PBT-07, PBT-09).

---

## Flujo de cálculo de semáforo

```
ProfileResult (de U1)
    │
    ▼
┌────────────────────────────────────────────────┐
│  1. baseline_store.get_last_n_runs(           │
│         environment_id=env_id,                 │
│         profile=profile_name,                  │
│         flow=flow_name,                        │
│         n=10,                                  │
│         status="success",                      │
│     ) → list[RunRecord]                        │
└────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────┐
│  2. bootstrap = is_bootstrap_mode(runs)        │
│     # True si len < 14                         │
└────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────┐
│  3. p95_ms = calculate_p95(runs)               │
│     # 0 si lista vacía                         │
└────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────┐
│  4. light = compute_traffic_light(             │
│         current_ms=profile_result.duration_ms, │
│         p95_ms=p95_ms,                         │
│         bootstrap=bootstrap,                   │
│     )                                          │
│  Reglas:                                       │
│    bootstrap=True              → GREEN         │
│    current > p95 * 1.5         → RED           │
│    current > p95 * 1.2         → YELLOW        │
│    otherwise                   → GREEN         │
└────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────┐
│  5. baseline_store.save_run(                   │
│         RunRecord(                             │
│             run_id, environment_id,            │
│             profile_name, flow_name,           │
│             duration_ms, status,               │
│             created_at,                        │
│         )                                      │
│     )                                          │
│  # Persistir SIEMPRE — incluso si falló        │
└────────────────────────────────────────────────┘
    │
    ▼
   (light, BaselineComparison) → consumido por U3 (Reporter)
```

---

## Constantes de configuración

```python
BOOTSTRAP_MIN_RUNS = 14            # umbral para salir de bootstrap
BASELINE_WINDOW = 10                # tamaño de ventana móvil
YELLOW_THRESHOLD = 1.2              # 20% sobre p95 → amarillo
RED_THRESHOLD = 1.5                 # 50% sobre p95 → rojo
```

Estas constantes viven en `src/baseline/baseline_manager.py` como módulo-level. **No** son env vars — un cambio aquí es un cambio de política del producto y debe ir en un PR con justificación.

---

## Lógica de `calculate_p95`

```python
def calculate_p95(runs: list[RunRecord]) -> int:
    """
    Calcula el percentil 95 de duration_ms de runs SUCCESS.
    
    Invariantes:
    - calculate_p95([]) == 0
    - min(durations) <= calculate_p95(runs) <= max(durations) (PBT-02)
    - calculate_p95([r]) == r.duration_ms
    """
    if not runs:
        return 0
    success_durations = sorted(r.duration_ms for r in runs if r.status == "success")
    if not success_durations:
        return 0
    # P95 con interpolación lineal estilo numpy
    n = len(success_durations)
    rank = 0.95 * (n - 1)
    lower_idx = int(rank)
    upper_idx = min(lower_idx + 1, n - 1)
    weight = rank - lower_idx
    return int(success_durations[lower_idx] * (1 - weight) + success_durations[upper_idx] * weight)
```

---

## Lógica de `is_bootstrap_mode`

```python
def is_bootstrap_mode(runs: list[RunRecord]) -> bool:
    """
    True si hay menos de BOOTSTRAP_MIN_RUNS (14) runs con status SUCCESS.
    
    Invariantes:
    - len(success_runs) < 14 → True (PBT-03)
    - len(success_runs) >= 14 → False
    """
    success_count = sum(1 for r in runs if r.status == "success")
    return success_count < BOOTSTRAP_MIN_RUNS
```

---

## Lógica de `compute_traffic_light`

```python
def compute_traffic_light(
    current_ms: int,
    p95_ms: int,
    bootstrap: bool,
) -> TrafficLight:
    """
    Reglas:
    - bootstrap=True → GREEN (BR-U2-01, PBT-07)
    - current_ms > p95_ms * RED_THRESHOLD → RED (PBT-08)
    - current_ms > p95_ms * YELLOW_THRESHOLD → YELLOW
    - otherwise → GREEN
    """
    if bootstrap:
        return TrafficLight.GREEN
    if p95_ms == 0:  # sin baseline aún pero no en bootstrap (caso raro: 14 fallidos + 0 success)
        return TrafficLight.GREEN
    if current_ms > p95_ms * RED_THRESHOLD:
        return TrafficLight.RED
    if current_ms > p95_ms * YELLOW_THRESHOLD:
        return TrafficLight.YELLOW
    return TrafficLight.GREEN
```

---

## InMemoryBaselineStore (impl MVP)

```python
class InMemoryBaselineStore:
    def __init__(self) -> None:
        # Clave: (environment_id, profile_name, flow_name)
        self._runs: dict[tuple[str, str, str], list[RunRecord]] = defaultdict(list)
        self._index_by_id: dict[str, RunRecord] = {}
    
    def save_run(self, run: RunRecord) -> None:
        key = (run.environment_id, run.profile_name, run.flow_name)
        self._runs[key].append(run)
        self._index_by_id[run.run_id] = run
    
    def get_last_n_runs(
        self,
        environment_id: str,
        profile: str,
        flow: str,
        n: int,
        status: str | None = None,
    ) -> list[RunRecord]:
        key = (environment_id, profile, flow)
        runs = self._runs.get(key, [])
        if status:
            runs = [r for r in runs if r.status == status]
        return runs[-n:]  # últimos n
    
    def get_run(self, run_id: str) -> RunRecord | None:
        return self._index_by_id.get(run_id)
```

**Cambio vs versión anterior:** clave compuesta incluye `environment_id`. Mismo profile+flow en sandbox y staging son baselines independientes.

---

## Migración futura a DynamoDB

Cuando se haga, será una clase `DynamoDBBaselineStore` que implementa el mismo Protocol:

```python
class DynamoDBBaselineStore:
    def __init__(self, table_name: str) -> None:
        self._table = boto3.resource("dynamodb").Table(table_name)
    
    def save_run(self, run: RunRecord) -> None: ...
    def get_last_n_runs(...) -> list[RunRecord]: ...
    def get_run(self, run_id: str) -> RunRecord | None: ...
```

**Lookup eficiente:** GSI `by-env-profile-flow-and-date` con PK `{env}#{profile}#{flow}` y SK `created_at`. Query directo de los últimos 10 sin scan.

**MVP:** queda InMemory. Migración a DynamoDB en sprint 3+ cuando se quiera persistencia entre reinicios del task ECS.

---

## Criterio de completitud (Definition of Done)

- [ ] Tests pasan (ejemplos + PBT con hypothesis).
- [ ] `is_bootstrap_mode([r1, ..., r13])` → True; `is_bootstrap_mode([r1, ..., r14])` → False (14 success).
- [ ] `compute_traffic_light` con `bootstrap=True` nunca retorna YELLOW (PBT-07).
- [ ] `compute_traffic_light` con `current > p95*1.5` siempre retorna RED (PBT-08).
- [ ] `calculate_p95` cumple `min <= result <= max` para cualquier lista no vacía (PBT-02).
- [ ] `InMemoryBaselineStore.save_run` + `get_run` round-trip (PBT-09).
- [ ] Tests para baseline por ambiente (sandbox no contamina staging).
- [ ] H2.1–H2.5 AC satisfechos.
