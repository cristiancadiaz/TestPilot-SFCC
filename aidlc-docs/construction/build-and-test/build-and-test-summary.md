# Build and Test Summary — TestPilot SFCC

## Estado del proyecto

Todas las unidades U0–U4 implementadas. El proyecto es un monolito Python modular ejecutable localmente.

## Estructura final del código

```
src/
├── models.py                    # U0 — 9 modelos Pydantic + constantes
├── agents/
│   └── translator.py            # Existente — NL→SyntheticUserConfig (Claude API)
├── api/
│   └── main.py                  # U4 — 3 endpoints REST + auth + middleware
├── executor/
│   ├── _core.py                 # U1 — InfrastructureError, execute_step, take_screenshot
│   ├── profiles/                # U1 — 3 BrowserProfiles
│   ├── selectors.py             # U1 — catálogo CSS centralizado
│   ├── flows/                   # U1 — checkout_full + checkout_card_declined
│   └── runner.py                # U1 — run_profile() entry point
├── baseline/
│   └── baseline_manager.py      # U2 — BaselineStore, InMemoryBaselineStore, funciones p95
└── reporter/
    └── report_generator.py      # U3 — generate_report, to_json_dict, to_markdown
```

## Comando de verificación completa

```bash
# Todo en un comando
pip install -e ".[dev]" && \
playwright install chromium && \
ruff check . && \
mypy src/ && \
pytest tests/ -v --tb=short
```

## Cobertura de requisitos

| RF | Implementado en |
|----|----------------|
| RF-01 (pyproject.toml) | U0 |
| RF-02 (src/models.py) | U0 |
| RF-03 (CLAUDE_MODEL) | U0 |
| RF-04 (3 perfiles) | U1 |
| RF-05 (selectores centralizados) | U1 |
| RF-06 (checkout_full) | U1 |
| RF-07 (checkout_card_declined) | U1 |
| RF-08 (FlowRunner + infra_error) | U1 |
| RF-09 (BaselineManager) | U2 |
| RF-10 (ReportGenerator) | U3 |
| RF-11 (GET /v1/runs/{id}) | U4 |
| RF-12 (GET /v1/runs/latest) | U4 |
| RF-13 (POST /v1/run integrado) | U4 |

## Próximos pasos recomendados (post-MVP)

1. **Selectores**: Ejecutar contra staging SFCC real y ajustar `src/executor/selectors.py`
2. **DynamoDB**: Reemplazar `InMemoryBaselineStore` con implementación boto3
3. **S3**: Reemplazar `take_screenshot` local con upload a S3
4. **3 perfiles en paralelo**: Envolver `run_profile` en `asyncio.gather` en `POST /v1/run`
5. **Pre-flight anti-bot**: Coordinar con DevOps para IP allowlist (R1)
