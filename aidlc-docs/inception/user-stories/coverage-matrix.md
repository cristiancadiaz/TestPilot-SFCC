# MoSCoW Coverage Matrix — TestPilot SFCC (actualizado 2026-06-03)

**Fuente**: PRD sección 8 (MoSCoW, incl. M20–M23 de la realineación) cruzada con `user-stories.md` iteración 3

**Cambio mayor 2026-06-03 (realineación de alcance):** se agregan M20–M23 (flows de recorrido, documento de auditoría, captura de red, ventana NL) cubiertos por las historias nuevas H5.5, H6.x–H9.x. J4 des-aplazado parcialmente (D14). M5 translator promovido a path principal de UX (D18). M9 refinado a evidencia dirigida por hallazgos (D16). Con **alcance fijo**, "aplazado" se lee como **ola posterior, no recorte**.

**Cambio mayor 2026-05-24:** se agrega M19 Dashboard Web Interno (cubierto por H5.1–H5.4 ya existentes en user-stories.md). M13 Secrets Manager promovido de "Simplificado" a "Completo" porque se usa desde día 1 para `env_access` + `shopper`.

---

## Cobertura por MoSCoW

| MoSCoW | Descripción | Cubierto por | Estado |
|---|---|---|---|
| M1 | POST /v1/run con instrucción NL | H4.1 (D8 actualizada — payload estructurado, no NL) | Completo |
| M2 | GET /v1/runs/{run_id} + /v1/runs/latest + /v1/runs/{id}/status + /v1/runs (lista) | H4.2, H4.3, H5.3, H5.4 | Completo (expandido para soportar dashboard) |
| M3 | 3 perfiles (`mobile_co`, `desktop_co`, `desktop_ec`) | H1.1 | Completo |
| M4 | 2 flujos (`checkout_full`, `checkout_card_declined`) — 10 pasos cada uno | H1.2, H1.3 | Completo |
| M5 | LLM traduce NL → config + validación schema | **H9.1, H9.2** (translator promovido a path principal de UX — D18; ver M23) | **Completo en ola NL** (era "disponible no principal") |
| M6 | Payment method de prueba + email `@testpilot.internal` | H1.2 (AC1, AC2) | Completo |
| M7 | Reporte dual JSON + Markdown | H3.1, H3.2 | Completo |
| M8 | Semáforo 3 estados (verde/amarillo/rojo) | H2.1, H2.2 | Completo |
| M9 | Screenshots: fallo + paso final (ADR-002) + evidencia por hallazgos en modo auditoría (D16) | H1.5 (gate) + **H7.4 (auditoría)** | Completo (refinado 2026-06-03) |
| M10 | DynamoDB stub (InMemory en MVP) | H2.5 | Completo (Protocol pattern) |
| M11 | Baseline p95 sobre últimas 10 ejecuciones (por ambiente) | H2.1, H2.4 | Completo |
| M12 | Periodo de bootstrapping (14 runs sin amarillos) | H2.2 | Completo |
| **M13** | **Secrets Manager para credenciales duales (`env_access` + `shopper`)** | **H4.1, H5.1, RF-15** | **Completo desde día 1** (era Simplificado en versión anterior) |
| M14 | Logging CloudWatch | H4.5 + (stdout + JSONFormatter, ingesta vía awslogs driver) | Simplificado |
| M15 | Webhook Slack | — | Aplazado a SHOULD HAVE |
| M16 | Schema versionado /v1/ | Endpoints `/v1/` en H4.1–H4.3, H5.* | Completo |
| M17 | Distinción infra vs tienda | H1.4 | Completo |
| M18 | Pre-flight anti-bot | (`anti_bot_whitelisted` flag en EnvironmentConfig) + operativo | Simplificado |
| **M19** | **Dashboard Web Interno (5 pantallas + matriz genérica)** | **H5.1, H5.2, H5.3, H5.4, H5.5** | **Completo** |
| **M20** | **Flows de recorrido curados (PLP/búsqueda, descuentos, PDP, carrito) + `full_journey`** | **H6.1–H6.4** | **Comprometido — ola 2 (HITL specs primero)** |
| **M21** | **Documento de auditoría de 6 dimensiones (colectores deterministas + agente que sintetiza, P7)** | **H7.1–H7.5** | **Comprometido — ola 2 (HITL specs primero)** |
| **M22** | **Captura de red / timings (HAR + CWV + controllers SFRA)** | **H8.1, H8.2** | **Comprometido — ola 2 (HITL specs primero)** |
| **M23** | **Ventana de lenguaje natural + modos gate/exploratorio** | **H9.1, H9.2, H9.3** | **Comprometido — ola 2 (HITL specs primero)** |

**Total**: 17 completos (ola 1) + 4 comprometidos ola 2 (M20–M23) / 2 simplificados (M14, M18) / 1 aplazado a ola posterior (M15).

---

## Justificación de simplificaciones y aplazamientos

