# Construction Artifacts

Artefactos generados durante la fase AI-DLC Construction. Son utiles para trazabilidad y descomposicion, pero **no estan listos para ejecucion directa** sin reconciliacion.

## Estado de vigencia

Estos documentos fueron generados antes de varias decisiones canonicas actuales:

- `specs/` quedo reservado solo para JSON Schemas.
- El PRD snapshot se movio a `docs/product/prd-2026-05-22.md`.
- El contrato vigente usa `flows[]` y `profiles[]`, no `flow` / `profile` singular.
- Los valores canonicos del schema usan underscore: `checkout_full`, `checkout_card_declined`, `mobile_co`, `desktop_co`, `desktop_ec`.
- `products[]` usa `search_term` y `validate_variant`, no `sku` / `quantity`.
- `shopper` y credenciales se resuelven server-side; no viajan en payload.
- Screenshots: solo fallo + paso final.

## Como usar esta carpeta

1. Usar estos documentos para entender la intencion original de unidades y dependencias.
2. Antes de ejecutar cualquier plan, pasar por [`../../docs/definition-of-ready.md`](../../docs/definition-of-ready.md).
3. Para contratos, validar contra [`../../specs/`](../../specs/).
4. Para arquitectura y restricciones, validar contra [`../../AGENTS.md`](../../AGENTS.md).
5. Si un plan de `construction/` contradice una fuente canonica, corregir el plan o crear una mision nueva antes de implementar.

## Riesgos conocidos de drift

| Tema | Riesgo | Fuente canonica actual |
|---|---|---|
| Naming de flows/profiles | Algunos planes usan kebab-case (`checkout-full`, `mobile-co`) | `specs/synthetic-user-config.schema.json` |
| Perfil Mexico | Algunos planes mencionan `mobile_mx` | `desktop_ec` en `specs/synthetic-user-config.schema.json` |
| Screenshots | Algunos planes hablan de OK+FAIL por paso | `PRODUCT.md`, `AGENTS.md`, ADR-002 |
| Payload de producto | Algunos planes mencionan `sku` / `quantity` | `products[].search_term`, `validate_variant` |
| Shopper en payload | Algunos planes historicos asumen email en config | Credenciales server-side via Secrets Manager |

## Regla

No ejecutar planes de `aidlc-docs/construction/**` como prompt de implementacion sin una pasada previa de reconciliacion. Las misiones activas deben vivir en `docs/antigravity-missions/` y cumplir la Definition of Ready.
