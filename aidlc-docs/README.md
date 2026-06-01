# aidlc-docs/

Artefactos generados durante el flujo AI-DLC de TestPilot SFCC. Esta carpeta existe para trazabilidad y descomposicion, no para reemplazar las fuentes canonicas del proyecto.

## Como leer esta carpeta

Empieza por:

1. [`aidlc-state.md`](./aidlc-state.md): estado del flujo, fase actual y artefactos existentes.
2. [`audit.md`](./audit.md): log de inputs, aprobaciones y generacion de artefactos.
3. La subcarpeta de la fase que necesites:
   - [`inception/`](./inception/): requisitos, user stories, arquitectura y diseno de aplicacion.
   - [`construction/`](./construction/): planes y artefactos de construccion generados por unidad. Requieren reconciliacion antes de ejecutarse.

## Relacion con documentos canonicos

| Necesitas decidir sobre... | Fuente canonica | Usa `aidlc-docs/` para... |
|---|---|---|
| Producto, audiencia, alcance e invariantes | [`../PRODUCT.md`](../PRODUCT.md) | Ver trazabilidad de requisitos e historias. |
| Arquitectura del repo y reglas de agentes | [`../AGENTS.md`](../AGENTS.md) | Ver descomposicion en componentes y servicios. |
| UI, tono visual y reportes renderizados | [`../DESIGN.md`](../DESIGN.md) | Ver NFRs y tacticas relacionadas. |
| Contratos API | [`../specs/*.json`](../specs/) | Ver preguntas de verificacion y planes derivados. |

Si hay conflicto entre un artefacto AI-DLC y una fuente canonica, corrige o anota el artefacto derivado. No cambies la fuente canonica para acomodar un documento generado.

## Estructura

```text
aidlc-docs/
├── aidlc-state.md              # estado resumido del flujo
├── audit.md                    # log de decisiones y prompts
├── inception/
│   ├── requirements/           # requisitos y preguntas de verificacion
│   ├── user-stories/           # historias, Gherkin y cobertura
│   ├── architecture/           # C4, ADRs y NFR tactics
│   ├── application-design/     # componentes, servicios y unidades
│   └── reverse-engineering/    # snapshot historico del workspace
└── construction/               # planes por unidad y build/test
```

## Convenciones de mantenimiento

- Mantener `audit.md` append-only.
- Actualizar `aidlc-state.md` cuando cambie la fase, se agregue una carpeta relevante o se cierre una brecha.
- No usar archivos de `construction/` como instrucciones directas si contradicen misiones vigentes en [`../docs/antigravity-missions/`](../docs/antigravity-missions/).
- Antes de pasar a implementacion, revisar que los artefactos derivados no contradigan `PRODUCT.md`, `AGENTS.md` ni `specs/*.json`.
- Antes de ejecutar una mision de codigo, revisar [`../docs/definition-of-ready.md`](../docs/definition-of-ready.md).
