# U2 Baseline Manager — Code Generation Plan

> **Reconciliado a specs v2 el 2026-06-06 (clave compuesta `(environment_id, profile, flow)` + gate-only C11).**
> Reemplaza el plan anterior que usaba clave `(profile, flow)` y omitia el guard de modo exploratorio.

---

## Unit Context

| Campo | Valor |
|---|---|
| **Tipo** | Greenfield — todos los archivos son nuevos |
| **Sprint** | 1 (paralelo con U1) |
| **Dependencias** | U0 (src/models.py: RunRecord, TrafficLight, Mode, EnvironmentId, ProfileId, FlowName) |
| **Gate de salida** | Gate 2 (build-sequence.md): PBT pasan, store separa por ambiente, bootstrap nunca YELLOW |
| **Profundidad** | Standard |

### Requisitos cubiertos

| ID | Descripcion |
|---|---|
| RF-09 | Baseline Manager: calculo p95, bootstrap silencioso, semaforo determinista |
| RNF-09 | Property-Based Testing con hypothesis (PBT-02, PBT-03, PBT-07, PBT-08, PBT-09) |
| C11 | Runs exploratorios NUNCA entran al baseline ni cuentan para bootstrap |
| Invariante #4 | Sin alertas amarillas en los primeros 14 runs exitosos por combinacion |
| Invariante #5 | p95 sobre los ultimos 10 runs (no porcentaje fijo) |

### Archivos objetivo

```
src/baseline/__init__.py
src/baseline/baseline_manager.py
tests/test_baseline_manager.py
tests/test_baseline_pbt.py
aidlc-docs/construction/u2/code/code-summary.md
```

---

## Invariantes de diseno (leer antes de implementar)

