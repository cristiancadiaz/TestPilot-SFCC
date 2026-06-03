# Investigacion

Contexto de mercado, validacion, critica y material de soporte del curso. Estos documentos explican por que el proyecto existe y que riesgos se consideraron, pero no son contrato de implementacion.

> **Vigencia (2026-06-02):** estos documentos son **insumos históricos** (Estación 1, mayo 2026). El **objetivo y alcance vigentes** del producto viven en [`PRODUCT.md`](../../PRODUCT.md) §1, realineado el 2026-06-02 (recorrido completo de tienda + documento de auditoría de 6 dimensiones + ventana de lenguaje natural). Racional completo en [`aidlc-docs/inception/scope-realignment-brief.md`](../../aidlc-docs/inception/scope-realignment-brief.md).

## Archivos

| Archivo | Uso |
|---|---|
| [`overview.md`](./overview.md) | Landscape tecnologico, why-now y analisis competitivo. |
| [`mercado.md`](./mercado.md) | Contexto de mercado y oportunidad. |
| [`critica.md`](./critica.md) | Critica y riesgos del enfoque. |
| [`deep-research-validacion.md`](./deep-research-validacion.md) | Investigacion de validacion y benchmarks. |
| [`deep-research-critica.md`](./deep-research-critica.md) | Investigacion critica y modos de fallo. |
| [`hcai-c2-internal-solution-brief.md`](./hcai-c2-internal-solution-brief.md) | Brief interno original del programa Hardcore AI. |

## Regla

Si un hallazgo de investigacion contradice una decision canonica vigente, no lo uses directamente para implementar. Abre una decision explicita en `PRODUCT.md`, `AGENTS.md`, `DESIGN.md` o un ADR.
