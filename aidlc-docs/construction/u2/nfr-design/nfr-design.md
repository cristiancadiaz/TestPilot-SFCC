# NFR Design — U2 Baseline Manager (2026-05-28)

Patrones concretos para satisfacer los NFR-U2-* y BR-U2-* de la unidad de baseline.

---

## Patrón 1: Protocol + Strategy para BaselineStore swappable (BR-U2-08)

Resuelve la migración futura de `InMemoryBaselineStore` → `DynamoDBBaselineStore` sin tocar U3 ni U4. El contrato entre unidades es el Protocol — no la implementación.

```python
# src/baseline/baseline_manager.py
from typing import Protocol, Literal
from datetime import datetime
from src.models import RunRecord

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
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[RunRecord], int]: ...
```

**Por qué Protocol y no ABC:**
- `Protocol` es structural subtyping — `DynamoDBBaselineStore` cumple el contrato sin heredar ni importar nada de U2.
- `mypy --strict` verifica la conformidad en tiempo de análisis estático, no en runtime.
- Sin acoplamiento de imports entre la implementación concreta y el contrato.

**Inyección en U3 y U4:**
```python
# U4 construye el store y lo inyecta en U3
store: BaselineStore = InMemoryBaselineStore()   # MVP
# store: BaselineStore = DynamoDBBaselineStore(TABLE_NAME)  # sprint 3+

report = generate_report(
    profile_results=results,
    baseline_store=store,
    ...
)
```

**Trade-off:** `Protocol` no fuerza la implementación en runtime (solo en type checking). Un desarrollador puede pasar un objeto que no cumple el contrato y el error se detectará solo al llamar el método. Aceptable para MVP con mypy en CI.

---

## Patrón 2: Clave compuesta por ambiente para aislamiento de baselines (BR-U2-05, NFR-U2-R1)

Impide que el baseline de `sandbox` (lento, recursos compartidos) contamine el de `staging` (más rápido, closer to production).

```python
class InMemoryBaselineStore:
    def __init__(self) -> None:
        # Clave: (environment_id, profile_name, flow_name)
        # Tres dimensiones para aislamiento completo
        self._runs: dict[tuple[str, str, str], list[RunRecord]] = defaultdict(list)
        self._index_by_id: dict[str, RunRecord] = {}
        self._all_runs: list[RunRecord] = []

    def save_run(self, run: RunRecord) -> None:
        key = (run.environment_id, run.profile_name, run.flow_name)
        self._runs[key].append(run)
        self._index_by_id[run.run_id] = run
        self._all_runs.append(run)

    def get_last_n_runs(
        self,
        environment_id: str,
        profile: str,
        flow: str,
        n: int,
        status: Literal["success", "failed", "error"] | None = None,
    ) -> list[RunRecord]:
        key = (environment_id, profile, flow)
        runs = self._runs.get(key, [])
        if status is not None:
            runs = [r for r in runs if r.status == status]
        return runs[-n:]  # ventana deslizante: últimos N (más recientes al final)
```

**Por qué `runs[-n:]` y no ordenar por `created_at`:**
- `InMemoryStore` inserta en orden cronológico (append). `[-n:]` es O(1) — sin copia innecesaria.
- Preserva el orden sin sort adicional (BR-U2-06).

**Verificación de aislamiento (test):**
```python
def test_baseline_isolated_by_environment():
    store = InMemoryBaselineStore()
    sandbox_run = RunRecord(environment_id="sandbox", profile_name="mobile-co",
                            flow_name="checkout-full", duration_ms=8000,
                            status="success", run_id="r1", created_at=datetime.now(UTC))
    staging_run = RunRecord(environment_id="staging", profile_name="mobile-co",
                            flow_name="checkout-full", duration_ms=3000,
                            status="success", run_id="r2", created_at=datetime.now(UTC))
    store.save_run(sandbox_run)
    store.save_run(staging_run)

    sandbox_results = store.get_last_n_runs("sandbox", "mobile-co", "checkout-full", 10, "success")
    staging_results = store.get_last_n_runs("staging", "mobile-co", "checkout-full", 10, "success")

    assert len(sandbox_results) == 1 and sandbox_results[0].duration_ms == 8000
    assert len(staging_results) == 1 and staging_results[0].duration_ms == 3000
```

---

## Patrón 3: calculate_p95 con interpolación lineal (NFR-U2-P1, PBT-02)

Implementación pura sin dependencia de `numpy` — stdlib Python únicamente.

```python
def calculate_p95(runs: list[RunRecord]) -> int:
    """
    Percentil 95 de duration_ms de runs SUCCESS.
    Interpolación lineal estilo numpy.percentile(arr, 95, interpolation='linear').

    Invariantes PBT-02:
    - calculate_p95([]) == 0
    - Para lista no vacía: min(d) <= resultado <= max(d)
    - calculate_p95([r]) == r.duration_ms
    - Monotonicidad: si todos los valores aumentan, p95 no disminuye
    """
    success_durations = sorted(
        r.duration_ms for r in runs if r.status == "success"
    )
    if not success_durations:
        return 0
    n = len(success_durations)
    if n == 1:
        return success_durations[0]
    rank = 0.95 * (n - 1)          # posición real (puede ser decimal)
    lower = int(rank)               # índice inferior
    upper = min(lower + 1, n - 1)  # índice superior (clampado)
    weight = rank - lower           # fracción para interpolación
    return int(
        success_durations[lower] * (1 - weight)
        + success_durations[upper] * weight
    )
```

