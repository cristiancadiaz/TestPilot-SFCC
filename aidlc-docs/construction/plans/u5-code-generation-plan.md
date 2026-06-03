# U5 Flows de Recorrido — Code Generation Plan

> ★ Realineación 2026-06-03 — ola 2. Prerrequisitos: U1 completo + `specs/` v2 aplicado (HECHO 2026-06-03).

## Unit Context
- **Tipo**: Brownfield — extiende `src/executor/` existente (U1)
- **Workspace root**: `F:\Development_Projects\IA\TestPilot-SFCC`
- **Stories cubiertas**: H6.1, H6.2, H6.3, H6.4 — RF-21, RF-22
- **Restricciones**: catálogo cerrado (C1) · selectores solo en `selectors.py` (C7) · cero pasos de pago en flows de recorrido (C3) · `full_journey` NUNCA como archivo flow (D15)

## Dependencies
Requiere U1 completo (runner, selectors, profiles) y `specs/synthetic-user-config.schema.json` v2 (enum de flows extendido).

## Steps

### Step 1: Crear `src/executor/flow_catalog.py` [ ]
- **Acción**: CREATE
- **Contenido**: registro declarativo del catálogo: `FLOW_REGISTRY` (nombre → módulo flow + `critical_points[]` + `preconditions`), `COMPOSITIONS = {"full_journey": ["search_and_filter", "pdp_validation", "cart_review", "checkout_full"]}`, función `expand_flows(flows: list[str]) -> list[str]` (expande `full_journey` y deduplica preservando orden)

### Step 2: Extender `src/executor/selectors.py` con grupos PLP y PROMOTIONS [ ]
- **Acción**: MODIFY
- **Contenido**: constantes para grid de PLP, refinamientos (categoría/precio), badge/precio tachado de promoción, navegación a página de ofertas. Prefijos `data-cmp-`/`data-testid-` donde existan. Un comentario por constante

### Step 3: Crear `src/executor/flows/search_and_filter.py` [ ]
- **Acción**: CREATE
- **Contenido**: `run(page, config, env, run_id, profile_id) -> FlowResult` — pasos: `env_access_auth` → `search_from_header` → `plp_results_validation` → `apply_refinement` → `grid_response_validation`. `setup()` no-op (no requiere estado previo). Emite precios observados para colectores (U6)

### Step 4: Crear `src/executor/flows/browse_discounted_products.py` [ ]
- **Acción**: CREATE
- **Contenido**: pasos: `env_access_auth` → `navigate_to_promotions` → `plp_discount_display_validation` (precio original tachado + precio con descuento) → `select_discounted_product` → `pdp_discount_consistency`. Inconsistencia de descuento = dato para hallazgo (no fallo duro, H6.4 AC3). Emite precios PLP/PDP

### Step 5: Crear `src/executor/flows/pdp_validation.py` [ ]
- **Acción**: CREATE
- **Contenido**: pasos: `env_access_auth` → `search_product` (por `products[].search_term`) → `pdp_price_visible` → `pdp_variant_selector` → `pdp_gallery_loads` → `pdp_add_to_cart_enabled`. `setup()` = búsqueda del producto

### Step 6: Crear `src/executor/flows/cart_review.py` [ ]
- **Acción**: CREATE
- **Contenido**: pasos: `cart_product_present` → `cart_quantity_update` → `cart_subtotal_recalc` → `cart_price_consistency` (vs precio PDP observado). `setup()` = buscar producto + añadir al carrito (pasos marcados `phase: "setup"`, H6.2 AC3)

### Step 7: Modificar `src/executor/runner.py` — despacho genérico + composición [ ]
- **Acción**: MODIFY
- **Contenido**: reemplazar despacho if/else por lookup en `FLOW_REGISTRY`; nueva función `run_composition(profile, flow_names, ...)` que ejecuta flows encadenados preservando el contexto del browser (omite `setup()` intermedios); fallo de un eslabón → siguientes flows `skipped` (H6.3 AC3)

### Step 8: Modificar `src/executor/flows/__init__.py` [ ]
- **Acción**: MODIFY
- **Contenido**: exports de los 4 flows nuevos

### Step 9: Actualizar `src/models.py` — enum FlowName [ ]
- **Acción**: MODIFY
- **Contenido**: `FlowName` extiende con los 4 flows modulares; `full_journey` NO entra al enum del executor (solo al de la API/config — se expande antes); campo `mode` y `phase` si U8 no los agregó aún (coordinar)

### Step 10: Crear `tests/test_flow_catalog.py` [ ]
- **Acción**: CREATE
- **Contenido**: `expand_flows(["full_journey"])` retorna la secuencia declarada; `expand_flows(["full_journey", "cart_review"])` deduplica; flow fuera de catálogo lanza; test estático: ningún flow de recorrido importa selectores de PAYMENT ni contiene pasos de pago (H6.1 AC2)

### Step 11: Crear `tests/test_journey_flows.py` [ ]
- **Acción**: CREATE
- **Contenido**: con MagicMock de Page — cada flow retorna FlowResult con pasos esperados; `setup()` de cart_review marca pasos `phase="setup"`; browse_discounted emite precios estructurados; fallo de paso → posteriores `skipped`

### Step 12: Crear `tests/test_runner_composition.py` [ ]
- **Acción**: CREATE
- **Contenido**: composición preserva contexto (mismo Page entre flows); fallo en eslabón 2 → eslabones 3-4 `skipped`; despacho genérico funciona para los 6 flows del registro sin if/else

## Validation
- `ruff check .` + `mypy src/` sin errores
- `uv run pytest tests/test_flow_catalog.py tests/test_journey_flows.py tests/test_runner_composition.py -v` verde
- Criterio de completitud de unit-of-work.md U5 satisfecho (H6.1–H6.4 AC)
