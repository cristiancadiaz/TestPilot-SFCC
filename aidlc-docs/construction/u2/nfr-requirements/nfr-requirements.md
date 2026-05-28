# NFR Requirements — U2 Baseline Manager (actualizado 2026-05-24)

## Performance

### NFR-U2-P1: Cálculo de p95 sub-milisegundo
`calculate_p95(runs_de_10)` debe ejecutarse en **< 1 ms** en hardware típico. Es Python puro sobre lista de 10 elementos — trivial.

### NFR-U2-P2: get_last_n_runs eficiente
Con InMemoryBaselineStore: O(N) sobre lista del tuple key — aceptable para N < 1000 runs por tuple en MVP. Con DynamoDB (post-MVP): O(log N) via GSI con SK ordenado por fecha — query directo.

### NFR-U2-P3: list_runs paginado
`list_runs(page_size=25)` retorna 25 items + count total. Sin scroll infinito en MVP — paginación explícita.

---

## PBT (Property-Based Testing con hypothesis) — BLOQUEANTE

### PBT-02: calculate_p95 — propiedades matemáticas
- Para cualquier lista no vacía de RunRecord success: `min(durations) <= p95 <= max(durations)`.
- Para lista de 1 elemento: `p95 == duration_ms`.
- Monotonicidad: `calculate_p95(runs_a) <= calculate_p95(runs_b)` si cada `r_a.duration_ms <= r_b.duration_ms`.

### PBT-03: is_bootstrap_mode — propiedad de umbral
- Para cualquier lista con `< 14` runs success: `is_bootstrap_mode = True`.
- Para cualquier lista con `>= 14` runs success: `is_bootstrap_mode = False`.
- Idempotente: `is_bootstrap_mode(runs)` == `is_bootstrap_mode(runs + runs_failed)` (los failed no cuentan).

### PBT-07: compute_traffic_light — bootstrap nunca YELLOW
Para cualquier combinación de `current_ms`, `p95_ms` con `bootstrap=True`: resultado != YELLOW.

### PBT-08: compute_traffic_light — RED cuando current >> p95
Para cualquier `current_ms > p95_ms * 1.5` con `bootstrap=False` y `p95_ms > 0`: resultado == RED.

### PBT-09: InMemoryBaselineStore — round-trip
- Para cualquier RunRecord r: `save_run(r)` → `get_run(r.run_id)` retorna `r` (igualdad estructural).
- `get_last_n_runs(env, profile, flow, 1)` después de `save_run(r)` con campos coincidentes retorna `[r]`.

### PBT bonus: aislamiento por ambiente
Para cualquier `r_sandbox` y `r_staging` con mismo `profile`/`flow`: `get_last_n_runs("sandbox", profile, flow)` retorna solo `r_sandbox`, no `r_staging`.

---

## Reliability

### NFR-U2-R1: Determinismo
Mismo input siempre → mismo output. Las funciones puras (`calculate_p95`, `is_bootstrap_mode`, `compute_traffic_light`) no dependen de tiempo wall-clock ni randomness.

### NFR-U2-R2: Sin estado global
Las funciones no escriben a globals ni leen variables módulo mutables (excepto las constantes que son frozen tras carga).

---

## Security

### NFR-U2-S1: SECURITY-10 — Sin logs de PII
`RunRecord` no contiene email del shopper ni credenciales. El `run_id` es UUID — no es PII. Loggear `run_id`, `environment_id`, `duration_ms`, `traffic_light` está OK.

### NFR-U2-S2: SECURITY-04 — Sin SQL injection
MVP: InMemory, no aplica. Post-MVP DynamoDB: usar boto3 con parámetros estructurados (no `query` raw) — DynamoDB no es SQL, pero el principio de no concatenar input controlado por usuario en la query expression aplica.

---

## Aplicabilidad Security Baseline a U2

| Regla | Aplica | Implementación |
|---|---|---|
| SECURITY-01 | N/A | Sin secrets en U2 |
| SECURITY-02 | N/A | — |
| SECURITY-03 | ✅ | Pydantic valida RunRecord en U0 |
| SECURITY-04 | Parcial | NFR-U2-S2 (relevante en migración) |
| SECURITY-05 | N/A | U4 |
| SECURITY-06 | N/A | — |
| SECURITY-07 | N/A | — |
| SECURITY-08 | ✅ | Sin deps nuevas (hereda de U0) |
| SECURITY-09 | N/A | U4 |
| SECURITY-10 | ✅ | NFR-U2-S1 |
| SECURITY-11 | N/A | — |
| SECURITY-12 | N/A | — |
| SECURITY-13 | N/A | — |
| SECURITY-14 | N/A | — |
| SECURITY-15 | N/A | U4 |

**Resumen U2:** 3/15 aplican. 12/15 son N/A — U2 es lógica pura, sin auth, sin IO, sin infra propia.

---

## Aplicabilidad PBT (resumen)

| Regla | Estado |
|---|---|
| PBT-02 | ✅ BLOQUEANTE |
| PBT-03 | ✅ BLOQUEANTE |
| PBT-07 | ✅ BLOQUEANTE |
| PBT-08 | ✅ BLOQUEANTE |
| PBT-09 | ✅ BLOQUEANTE |

**U2 es la unidad con más cobertura PBT** del proyecto — su naturaleza puramente algorítmica lo justifica.
