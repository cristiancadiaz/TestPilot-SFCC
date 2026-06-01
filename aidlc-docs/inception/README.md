# Inception Artifacts

Artefactos de la fase AI-DLC Inception: requisitos, historias, arquitectura, ADRs, diseno de aplicacion y reverse engineering.

## Como leerlos

- Para decisiones vigentes, empieza por `PRODUCT.md`, `AGENTS.md`, `DESIGN.md` y `specs/*.json`.
- Usa esta carpeta para trazabilidad: de donde salieron requisitos, historias, ADRs y unidades.
- Si un documento de Inception contradice una fuente canonica, gana la fuente canonica.

## Secciones

| Carpeta | Uso |
|---|---|
| `requirements/` | Requisitos y preguntas de verificacion. |
| `user-stories/` | Historias, escenarios Gherkin y matriz de cobertura. |
| `architecture/` | C4, ADRs y NFR tactics. |
| `application-design/` | Componentes, metodos, servicios, dependencias y unidades. |
| `reverse-engineering/` | Snapshot historico del workspace documentation-first. |

## Nota de vigencia

Inception esta mas cerca de las decisiones canonicas que `construction/`, pero aun puede contener convenciones historicas. Antes de usar una historia, requisito o unidad como input de implementacion, revisar [`../../docs/definition-of-ready.md`](../../docs/definition-of-ready.md).