**Por qué interpolación lineal y no percentil simple:**
- Con 10 muestras (BASELINE_WINDOW), el percentil sin interpolación puede saltar ±10% entre runs consecutivos. La interpolación suaviza.
- Consistente con el comportamiento de `numpy.percentile(arr, 95)` — facilita validar contra herramientas externas.

**Sin numpy:** `numpy` añade ~50 MB a la imagen Docker y un import lento en cold start. Para una lista de máximo 10 elementos, la interpolación manual es < 1 μs.

---

## Patrón 4: compute_traffic_light con bootstrap guard explícito (BR-U2-01, BR-U2-03, PBT-07, PBT-08)

El guard de bootstrap es la primera condición — no se puede eludir por ninguna combinación de `current_ms` / `p95_ms`.

```python
BOOTSTRAP_MIN_RUNS: Final[int] = 14
BASELINE_WINDOW:    Final[int] = 10
YELLOW_THRESHOLD:   Final[float] = 1.2
RED_THRESHOLD:      Final[float] = 1.5

def compute_traffic_light(
    current_ms: int,
    p95_ms: int,
    bootstrap: bool,
) -> TrafficLight:
    """
    Reglas en orden de prioridad estricto:
    1. bootstrap=True → GREEN (nunca YELLOW — PBT-07)
    2. p95_ms == 0    → GREEN (sin historia — caso degenerado BR-U2-04)
    3. current > p95 * RED_THRESHOLD    → RED   (PBT-08)
    4. current > p95 * YELLOW_THRESHOLD → YELLOW
    5. otherwise                        → GREEN
    """
    if bootstrap:
        return TrafficLight.GREEN
    if p95_ms == 0:
        return TrafficLight.GREEN
    if current_ms > p95_ms * RED_THRESHOLD:
        return TrafficLight.RED
    if current_ms > p95_ms * YELLOW_THRESHOLD:
        return TrafficLight.YELLOW
    return TrafficLight.GREEN
```

**Por qué `Final` en las constantes:**
- `mypy --strict` verifica que nadie las reasigne fuera de la declaración.
- Comunica la intención de inmutabilidad sin añadir un enum ni una config class.

**Por qué las constantes NO son env vars:**
- Son política del producto, no configuración de deployment.
- Cambiarlas requiere un PR con evidencia estadística — no un `export YELLOW_THRESHOLD=1.1`.

---

## Patrón 5: Suite PBT con hypothesis (NFR-U2 — PBT-02, 03, 07, 08, 09 — BLOQUEANTE)

Estructura de los tests de propiedad que garantizan los invariantes matemáticos de U2.

