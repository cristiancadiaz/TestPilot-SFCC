# Unit of Work Dependencies — TestPilot SFCC (actualizado 2026-06-03)

> ⚠️ **Realineación 2026-06-03:** se agregan U5–U8 (ola 2). Todas requieren la **puerta HITL de `specs/`**
> (cascade #6) antes de construcción. La ola 1 (U0–U4, MD0) no cambia.

## Dependency Matrix

| Unidad | Depende de | Tipo | Puede paralelizarse |
|--------|-----------|------|-------------------|
| U0 Setup base | Ninguna | — | No (es el punto de partida) |
| U1 Executor | U0 | Compile (usa src/models.py) | Sí, en paralelo con U2 y MD0 |
| U2 Baseline Manager | U0 | Compile (usa src/models.py RunRecord, TrafficLight, EnvironmentId) | Sí, en paralelo con U1 y MD0 |
| U3 Reporter | U0, U2 | Compile (usa BaselineStore Protocol + TrafficLight) | No (requiere U2) |
| U4 API Endpoints | U0, U1, U2, U3 | Runtime (llama a todos + integra Secrets Manager + DynamoDB) | No (requiere U1+U2+U3) |
| MD0 Dashboard | U0 (contratos TS), U4 (runtime) | Contract (proyecta modelos TS de U0) + Runtime (consume REST de U4) | Sí en desarrollo con mocks de U4; integración final requiere U4 |
| **U5 Flows de recorrido** | **U1 + HITL specs** | Compile (extiende flows/, selectors, runner → despacho genérico) | **Sí, en paralelo con U7** |
| **U7 Captura de red** | **U1 + HITL specs** | Compile (listeners en executor) + Contract (campos en execution_report) | **Sí, en paralelo con U5** |
| **U6 Auditoría (colectores + agente)** | **U1, U3, U5, U7 + HITL specs** | Compile (colectores consumen datos de U5/U7) + Runtime (agente vía src/classifier/; reporter integra documento) | No (requiere U5+U7 para datos de dimensiones) |
| **U8 Ventana NL + modos** | **U0 (translator), U2 (filtro mode), U4, MD0 + HITL specs** | Runtime (endpoint translate + UI) + Contract (campo `mode`) | **Sí, en paralelo con U5/U6/U7** (no depende de ellas) |

## Secuencia de construcción recomendada

```
[Fase 1]   U0 Setup base        (prerrequisito de todo)
               |
    +----------+----------+----------+
    |                     |          |
[Fase 2]   U1 Executor    U2 Baseline   MD0 Dashboard  (paralelo — MD0 usa mocks de API)
    |                     |          |
    +----------+----------+          |
               |                     |
[Fase 3]   U3 Reporter               |  (depende de U2)
               |                     |
[Fase 4]   U4 API Endpoints          |  (depende de U1+U2+U3)
               |                     |
               +─── integracion ─────+  (MD0 conecta a U4 real)

========= PUERTA HITL specs/ (cascade #6 — breaking changes aprobados por humano) =========

[Fase 5]   U5 Flows recorrido   U7 Captura de red   U8 Ventana NL + modos   (paralelo)
               |                     |                   |
               +----------+----------+                   |
                          |                              |
[Fase 6]   U6 Auditoria (colectores + agente)            |  (requiere U5+U7)
                          |                              |
                          +───── integracion ────────────+  (documento de auditoria en MD0;
                                                             matriz generica ya lista via H5.5)
```

> **Nota ola 2:** la fecha del Demo Day (9-jun) NO recorta estas unidades — alcance fijo, el tiempo flexea.
> H5.5 (matriz genérica) conviene construirla en MD0 desde ola 1: es barata y evita re-trabajo del dashboard al llegar U5.

## Contratos de interfaz entre unidades

| Interfaz | Definida en | Consumida por |
|----------|-------------|---------------|
| `SyntheticUserConfig` | src/models.py (U0) | U1, U4, MD0 (vista TS) |
| `EnvironmentConfig` | src/models.py (U0) | U4 (CRUD), MD0 (P1 form) |
| `EnvironmentAccessCredentials` | src/models.py (U0) | U4 (resolver), U1 (http_credentials) — runtime only |
| `ShopperCredentials` | src/models.py (U0) | U4 (resolver), U1 (shopper_login) — runtime only |
| `ResolvedEnvironment` | src/models.py (U0) | U4 (produce), U1 (consume) |
| `ProfileResult` | src/models.py (U0) | U1 (produce), U3 (consume), U4 (consume) |
| `RunRecord` | src/models.py (U0) | U2 (produce/consume), U3 (consume), U4 (consume) |
| `RunStatus` / `ProfileLiveStatus` | src/models.py (U0) | U4 (produce), MD0 (P3 polling) |
| `TrafficLight` | src/models.py (U0) | U2 (produce), U3 (consume), MD0 (renderiza) |
| `ExecutionReport` | src/models.py (U0) | U3 (produce), U4 (retorna), MD0 (P4 renderiza) |
| `BaselineStore` (Protocol) | src/baseline/ (U2) | U3 (consume), U4 (consume) |
| **REST API `/v1/*`** | U4 (FastAPI routers) | MD0 (consumidor único), agentes CI/CD externos |
| **Estáticos `/`** | MD0 (Vite build) | Servidos por U4 (`StaticFiles` mount) |
| **FlowCatalog (registro + composición `full_journey` + puntos críticos)** *(★ ola 2)* | src/executor/ (U5) | U1-runner (despacho), U6 (puntos críticos de evidencia), U8 (catálogo para el translator), MD0 (columnas de la matriz) |
| **AuditFinding[] (hallazgos deterministas)** *(★ ola 2)* | colectores (U6, datos de U5/U7) | AuditAgent (U6), U3 (reporte), MD0 (vista) |
| **NetworkSummary + HAR ref** *(★ ola 2)* | src/executor/ (U7) | U6 (dimensión rendimiento), U3 (resumen en reporte) |
| **`mode: gate\|exploratory`** *(★ ola 2)* | src/models.py (U0, campo nuevo HITL) | U2 (filtro baseline), U4 (`latest` solo gate), MD0 (marca visual) |
| **`POST /v1/translate` (config propuesto + explicación, sin ejecutar)** *(★ ola 2)* | U8 (src/api + translator) | MD0 (NL window P2) |

## Checkpoints de integración

### Checkpoint 1 — Tras U1+U2+U3 (antes de construir U4)
Verificar en script local:
```python
report = generate_report(
    profile_results=[await run_profile(...)],
    baseline_store=InMemoryBaselineStore(),
    config=synthetic_user_config,
    run_id=str(uuid4()),
    env=resolved_environment_mock,
    started_at=datetime.now(timezone.utc),
)
assert report.orders_created == 0
assert to_json_dict(report)  # valida contra specs/execution_report.schema.json
```
Este checkpoint evita sorpresas al integrar todo en U4.

### Checkpoint 2 — Tras U4 (antes de conectar MD0 real)
Verificar contra backend levantado:
```bash
# 1. CRUD environments
curl -X POST .../v1/environments -H "X-API-Key: $KEY" -d '{...}'
curl .../v1/environments -H "X-API-Key: $KEY"

# 2. Run completo
curl -X POST .../v1/run -H "X-API-Key: $KEY" -d '{"environment_id":"sandbox",...}'

# 3. Status polling
curl .../v1/runs/$RUN_ID/status -H "X-API-Key: $KEY"

# 4. Historial
curl ".../v1/runs?environment_id=sandbox&page=1" -H "X-API-Key: $KEY"
```
Si los 4 endpoints responden correctamente, MD0 puede conectarse sin sorpresas.

### Checkpoint 3 — Tras integración MD0 ↔ U4 (gate final)
Flujo end-to-end del usuario:
1. Carolina registra un ambiente desde MD0 P1 → U4 persiste en DynamoDB.
2. Carolina lanza un run desde MD0 P2 → U4 resuelve credenciales y orquesta U1+U2+U3.
3. MD0 P3 muestra estado vivo (polling 3s) mientras los 3 perfiles ejecutan.
4. Al completar, MD0 navega a P4 con semáforo + screenshots + comparación con baseline.
5. MD0 P5 muestra el nuevo run en el historial.

Si el flujo completo funciona contra un ambiente real (sandbox SFCC), el sistema está listo para sprint piloto.

### Checkpoint 4 — Puerta HITL de specs/ (antes de Fase 5) *(★ ola 2)*
Aprobación humana explícita de los breaking changes de contrato, en un solo paquete:
1. `synthetic-user-config.schema.json`: enum `flows[]` extendido (4 flows de recorrido + representación de `full_journey`), `maxItems` ajustado, campo `mode` (`gate|exploratory`, default gate). Bump de versión.
2. `execution_report.schema.json`: campos de auditoría (hallazgos por dimensión + refs de evidencia) y de red (resumen + HAR ref). Bump de versión.
3. Contrato del endpoint `POST /v1/translate`.
Ningún código de U5–U8 que dependa de estos campos se escribe antes de esta aprobación.

### Checkpoint 5 — Tras U5+U7 (antes de U6) *(★ ola 2)*
Verificar en script local que un run de `full_journey` produce: StepResults por flow encadenado, datos de precios por página (U5), NetworkSummary con timings de controllers + CWV (U7), y cero credenciales en el HAR persistido. Estos son exactamente los inputs que los colectores de U6 consumen.

### Checkpoint 6 — Tras U6+U8 (gate final ola 2) *(★ ola 2)*
Flujo end-to-end del usuario no-técnico:
1. Valentina escribe "revisa la PDP de un producto en oferta y confirma que el descuento se aplique" en MD0.
2. Preview del config propuesto (flows: `browse_discounted_products`/`pdp_validation`, modo) → confirma.
3. Run ejecuta; matriz genérica muestra celdas en vivo.
4. Documento de auditoría legible con hallazgos enlazados a evidencia; semáforo determinista aparte.
5. Run exploratorio de prueba NO aparece en el baseline ni en `latest` de gate.

## Notas sobre MD0

**Por qué MD0 no es prerrequisito de U4 ni viceversa:**
- MD0 puede desarrollarse en paralelo con U4 usando mocks (MSW, JSON Server, o handlers de Vite).
- U4 puede testearse sin MD0 (TestClient de FastAPI cubre todos los endpoints).
- El acople real es **vía contrato REST** (`/v1/*`), no vía import de código.

**Por qué MD0 depende contractualmente de U0:**
- Los `interface` TypeScript del frontend proyectan los modelos Pydantic de `src/models.py`.
- Si U0 cambia un modelo (ej. agrega campo a `ExecutionReport`), MD0 debe actualizar su `types/api.ts`.
- Recomendación: generar `types/api.ts` automáticamente desde `openapi.json` de FastAPI (post-MVP) — elimina drift.

**Servido por U4:**
- En producción, FastAPI sirve `src/dashboard/dist/` como estáticos (`StaticFiles` mount).
- Esto implica que el build de MD0 debe estar disponible al hacer `docker build` (multi-stage en Dockerfile de U0).
- Sin esta integración, MD0 funcional pero no accesible vía la URL del ALB.
