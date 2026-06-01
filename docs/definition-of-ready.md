# Definition of Ready

Checklist para decidir si una mision esta lista para pasar de documentacion a implementacion. No reemplaza los criterios de aceptacion de cada mision; los valida antes de soltar un agente a escribir codigo.

## Antes de ejecutar una mision

- [ ] La fuente canonica aplicable esta identificada:
  - Producto: `PRODUCT.md`
  - Arquitectura/agentes: `AGENTS.md`
  - UI/diseno: `DESIGN.md`
  - Contratos API: `specs/*.json`
- [ ] La mision no contradice `specs/*.json`.
- [ ] Los nombres externos usan los valores canonicos del schema (`checkout_full`, `checkout_card_declined`, `mobile_co`, `desktop_co`, `desktop_ec`).
- [ ] El payload de entrada usa `flows[]`, `profiles[]`, `products[].search_term` y `products[].validate_variant`.
- [ ] El payload no incluye shopper, storefront URL, passwords, payment credentials ni credenciales de ambiente.
- [ ] La politica de screenshots es fallo + paso final; nunca OK intermedios.
- [ ] Los archivos permitidos y prohibidos estan listados en la mision.
- [ ] Los cambios a `specs/`, `infra/` o `src/executor/flows/` tienen confirmacion humana explicita.
- [ ] Los comandos de verificacion estan definidos y son reproducibles.
- [ ] La mision declara que dependencias nuevas requieren aprobacion humana.

## Antes de aprobar un plan generado por un agente

- [ ] El plan cita `AGENTS.md` y los schemas relevantes.
- [ ] No usa artefactos AI-DLC derivados como fuente unica de verdad.
- [ ] Si usa `aidlc-docs/construction/**`, reconoce su estado de snapshot y revisa `aidlc-docs/construction/README.md`.
- [ ] No introduce flows, profiles, environments ni campos de contrato nuevos.
- [ ] No convierte invariantes de producto en configuracion opcional.
- [ ] No propone CI, dependencias, infra o codigo fuera del alcance aprobado.

## Senales de no-ready

Si aparece cualquiera de estas senales, detener la ejecucion y reconciliar documentacion:

- `specs/prd.md` como fuente actual.
- `checkout-full` / `checkout-card-declined` como valores de contrato en lugar de `checkout_full` / `checkout_card_declined`.
- `mobile_mx`, `mobile-co`, `desktop-co` o `desktop-ec` como valores de `profiles[]`.
- `flow` o `profile` singular en payload de entrada.
- `sku` / `quantity` en `products[]`.
- `shopper.email` dentro del request.
- Screenshots OK+FAIL en todos los pasos.
- DynamoDB escrito desde `src/executor/`.

## Resultado esperado

Una mision ready debe poder entregarse a un agente externo sin pedirle que descubra el contexto global del repo. Si el agente necesita leer mas de los documentos listados en la mision para entender el contrato vigente, la mision no esta lista.