### M5 — Translator NL → PROMOVIDO a path principal de UX (actualizado 2026-06-03)

**Justificación 2026-06-03 (D18)**: el criterio de promoción definido en 2026-05-24 se cumplió — la realineación hace de la ventana NL la entrada principal para usuarios no-técnicos (UC6, M23). Se materializa exactamente como estaba previsto: endpoint dedicado de traducción que devuelve config **sin ejecutar** + preview + confirmación; `POST /v1/run` sigue recibiendo solo payload estructurado (D8 intacta a nivel de contrato). Cubierto por H9.1/H9.2.

**Justificación 2026-05-24** (histórico): Decisión D8 actualizada — `POST /v1/run` recibe `SyntheticUserConfig` estructurado vía Pydantic. El translator se mantuvo como funcionalidad disponible para uso futuro. Esto redujo el riesgo R4 (LLM misinterpretation) y simplificó el path principal.

---

### M13 — Secrets Manager: COMPLETO (actualizado 2026-05-24)

**Justificación 2026-05-24**: el modelo de credenciales duales (`env_access` + `shopper` por ambiente) exige resolución desde Secrets Manager desde día 1. Sin esto, el sistema no funciona — no es una "simplificación post-MVP". Implementado por:
- `EnvironmentResolver` (S6) con caché TTL 5 min
- `SecretsManagerClient` (S7 implícito en C4-D)
- 8 secrets esperados: 2 por cada uno de los 3 ambientes + 1 API key + 1 Anthropic key
- Validación de paths al CREAR ambiente (BR-U4-07)

**Estado anterior** ("env vars en MVP") quedó obsoleto.

---

### M14 — CloudWatch logging → logging estándar en MVP

**Justificación**: stdout + `JSONFormatter` (decisión D12) ya emite logs estructurados que CloudWatch agent consume tal cual via `awslogs` driver del task definition. Sin cambios de código necesarios para llegar a CloudWatch.

---

### M15 — Webhook Slack → SHOULD HAVE

**Justificación**: Nice-to-have de notificación. El producto funciona end-to-end sin él (Carolina puede consultar el dashboard P5 o `GET /v1/runs/latest`). Aplazado hasta validar adopción interna.

---

### M18 — Pre-flight anti-bot → simplificado

**Justificación 2026-05-24**: parcialmente cubierto por el flag `anti_bot_whitelisted` en `EnvironmentConfig` — permite al equipo saber qué ambientes tienen la excepción aplicada. La aplicación de la excepción IP sigue siendo trabajo operativo (DevOps/Security). No requiere código aplicacional.

---

## Cobertura por Journey del PRD

| Journey PRD | Cubierto por | Notas |
|---|---|---|
| J1 — Carolina pre-deploy (happy path) | H4.1, H1.1, H1.2, H1.5, H3.1, H3.2, H5.1, H5.2 | Completo (incluye dashboard P1+P2+P3+P4) |
| J2 — Andrés revisa historial semanal | H4.2 + **H5.4 (historial filtrable)** | **Completo en MVP** (era parcial en versión anterior — el dashboard P5 con filtros cubre lo que faltaba de J2) |
| J3 — Edge case: timeout de infra | H1.4 | Completo |
| J4 — Edge case: agente no clasifica, escala a humano | **H7.3** (+ H7.2) | **Des-aplazado 2026-06-03 (D14)**: restaurado como agente de auditoría que sintetiza y marca `requires_human_review` — el semáforo sigue siendo regla determinista (P7). Entrega en ola 2 |

---

## Cobertura por Use Case (UC) del PRD

| UC | Cubierto por | Notas |
|---|---|---|
| UC1 — Validación pre-deploy de release | H4.1, H1.1–H1.5, H3.1, H3.2, H5.2 | Completo |
| UC2 — Detección de regresión de performance | H2.1, H2.2, H2.4, H5.4 | Completo |
| UC3 — Flujo de tarjeta rechazada | H1.3 | Completo |
| UC4 — Agente CI/CD consulta estado | H4.3, H3.2 | Completo |
| UC5 — Bootstrap de baseline | H2.2 | Completo |
| **UC6 — Miembro no-técnico lanza prueba en lenguaje natural** | **H9.1, H9.2** (ventana NL) + H5.1–H5.5 (dashboard) + H6.2/H6.4, H7.2 (documento legible) | **★ Realineado 2026-06-03 — UC6 del PRD v1.2 es la ventana NL, no solo el dashboard. Ola 2** |

---

## Cobertura por principio de diseño

