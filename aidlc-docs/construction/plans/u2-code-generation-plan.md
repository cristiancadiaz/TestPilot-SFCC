# U2 Baseline Manager — Code Generation Plan

## Unit Context
- **Tipo**: Greenfield (todos los archivos nuevos)
- **Stories cubiertas**: RF-09, RNF-09

## Steps

### Step 1: Crear `src/baseline/__init__.py` [x]
- Export: `BaselineStore`, `InMemoryBaselineStore`, `calculate_p95`, `is_bootstrap_mode`, `compute_traffic_light`

### Step 2: Crear `src/baseline/baseline_manager.py` [x]
- `YELLOW_THRESHOLD = 1.2`, `RED_THRESHOLD = 1.5`, `BOOTSTRAP_MIN_RUNS = 14`, `BASELINE_WINDOW = 10`
- `BaselineStore(Protocol)`
- `InMemoryBaselineStore` — dict[(profile, flow)] → list[RunRecord]
- `calculate_p95(runs: list[RunRecord]) -> int`
- `is_bootstrap_mode(runs: list[RunRecord]) -> bool`
- `compute_traffic_light(current_ms: int, p95_ms: int, bootstrap: bool) -> TrafficLight`

### Step 3: Crear `tests/test_baseline_manager.py` [x]
- Tests de ejemplo: bootstrap con 5 runs, p95 con 10 runs conocidos, semáforo verde/amarillo/rojo/bootstrap

### Step 4: Crear `tests/test_baseline_pbt.py` [x]
- `@given` tests con hypothesis para PBT-02, PBT-03, PBT-07, PBT-08, PBT-09

### Step 5: Crear `aidlc-docs/construction/u2/code/code-summary.md` [x]

## Traceability
| RF/RNF | Step |
|--------|------|
| RF-09 (BaselineManager) | Steps 1–2 |
| RNF-09 (PBT hypothesis) | Step 4 |
