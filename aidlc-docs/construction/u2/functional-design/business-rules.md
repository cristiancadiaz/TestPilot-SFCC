# Business Rules — U2 Baseline Manager (actualizado 2026-05-24)

## BR-U2-01: Bootstrap — sin alertas amarillas con < 14 runs success
`is_bootstrap_mode(runs)` retorna `True` si la cantidad de runs con `status="success"` es menor a `BOOTSTRAP_MIN_RUNS=14`.

`compute_traffic_light` con `bootstrap=True` nunca retorna `TrafficLight.YELLOW`. Test PBT-07 garantiza esto para cualquier combinación de `current_ms` y `p95_ms`.

**Razón:** principio P4 (semáforo honesto) — durante la fase de aprendizaje no hay base estadística para emitir alertas.

---

## BR-U2-02: p95 sobre las últimas 10 ejecuciones success
`calculate_p95` recibe las últimas 10 ejecuciones `success` del tuple `(environment_id, profile, flow)`. El caller (U3 reporter) es responsable de pedirle al store `get_last_n_runs(environment_id, profile, flow, n=10, status="success")`.

**Por qué solo success:** los runs fallidos no representan el tiempo "normal" — un run fallido puede haber abortado en el paso 3 (rápido) o en el paso 10 (lento). Mezclarlos contamina el p95.

---

## BR-U2-03: Umbrales del semáforo
```
bootstrap=True              → GREEN siempre
current_ms > p95 * 1.5      → RED
current_ms > p95 * 1.2      → YELLOW
otherwise                   → GREEN
```

Factores son constantes del módulo:
- `YELLOW_THRESHOLD = 1.2`
- `RED_THRESHOLD = 1.5`

**Razón de elegir 1.2 / 1.5:** la literatura de SRE (Google, Datadog) usa estos rangos como defaults para p95. Cambiar requiere decisión documentada del PO + 2 semanas de observación.

---

## BR-U2-04: p95 de lista vacía
`calculate_p95([])` retorna `0` (sin historial, no hay baseline). El caller debe detectar `runs_count == 0` y marcar `bootstrap_mode=True`.

`compute_traffic_light` con `p95_ms=0` y `bootstrap=False` (caso raro: 14 runs todos fallidos + 0 success — escenario degenerado) retorna `GREEN` para no bloquear pero el reporter debe loggear warning.

---

## BR-U2-05: Baseline por ambiente — clave compuesta (NUEVO)
La clave del baseline es `(environment_id, profile_name, flow_name)`. No mezclar baselines de ambientes distintos.

**Razón:** sandbox y staging tienen perfiles de performance muy diferentes (sandbox suele compartir recursos). Mezclar genera falsos positivos en staging (alertas por lentitud aparente) y falsos negativos en sandbox (regresiones reales enmascaradas por su lentitud histórica).

---

## BR-U2-06: Orden cronológico en get_last_n_runs
`get_last_n_runs` retorna registros en orden cronológico (más antiguo primero, más reciente al final). El cálculo de p95 no depende del orden, pero el reporter puede mostrarlos en orden.

---

## BR-U2-07: Solo runs SUCCESS en el baseline
Solo los `RunRecord` con `status == "success"` cuentan en `calculate_p95` y en `is_bootstrap_mode`. Los runs `failed` y `error` se persisten en el store (para historial), pero NO se cuentan para el cálculo.

**Razón:** ver BR-U2-02. Esto implica que `is_bootstrap_mode` puede retornar True después de 20 runs si solo 13 fueron success — protege la honestidad del semáforo.

---

## BR-U2-08: BaselineStore es Protocol-based (Strategy pattern)
La interfaz `BaselineStore` es un Protocol de Python. Cualquier implementación que cumpla la signature es válida. MVP: `InMemoryBaselineStore`. Futuro: `DynamoDBBaselineStore`.

**Cambio entre impls debe ser transparente para U3 y U4.**

---

## BR-U2-09: Funciones de cálculo SON puras
`calculate_p95`, `is_bootstrap_mode`, `compute_traffic_light` no tienen side effects, no hacen IO, no dependen de tiempo wall-clock, no usan globals. Esto las hace:
- Testeables con hypothesis sin mocks.
- Predecibles entre invocaciones (mismo input → mismo output).
- Reutilizables en otros contextos (CLI, batch reports).

**Verificación:** tests PBT cubren todas las propiedades enumeradas en `nfr-requirements.md`.

---

## BR-U2-10: BaselineStore.save_run persiste también failed/error
El store guarda TODOS los runs, no solo success. Esto permite:
- Historial completo para el dashboard P5.
- Tendencias de tasa de fallo por ambiente.
- Debug de runs específicos por `run_id`.

El filtrado por `status="success"` ocurre en `get_last_n_runs(status="success")`, no en `save_run`.

---

## Trazabilidad

| BR | Historia | Notas |
|---|---|---|
| BR-U2-01, BR-U2-05, BR-U2-07 | H2.2 (bootstrap honesto) | Principio P4 |
| BR-U2-02, BR-U2-03 | H2.1 (alerta de regresión) | — |
| BR-U2-08, BR-U2-09 | H2.5 (baseline swappable) | Habilita migración a DynamoDB |
| BR-U2-10 | H2.3 (consulta de histórico MVP) | — |