| Principio | Cubierto por |
|---|---|
| P1 — Cero órdenes confirmadas | H1.2, H3.3 (defense-in-depth) + invariante `orders_created != 0` → 500 (BR-U4-11) |
| P2 — API versionada desde día 1 | Todos los endpoints `/v1/` (H4.1, H4.2, H4.3, H5.*) |
| P3 — Validación estricta de output LLM | H4.1 (AC2 — Pydantic en payload) |
| P4 — Honestidad del semáforo | H2.1, H2.2 |
| P5 — Seguridad de credenciales | H4.4, H0.2, H5.1 (dashboard no muestra credenciales — solo paths) |
| P6 — Trazabilidad completa | H4.1 (run_id), H4.5 (request_id en logs), H5.4 (historial auditable), H7.2 (evidencia enlazada por hallazgo) |
| **P7 — El agente sintetiza, no juzga (★ 2026-06-03)** | **H7.2, H7.3, H7.5** (+ C10: semáforo solo determinista) |

---

## Cobertura por unidad de trabajo

| Unidad | Historias | AC totales | RFs cubiertos |
|---|---|---|---|
| U0 Setup | 3 (H0.1, H0.2, H0.3) | 11 | RF-01, RF-02, RF-03 |
| U1 Executor | 5 (H1.1–H1.5) | 20 | RF-04, RF-05, RF-06, RF-07, RF-08 |
| U2 Baseline | 5 (H2.1–H2.5) | 20 | RF-09 |
| U3 Reporter | 3 (H3.1, H3.2, H3.3) | 11 | RF-10 |
| U4 API | 5 (H4.1–H4.5) | 21 | RF-11, RF-12, RF-13, RF-14, RF-15, RF-16, RF-17, RF-18, RF-19 |
| MD0 Dashboard | 5 (H5.1–H5.5) | 20 | RF-20, RF-29 |
| **U5 Flows de recorrido** | **4 (H6.1–H6.4)** | **16** | **RF-21, RF-22** |
| **U6 Auditoría** | **5 (H7.1–H7.5)** | **19** | **RF-24, RF-25, RF-26** |
| **U7 Captura de red** | **2 (H8.1–H8.2)** | **7** | **RF-23** |
| **U8 Ventana NL + modos** | **3 (H9.1–H9.3)** | **12** | **RF-27, RF-28** |
| **Total** | **40 historias** | **157 ACs** | **29 RFs** |

> **Nota de numeración (2026-06-03):** RF-14..RF-20 son los agregados de application design (2026-05-24, retro-portados a `requirements.md`); RF-21..RF-29 son la capa de la realineación. U5–U8 requieren la **puerta HITL de `specs/`** antes de construcción (cascade #6).

---

## Brechas restantes (deben monitorearse en Construction)

1. **M10 cubierto por Protocol pattern, pero no validado contra DynamoDB real**: si el equipo quiere validar la swappabilidad, conviene implementar un `DynamoDBBaselineStore` mock (con `moto` o LocalStack) que pase los mismos tests del Protocol. NO bloqueante para MVP.
2. ~~**J4 aplazado**~~ → **RESUELTO en diseño (2026-06-03, D14)**: H7.3 restaura la detección de anomalías con `requires_human_review` vía colectores deterministas + agente de síntesis. **Riesgo residual**: hasta que la ola 2 (U6) se construya, el gate de checkout sigue siendo mecánico — los bugs sutiles de promociones se detectan recién con U5+U6 en operación.
3. **Auth multi-usuario del dashboard**: MVP usa una sola API key compartida (sessionStorage). Si el equipo crece >10 personas, evaluar SSO corporativo. NO bloqueante para MVP.
4. **Rotación automática de Secrets Manager**: MVP usa rotación manual. Automatizar con Lambda rotator en sprint 3+.

---

## Cambios vs versión anterior (2026-05-24) — realineación 2026-06-03

- **Agregados**: M20–M23 (recorrido, auditoría, red, ventana NL) con cobertura H6.x–H9.x + H5.5 — comprometidos para ola 2 (alcance fijo, no recortable)
- **Des-aplazado**: J4 (D14) — cubierto por H7.3
- **Promovido**: M5 translator a path principal de UX (D18) — cubierto por H9.1/H9.2
- **Refinado**: M9 evidencia dirigida por hallazgos (D16) — H1.5 (gate) + H7.4 (auditoría)
- **Realineado**: UC6 ahora es la ventana NL del PRD v1.2 (antes solo dashboard)
- **Agregado**: P7 a la cobertura por principios
- **Totales**: 40 historias / 157 ACs / 29 RFs (era 25/99/20)

## Cambios vs versión anterior (2026-05-22)

- **Agregado**: M19 (Dashboard) con cobertura completa via H5.1–H5.4
- **Promovido**: M13 Secrets Manager de "Simplificado" a "Completo" (se usa desde día 1)
- **Promovido**: J2 Andrés historial de "Parcial" a "Completo" (dashboard P5 cubre filtros)
- **Reclasificado**: M5 Translator de "Completo" a "Disponible pero no en path principal" (D8 actualizada)
- **Agregado**: UC6 (Equipo no-CLI opera el sistema) cubierto por dashboard
- **Total de historias**: 25 (era 21 antes de agregar H5.1–H5.4)
- **Total de ACs**: 99 (era 83)
