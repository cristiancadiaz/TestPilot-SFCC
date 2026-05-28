# Integration Test Instructions — TestPilot SFCC

## Prerequisito: acceso al storefront SFCC staging

Los tests de integración requieren una URL de storefront real. Antes de ejecutar:

1. Confirmar con DevOps/Security que la IP del entorno de CI está en la allowlist de Akamai/Cloudflare (R1 del risk register)
2. Obtener la URL del storefront de staging

## Test de smoke E2E (manual — un solo perfil)

```bash
# Levantar la API localmente
pip install -e ".[dev]"
playwright install chromium
export API_KEY=dev-local-key
export STOREFRONT_URL=https://your-sfcc-staging.example.com
uvicorn src.api.main:app --port 8000

# En otra terminal, enviar un run
curl -X POST http://localhost:8000/v1/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-local-key" \
  -d '{
    "testRunId": "550e8400-e29b-41d4-a716-446655440001",
    "flow": "checkout_full",
    "profile": "desktop_co",
    "storefrontUrl": "'"$STOREFRONT_URL"'",
    "email": "integration@testpilot.internal"
  }'
```

## Verificaciones post-integración

1. `trafficLight` en la respuesta es "green" (bootstrap mode en primera ejecución)
2. `ordersCreated` NO aparece en la respuesta JSON
3. Screenshots generados en `SCREENSHOT_DIR` (último paso)
4. `GET /v1/runs/latest` retorna el run con `ttlOk: true`
5. `GET /v1/runs/{run_id}` con el ID del run retorna 200

## Test del flujo checkout_card_declined

```bash
curl -X POST http://localhost:8000/v1/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-local-key" \
  -d '{
    "testRunId": "550e8400-e29b-41d4-a716-446655440002",
    "flow": "checkout_card_declined",
    "profile": "mobile_co",
    "storefrontUrl": "'"$STOREFRONT_URL"'",
    "email": "integration@testpilot.internal"
  }'
```

**Resultado esperado**: `status: "success"`, paso `verify_decline_message` en la lista de steps con `status: "success"`.

## Nota sobre selectores

Los selectores en `src/executor/selectors.py` son placeholders SFCC/SFRA genéricos.
Si el checkout falla en los primeros steps, actualizar los selectores para el cartridge específico.
