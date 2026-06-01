# Documentacion de TestPilot SFCC

Este directorio contiene contexto de producto, mercado y planes de ejecucion. No todos los documentos tienen la misma autoridad. Para evitar drift, usa esta pagina como mapa de lectura.

## Lectura recomendada

### Si vas a implementar codigo

1. Lee [`../AGENTS.md`](../AGENTS.md) para arquitectura, convenciones, restricciones y rutas protegidas.
2. Lee [`../PRODUCT.md`](../PRODUCT.md) para invariantes de producto y alcance MVP.
3. Lee [`../specs/README.md`](../specs/README.md) y los JSON Schemas en [`../specs/`](../specs/) para contratos API.
4. Revisa [`definition-of-ready.md`](./definition-of-ready.md) antes de ejecutar una mision.
5. Si la tarea viene de una mision, lee solo el archivo correspondiente en [`antigravity-missions/`](./antigravity-missions/).
6. Usa [`../aidlc-docs/README.md`](../aidlc-docs/README.md) solo cuando necesites trazabilidad AI-DLC mas detallada.

### Si vas a revisar producto o alcance

1. [`../PRODUCT.md`](../PRODUCT.md) es la fuente canonica de producto.
2. [`../README.md`](../README.md) da el resumen ejecutivo del sistema.
3. [`product/`](./product/) contiene snapshots de definicion de producto.
4. [`research/`](./research/) contiene insumos de investigacion y decision, no contratos vigentes.

### Si vas a revisar arquitectura o decisiones tecnicas

1. [`../AGENTS.md`](../AGENTS.md) es la fuente canonica para arquitectura operativa de agentes.
2. [`../aidlc-docs/inception/architecture/adrs/`](../aidlc-docs/inception/architecture/adrs/) contiene ADRs puntuales.
3. [`../aidlc-docs/inception/application-design/`](../aidlc-docs/inception/application-design/) contiene la descomposicion AI-DLC en componentes, servicios y unidades.

### Si vas a revisar contratos

1. [`../specs/synthetic-user-config.schema.json`](../specs/synthetic-user-config.schema.json) es la fuente de verdad del payload de entrada.
2. [`../specs/execution_report.schema.json`](../specs/execution_report.schema.json) es la fuente de verdad del reporte de salida.
3. [`product/prd-2026-05-22.md`](./product/prd-2026-05-22.md) conserva el PRD de estacion como insumo historico. Si contradice los schemas, gana `specs/*.json`.

## Niveles de autoridad

| Nivel | Documentos | Uso |
|---|---|---|
| Canonico | `PRODUCT.md`, `AGENTS.md`, `DESIGN.md`, `specs/*.json` | Decisiones vigentes. Si hay conflicto, estos documentos mandan. |
| Operativo | `docs/antigravity-missions/*.md`, `aidlc-docs/aidlc-state.md`, `progress/README.md` | Planes de trabajo, estado y coordinacion. Deben alinearse con lo canonico. |
| Readiness | `docs/definition-of-ready.md` | Checklist para pasar de documentacion a implementacion. |
| Derivado | `aidlc-docs/inception/**`, `aidlc-docs/construction/**` | Artefactos generados por AI-DLC. Utiles para trazabilidad, no reemplazan lo canonico. |
| Producto derivado | `docs/product/**` | Snapshots de producto, ICP y PVB. Usar como contexto; `PRODUCT.md` manda. |
| Investigacion | `docs/research/**` | Contexto, benchmark y racional. No usar como contrato de implementacion si contradice fuentes canonicas. |
| Historico | `docs/product/prd-2026-05-22.md` | Snapshot de la estacion/PRD. Mantiene decisiones y conflictos resueltos en ese momento. |

## Regla de resolucion de conflictos

Cuando dos documentos digan cosas distintas:

1. Para contratos API, gana `specs/*.json`.
2. Para invariantes de producto, gana `PRODUCT.md`.
3. Para restricciones de agentes, rutas protegidas y arquitectura del repo, gana `AGENTS.md`.
4. Para UI y material visual, gana `DESIGN.md`.
5. Para decisiones antiguas o contexto de por que se tomo una decision, consulta `aidlc-docs/` y `docs/`.

## Higiene documental

- No dupliques decisiones canonicas en documentos derivados; enlaza al source of truth.
- Si una mision contradice `specs/*.json`, corrige la mision antes de ejecutarla.
- Si un documento historico conserva una decision superada, agrega una nota de vigencia en vez de borrar el contexto.
- No muevas artefactos AI-DLC generados sin actualizar `aidlc-docs/aidlc-state.md`.
