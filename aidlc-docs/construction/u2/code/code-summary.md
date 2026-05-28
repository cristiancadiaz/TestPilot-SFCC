# Code Summary — U2 Baseline Manager

## Archivos creados

| Archivo | Descripción |
|---------|-------------|
| `src/baseline/__init__.py` | Exports del módulo |
| `src/baseline/baseline_manager.py` | `BaselineStore` Protocol, `InMemoryBaselineStore`, 3 funciones puras |
| `tests/test_baseline_manager.py` | 14 tests de ejemplo (p95, bootstrap, semáforo, store) |
| `tests/test_baseline_pbt.py` | 7 tests hypothesis (PBT-02, PBT-03, PBT-07, PBT-08, PBT-09) |

## Constantes clave

| Constante | Valor | Significado |
|-----------|-------|-------------|
| `BOOTSTRAP_MIN_RUNS` | 14 | Mínimo de runs success para salir de bootstrap |
| `BASELINE_WINDOW` | 10 | Ventana de runs para calcular p95 |
| `YELLOW_THRESHOLD` | 1.2 | Factor p95 para alerta amarilla |
| `RED_THRESHOLD` | 1.5 | Factor p95 para alerta roja |

## Decisiones relevantes

- `BaselineStore` es `Protocol` con `@runtime_checkable` — permite `isinstance(store, BaselineStore)` en tests
- Solo runs con `status == "success"` entran en el cálculo de p95 (falla genuina no sesga el baseline)
- `calculate_p95([])` retorna 0 — el caller detecta sin-historial por `runs_count == 0`
- `compute_traffic_light` con `p95_ms == 0` retorna GREEN (sin baseline = sin alerta)