**Clave compuesta `(environment_id, profile, flow)`**: el store separa el historial por
ambiente. Sin esta separacion, los runs de `sandbox` contaminarian el baseline de `staging`.
Esto lo exige Gate 4 de `build-sequence.md` ("Baseline consultado con environment_id —
no se mezclan ambientes") y el campo `environment_id: EnvironmentId` de `RunRecord` en
`src/models.py`.

**Solo gate-mode (C11)**: `record_run` comprueba `run.mode == "gate"` antes de almacenar.
Los runs exploratorios se ignoran silenciosamente (no lanzan excepcion, simplemente no se
persistern). Esta logica no es responsabilidad del caller — el store mismo es el guardabarrera.
`RunRecord` no tiene campo `mode`, por lo que el guard se aplica en el metodo `record_run`
de `BaselineManager` que envuelve al store; el caller en `src/baseline/` debe pasar el modo
del run. Ver Step 2 para la firma exacta.

**Bootstrap por combinacion**: cada tripleta `(environment_id, profile, flow)` arranca su
propio conteo. Un flow nuevo del catalogo comienza en bootstrap = 0 runs aunque el sistema
lleve meses en produccion (invariante #4, RF-21).

**El semaforo es determinista (P7/C10)**: `compute_traffic_light` no llama al LLM ni a
ningun otro modulo — es logica pura de comparacion de enteros.

---

## Steps

### Step 1: Crear `src/baseline/__init__.py` [ ]

**Descripcion**: modulo publico de U2. Exporta la interfaz completa para que U3 y U4
importen desde `src.baseline` sin depender de rutas internas.

**Contenido del archivo**:

```python
"""Baseline manager for TestPilot SFCC.

Public API of the src/baseline package. U3 (reporter) and U4 (API) import from
here — never from src.baseline.baseline_manager directly.

Only gate-mode runs feed the baseline (C11 / invariant #5).
The traffic light is computed deterministically (P7 / C10).
"""

from src.baseline.baseline_manager import (
    BASELINE_WINDOW,
    BOOTSTRAP_MIN_RUNS,
    RED_THRESHOLD,
    YELLOW_THRESHOLD,
    BaselineManager,
    BaselineStore,
    InMemoryBaselineStore,
    calculate_p95,
    compute_traffic_light,
    is_bootstrap_mode,
)

__all__ = [
    "BaselineStore",
    "InMemoryBaselineStore",
    "BaselineManager",
    "calculate_p95",
    "is_bootstrap_mode",
    "compute_traffic_light",
    "YELLOW_THRESHOLD",
    "RED_THRESHOLD",
    "BOOTSTRAP_MIN_RUNS",
    "BASELINE_WINDOW",
]
```

**TDD**: no hay logica propia aqui — los tests cubren el modulo importado (Steps 3 y 4).
Se verifica que el import no lanza `ImportError` en el test de humo del Step 3.

---

### Step 2: Crear `src/baseline/baseline_manager.py` [ ]

**Descripcion**: modulo central de U2. Define el Protocol, la implementacion en memoria,
las funciones puras y el `BaselineManager` que orquesta el guard gate-only.

**Contenido del archivo** (estructura completa):

```
CONSTANTES
  YELLOW_THRESHOLD: float = 1.2
  RED_THRESHOLD: float = 1.5
  BOOTSTRAP_MIN_RUNS: int = 14   # invariante #4: sin amarillos hasta 14 runs exitosos
  BASELINE_WINDOW: int = 10      # invariante #5: p95 sobre los ultimos 10 runs

TIPO
  _StoreKey = tuple[EnvironmentId, ProfileId, FlowName]
    -- clave compuesta de 3 partes; evita mezclar baselines entre ambientes

PROTOCOL BaselineStore
  record_run(run: RunRecord) -> None
    -- persiste el run en la coleccion de la clave (env_id, profile, flow)
    -- SOLO se llama con runs gate (el guard esta en BaselineManager.save_run)
  get_runs(environment_id, profile_name, flow_name, limit) -> list[RunRecord]
    -- devuelve los ultimos `limit` runs de la clave, ordenados desc por created_at
  list_runs(environment_id, limit, offset) -> list[RunRecord]
    -- historial paginado por ambiente (para Gate 5 / RF-17)
    -- offset/limit son enteros; offset=0 devuelve los mas recientes

CLASE InMemoryBaselineStore (implementa BaselineStore)
  _data: dict[_StoreKey, list[RunRecord]] = {}
  record_run(run) -> None
    -- clave = (run.environment_id, run.profile_name, run.flow_name)
    -- append a _data[clave]; si no existe, crea lista vacia primero
  get_runs(environment_id, profile_name, flow_name, limit=BASELINE_WINDOW) -> list[RunRecord]
    -- ordena por created_at desc, devuelve los primeros `limit`
  list_runs(environment_id, limit=50, offset=0) -> list[RunRecord]
    -- concatena todos los runs del ambiente, ordena desc, aplica offset/limit

FUNCIONES PURAS (sin estado, sin efectos secundarios)

  calculate_p95(runs: list[RunRecord]) -> int
    -- si runs esta vacio: retorna 0
    -- extrae durations = [r.duration_ms for r in runs if r.status == "success"]
    -- si no hay runs exitosos: retorna 0
    -- ordena durations, calcula indice p95 = ceil(0.95 * len) - 1 (0-based)
    -- retorna int(durations[indice])

  is_bootstrap_mode(runs: list[RunRecord]) -> bool
    -- cuenta solo runs con status == "success"
    -- retorna True si el conteo < BOOTSTRAP_MIN_RUNS (= 14)

  compute_traffic_light(current_ms: int, p95_ms: int, bootstrap: bool) -> TrafficLight
    -- si bootstrap es True: retorna TrafficLight.GREEN (invariante #4 — sin amarillos)
    -- si p95_ms == 0: retorna TrafficLight.GREEN (sin baseline previo = no hay umbral)
    -- ratio = current_ms / p95_ms
    -- si ratio >= RED_THRESHOLD (1.5): retorna TrafficLight.RED
    -- si ratio >= YELLOW_THRESHOLD (1.2): retorna TrafficLight.YELLOW
    -- en otro caso: retorna TrafficLight.GREEN

CLASE BaselineManager
  -- orquestador: encapsula el guard gate-only para que los callers no necesiten
  -- conocer C11. Los callers (U3 reporter, U4 API) llaman a este objeto, no al store
  -- directamente.
  __init__(self, store: BaselineStore) -> None
  save_run(self, run: RunRecord, mode: Mode) -> None
    -- GUARD: si mode != "gate": retorna inmediatamente (no lanza; C11)
    -- en caso contrario: self._store.record_run(run)
  get_baseline_comparison(
      self,
      environment_id: EnvironmentId,
      profile_name: ProfileId,
      flow_name: FlowName,
      current_ms: int,
  ) -> BaselineComparison
    -- runs = self._store.get_runs(environment_id, profile_name, flow_name, BASELINE_WINDOW)
    -- p95 = calculate_p95(runs)
    -- bootstrap = is_bootstrap_mode(runs)
    -- retorna BaselineComparison(
         p95_ms=p95,
         current_ms=current_ms,
         bootstrap_mode=bootstrap,
         runs_count=len(runs),
       )
  list_runs(self, environment_id, limit, offset) -> list[RunRecord]
    -- delega a self._store.list_runs(environment_id, limit, offset)
```

**Importaciones**: `from src.models import RunRecord, TrafficLight, Mode, EnvironmentId, ProfileId, FlowName, BaselineComparison`

**TDD — RED antes de escribir una sola linea de implementacion**:
Escribir primero los tests del Step 3 que fallan, luego implementar hasta que pasen.

---

### Step 3: Crear `tests/test_baseline_manager.py` [ ]

**Descripcion**: tests de ejemplo (deterministas, sin hypothesis). Cubren los comportamientos
clave incluyendo la separacion por `environment_id` y el guard gate-only.

**Casos de test obligatorios**:

```
IMPORT SMOKE
  test_import_ok
    -- from src.baseline import BaselineManager, InMemoryBaselineStore, calculate_p95
    -- no debe lanzar ImportError

FUNCIONES PURAS
  test_calculate_p95_empty_list
    -- calculate_p95([]) == 0

  test_calculate_p95_ten_known_runs
    -- 10 runs exitosos con durations [100,200,...,1000] ms
    -- p95 index = ceil(0.95*10)-1 = 9 -> durations[9] = 1000 (sorted)
    -- calculate_p95(runs) == 1000

  test_calculate_p95_excludes_failed_runs
    -- 5 runs: 3 status=success (durations 100,200,300), 2 status=failed (duration 9999)
    -- p95 calculado solo sobre los 3 exitosos

  test_is_bootstrap_mode_fewer_than_14
    -- 5 runs exitosos -> True

  test_is_bootstrap_mode_exactly_14
    -- 14 runs exitosos -> False (bootstrap termina cuando se completa el run 14)

  test_is_bootstrap_mode_more_than_14
    -- 20 runs exitosos -> False

  test_compute_traffic_light_green
    -- current_ms=1000, p95_ms=1000, bootstrap=False -> GREEN

  test_compute_traffic_light_yellow
    -- current_ms=1250, p95_ms=1000, bootstrap=False -> YELLOW  (ratio=1.25 >= 1.2)

  test_compute_traffic_light_red
    -- current_ms=1600, p95_ms=1000, bootstrap=False -> RED  (ratio=1.6 >= 1.5)

  test_compute_traffic_light_bootstrap_always_green
    -- current_ms=9999, p95_ms=1, bootstrap=True -> GREEN
    -- (invariante #4: bootstrap nunca devuelve YELLOW ni RED)

  test_compute_traffic_light_zero_p95_is_green
    -- current_ms=5000, p95_ms=0, bootstrap=False -> GREEN

STORE — SEPARACION POR environment_id (Gate 2)
  test_store_separates_by_environment_id
    -- Fixture: store = InMemoryBaselineStore()
    -- Insertar run_sandbox: env=sandbox, profile=mobile_co, flow=checkout_full, duration=500
    -- Insertar run_staging: env=staging, profile=mobile_co, flow=checkout_full, duration=1000
    -- get_runs(sandbox, mobile_co, checkout_full) devuelve [run_sandbox] solamente
    -- get_runs(staging, mobile_co, checkout_full) devuelve [run_staging] solamente
    -- Los baselines de sandbox y staging son INDEPENDIENTES

  test_store_returns_last_n_runs
    -- Insertar 15 runs en la misma clave (env, profile, flow)
    -- get_runs(..., limit=10) devuelve exactamente 10 runs
    -- Los 10 son los mas recientes (created_at desc)

LIST_RUNS PAGINADO
  test_list_runs_pagination
    -- Insertar 5 runs en sandbox
    -- list_runs(sandbox, limit=3, offset=0) devuelve 3 runs
    -- list_runs(sandbox, limit=3, offset=3) devuelve los 2 restantes

BASELINEMANAGER — GUARD GATE-ONLY (C11)
  test_save_run_gate_mode_persists
    -- manager.save_run(run, mode="gate")
    -- get_runs devuelve 1 elemento

  test_save_run_exploratory_mode_ignored
    -- manager.save_run(run, mode="exploratory")
    -- get_runs devuelve lista vacia (el run no se persiste)

  test_save_run_exploratory_does_not_raise
    -- manager.save_run(run, mode="exploratory") no lanza ninguna excepcion

BASELINEMANAGER — get_baseline_comparison
  test_get_baseline_comparison_bootstrap
    -- 5 runs gate previos -> bootstrap_mode=True en el BaselineComparison retornado

  test_get_baseline_comparison_full
    -- 10 runs gate previos, durations conocidos
    -- p95_ms == valor esperado, bootstrap_mode=False, runs_count=10
```

---

### Step 4: Crear `tests/test_baseline_pbt.py` [ ]

**Descripcion**: property-based tests con `hypothesis`. Estos tests son BLOQUEANTES para Gate 2.

**Estrategias de hypothesis**:

```python
# Estrategia reutilizable para RunRecord gate exitoso
def gate_run_strategy(env_id, profile, flow):
    return builds(
        RunRecord,
        run_id=uuids().map(str),
        environment_id=just(env_id),
        profile_name=just(profile),
        flow_name=just(flow),
        duration_ms=integers(min_value=0, max_value=600_000),
        status=just("success"),
        created_at=datetimes(),
    )
```

**Tests PBT obligatorios (todos bloqueantes para Gate 2)**:

```
PBT-02: Round-trip BaselineComparison
  @given(lista de RunRecord exitosos gate, current_ms entero)
  Propiedad: BaselineComparison se puede serializar a dict y reconstruirse con
             BaselineComparison(**data) sin perdida de campos
  -- Cubre RF-09 integridad del modelo de comparacion

PBT-03: calculate_p95 es invariante al orden
  @given(lista no vacia de RunRecord exitosos)
  Propiedad: calculate_p95(runs) == calculate_p95(shuffled(runs))
  -- El percentil no depende del orden de insercion

PBT-07: calculate_p95 esta acotado por [min, max] de las durations exitosas
  @given(lista de RunRecord con status mix)
  Propiedad: si hay al menos un run exitoso:
             min(d for success runs) <= calculate_p95(runs) <= max(d for success runs)
  -- Propiedad fundamental de cualquier percentil

PBT-08: compute_traffic_light es determinista para el mismo input
  @given(current_ms: int>=0, p95_ms: int>=0, bootstrap: bool)
  Propiedad: compute_traffic_light(c, p, b) == compute_traffic_light(c, p, b)
  -- Misma llamada, mismo resultado; no hay estado oculto ni aleatoriedad

PBT-09: bootstrap=True NUNCA retorna YELLOW ni RED
  @given(current_ms: int>=0, p95_ms: int>=1)
  Propiedad: compute_traffic_light(current_ms, p95_ms, bootstrap=True)
             not in {TrafficLight.YELLOW, TrafficLight.RED}
  -- Invariante #4 (bootstrap silence): reforzado por PBT, no solo por ejemplo
  -- Este test es el mas critico para Gate 2

PBT-EXTRA (recomendado, no bloqueante): separacion por environment_id
  @given(runs_sandbox: list[RunRecord] con env=sandbox,
         runs_staging: list[RunRecord] con env=staging)
  Propiedad: despues de insertar ambos grupos en el store,
             get_runs(sandbox,...) no contiene ningun run de staging y viceversa
  -- Verifica el invariante de clave compuesta con datos arbitrarios
```

**Configuracion hypothesis recomendada**:

```python
settings(max_examples=200, deadline=None)
# deadline=None porque los tests de store pueden ser lentos con listas grandes
```

---

### Step 5: Crear `aidlc-docs/construction/u2/code/code-summary.md` [ ]

**Descripcion**: resumen de la implementacion completada de U2. Se crea DESPUES de que los
Steps 1-4 esten completos y Gate 2 verificado.

**Estructura esperada del resumen**:

- Archivos creados y proposito de cada uno
- Decisiones de implementacion tomadas (clave compuesta, guard gate-only, funcion pura vs metodo)
- Resultados de Gate 2: tests PBT pasados, store separacion por ambiente verificada
- Notas de trazabilidad (RF-09, RNF-09, C11, invariantes #4 y #5)
- Cualquier desvio del plan y su justificacion

---

## Traceability

| Requisito | Steps que lo implementan | Criterio de aceptacion |
|---|---|---|
| RF-09 (Baseline Manager, clave compuesta) | Steps 1, 2, 3 | `InMemoryBaselineStore` usa `(environment_id, profile, flow)` como clave; test `test_store_separates_by_environment_id` pasa |
| RF-09 (calculo p95, bootstrap, semaforo) | Steps 2, 3 | `calculate_p95`, `is_bootstrap_mode`, `compute_traffic_light` implementados y probados con casos deterministas |
| RF-09 (list_runs paginado) | Steps 2, 3 | `list_runs(environment_id, limit, offset)` implementado; `test_list_runs_pagination` pasa |
| RNF-09 (PBT hypothesis) | Step 4 | PBT-02, PBT-03, PBT-07, PBT-08, PBT-09 pasan con `uv run pytest tests/test_baseline_pbt.py` |
| C11 (exploratorio fuera del baseline) | Steps 2, 3 | `save_run(..., mode="exploratory")` no persiste; `test_save_run_exploratory_mode_ignored` y `test_save_run_exploratory_does_not_raise` pasan |
| Invariante #4 (bootstrap silence) | Steps 2, 3, 4 | `compute_traffic_light(bootstrap=True)` nunca YELLOW/RED; PBT-09 lo verifica con 200 ejemplos |
| Invariante #5 (p95 sobre ultimos 10 runs) | Steps 2, 3 | `BASELINE_WINDOW=10`; `get_runs` limita a 10 por defecto |
| Gate 2 (build-sequence.md) | Steps 3, 4 | Todos los checks del Gate 2 verificados antes de Step 5 |

---

## Checklist de Gate 2 (verificar antes de marcar U2 completa)

- [ ] `uv run pytest tests/test_baseline_manager.py` — todos los tests pasan
- [ ] `uv run pytest tests/test_baseline_pbt.py` — PBT-02, PBT-03, PBT-07, PBT-08, PBT-09 pasan
- [ ] `ruff check src/baseline/` — sin errores
- [ ] `mypy src/baseline/` — sin errores (mypy --strict)
- [ ] `InMemoryBaselineStore` separa runs por ambiente (test_store_separates_by_environment_id)
- [ ] `compute_traffic_light` con `bootstrap=True` nunca retorna YELLOW (PBT-09)
- [ ] Run exploratorio ignorado sin excepcion (test_save_run_exploratory_mode_ignored)
