# Unit of Work Dependencies — TestPilot SFCC (actualizado 2026-05-24)

## Dependency Matrix

| Unidad | Depende de | Tipo | Puede paralelizarse |
|--------|-----------|------|-------------------|
| U0 Setup base | Ninguna | — | No (es el punto de partida) |
| U1 Executor | U0 | Compile (usa src/models.py) | Sí, en paralelo con U2 y MD0 |
| U2 Baseline Manager | U0 | Compile (usa src/models.py RunRecord, TrafficLight, EnvironmentId) | Sí, en paralelo con U1 y MD0 |
| U3 Reporter | U0, U2 | Compile (usa BaselineStore Protocol + TrafficLight) | No (requiere U2) |
| U4 API Endpoints | U0, U1, U2, U3 | Runtime (llama a todos + integra Secrets Manager + DynamoDB) | No (requiere U1+U2+U3) |
| MD0 Dashboard | U0 (contratos TS), U4 (runtime) | Contract (proyecta modelos TS de U0) + Runtime (consume REST de U4) | Sí en desarrollo con mocks de U4; integración final requiere U4 |

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
               +─── integración ─────+  (MD0 conecta a U4 real)
```

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
assert to_json_dict(report)  # valida contra specs/execution_report.json
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