```python
# tests/test_baseline_pbt.py
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from datetime import datetime, timezone
from src.baseline.baseline_manager import (
    calculate_p95, is_bootstrap_mode, compute_traffic_light,
    InMemoryBaselineStore, BOOTSTRAP_MIN_RUNS, RED_THRESHOLD, YELLOW_THRESHOLD,
)
from src.models import RunRecord, TrafficLight

# ── Estrategia de RunRecord para hypothesis ───────────────────────────────────
run_strategy = st.builds(
    RunRecord,
    run_id=st.uuids().map(str),
    environment_id=st.sampled_from(["sandbox", "development", "staging"]),
    profile_name=st.sampled_from(["mobile-co", "desktop-co", "desktop-ec"]),
    flow_name=st.sampled_from(["checkout-full", "checkout-card-declined"]),
    duration_ms=st.integers(min_value=1000, max_value=120_000),
    status=st.sampled_from(["success", "failed", "error"]),
    created_at=st.just(datetime.now(timezone.utc)),
)
success_run_strategy = run_strategy.filter(lambda r: r.status == "success")


# ── PBT-02: calculate_p95 — bounds ───────────────────────────────────────────
@given(runs=st.lists(success_run_strategy, min_size=1, max_size=50))
@settings(max_examples=500)
def test_p95_within_min_max(runs):
    result = calculate_p95(runs)
    durations = [r.duration_ms for r in runs]
    assert min(durations) <= result <= max(durations)


@given(run=success_run_strategy)
def test_p95_single_element_equals_value(run):
    assert calculate_p95([run]) == run.duration_ms


# ── PBT-03: is_bootstrap_mode — umbral 14 ────────────────────────────────────
@given(runs=st.lists(success_run_strategy, min_size=0, max_size=13))
def test_bootstrap_true_below_threshold(runs):
    assert is_bootstrap_mode(runs) is True


@given(runs=st.lists(success_run_strategy, min_size=14, max_size=30))
def test_bootstrap_false_at_or_above_threshold(runs):
    assert is_bootstrap_mode(runs) is False


@given(
    success_runs=st.lists(success_run_strategy, min_size=14, max_size=20),
    failed_runs=st.lists(
        run_strategy.filter(lambda r: r.status != "success"), min_size=0, max_size=10
    ),
)
def test_bootstrap_failed_runs_dont_count(success_runs, failed_runs):
    all_runs = success_runs + failed_runs
    assert is_bootstrap_mode(all_runs) is False


# ── PBT-07: compute_traffic_light — bootstrap nunca YELLOW ───────────────────
@given(
    current_ms=st.integers(min_value=0, max_value=200_000),
    p95_ms=st.integers(min_value=0, max_value=200_000),
)
def test_bootstrap_never_yellow(current_ms, p95_ms):
    result = compute_traffic_light(current_ms, p95_ms, bootstrap=True)
    assert result != TrafficLight.YELLOW


# ── PBT-08: compute_traffic_light — RED cuando current >> p95 ────────────────
@given(
    p95_ms=st.integers(min_value=1000, max_value=100_000),
    multiplier=st.floats(min_value=RED_THRESHOLD + 0.01, max_value=5.0),
)
def test_red_when_current_exceeds_threshold(p95_ms, multiplier):
    current_ms = int(p95_ms * multiplier)
    result = compute_traffic_light(current_ms, p95_ms, bootstrap=False)
    assert result == TrafficLight.RED


# ── PBT-09: InMemoryBaselineStore — round-trip ────────────────────────────────
@given(run=run_strategy)
def test_store_round_trip(run):
    store = InMemoryBaselineStore()
    store.save_run(run)
    retrieved = store.get_run(run.run_id)
    assert retrieved == run


@given(run=success_run_strategy)
def test_store_get_last_returns_saved(run):
    store = InMemoryBaselineStore()
    store.save_run(run)
    results = store.get_last_n_runs(
        run.environment_id, run.profile_name, run.flow_name, 1, "success"
    )
    assert len(results) == 1
    assert results[0] == run
```

**Por qué `st.builds` sobre `st.fixed_dictionaries`:**
- Hypothesis infiere los tipos desde los type hints de `RunRecord` (Pydantic).
- `st.builds` genera ejemplos más variados que diccionarios manuales.
- Falla explícitamente si `RunRecord` cambia su firma — el test actúa como contrato de integración.

---

## Patrón 6: Diseño del GSI DynamoDB para migración futura (BR-U2-08, NFR-U2-P2)

No se implementa en MVP, pero el diseño es parte del NFR Design para que la migración no requiera rediseño de U2.

```
Tabla DynamoDB: testpilot-baselines

PK  →  run_id          (UUID — para get_run)
SK  →  created_at (ISO8601)

GSI: by-env-profile-flow
  PK  →  {environment_id}#{profile_name}#{flow_name}
  SK  →  created_at (ISO8601)
  Proyección: ALL

Query para get_last_n_runs("staging", "mobile-co", "checkout-full", 10, "success"):
  KeyConditionExpression: PK = "staging#mobile-co#checkout-full"
  FilterExpression: #status = :success
  ScanIndexForward: False   (orden descendente → más recientes primero)
  Limit: 10
```

**Por qué GSI y no scan:**
- `Limit: 10` sobre un GSI con SK ordenado es O(log N) — independiente del total de runs.
- Un `scan` con `FilterExpression` costaría O(N) y consumiría RCUs innecesarias.

**ADR implícito:** se elige DynamoDB (no RDS) porque:
- Sin esquema fijo — `RunRecord` puede evolucionar sin migraciones.
- TTL nativo — runs > 90 días se borran solos (RNF-09 cost discipline).
- Serverless pay-per-use — MVP con < 10 runs/día cuesta < $1/mes.

**Cuando hacer la migración:**
- Trigger: se necesita persistencia entre reinicios del task ECS (sprint 3+).
- Acción: crear `DynamoDBBaselineStore` que implemente el mismo `BaselineStore` Protocol.
- U3 y U4 no cambian — solo el punto de inyección en U4.

---

## Resumen patrones → NFRs / BRs

| Patrón | NFRs / BRs satisfechos |
|---|---|
| 1. Protocol + Strategy | BR-U2-08, NFR-U2-R1, NFR-U2-R2 |
| 2. Clave compuesta por ambiente | BR-U2-05, BR-U2-06, NFR-U2-R1 |
| 3. calculate_p95 con interpolación | NFR-U2-P1, PBT-02 |
| 4. compute_traffic_light con bootstrap guard | BR-U2-01, BR-U2-03, BR-U2-04, PBT-07, PBT-08 |
| 5. Suite PBT hypothesis | PBT-02, PBT-03, PBT-07, PBT-08, PBT-09 — BLOQUEANTE |
| 6. GSI DynamoDB (diseño futuro) | BR-U2-08, NFR-U2-P2, NFR-U2-P3 |
