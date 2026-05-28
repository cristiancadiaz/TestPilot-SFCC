# Code Summary — U0 Setup Base

## Archivos creados

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `pyproject.toml` | Nuevo | Build system, dependencias pinned, ruff, mypy, pytest config |
| `src/models.py` | Nuevo | Todos los modelos Pydantic compartidos del sistema |
| `tests/test_models.py` | Nuevo | 11 tests unitarios para los modelos |
| `Dockerfile` | Nuevo | Imagen Playwright v1.48.0-jammy, usuario pwuser, EXPOSE 8000 |
| `.dockerignore` | Nuevo | Excluye .env, .git, aidlc-docs/, tests/, __pycache__ |

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `src/agents/translator.py` | Eliminada clase `SyntheticUserConfig` local; agregado `CLAUDE_MODEL = "claude-haiku-4-5-20251001"`; importa `SyntheticUserConfig`, `FLOWS`, `PROFILES` desde `src.models` |
| `src/api/main.py` | Eliminada clase `SyntheticUserConfig` local con sus validators y model_config; importa `SyntheticUserConfig` desde `src.models`; limpiados imports no usados |

## Versiones clave fijadas

| Dependencia | Versión |
|-------------|---------|
| Python | >=3.12 |
| fastapi | 0.115.0 |
| pydantic | 2.9.2 |
| anthropic | 0.40.0 |
| playwright | 1.48.0 |
| Imagen Docker base | mcr.microsoft.com/playwright/python:v1.48.0-jammy |

## Decisiones relevantes

- `SyntheticUserConfig` ahora es canónica en `src/models.py`: elimina la duplicación entre `translator.py` y `api/main.py`
- `CLAUDE_MODEL` como constante de módulo: facilita actualizaciones futuras en un solo lugar
- `FLOWS` y `PROFILES` exportados desde `src/models.py` como tuplas: ambos módulos usan la misma fuente de verdad para el catálogo cerrado
- Dockerfile usa `pwuser` (usuario no-root incluido en imagen base de Playwright)

## Criterio de completitud verificado (manual)

```
pyproject.toml       ✓ configurado con ruff, mypy strict, pytest
src/models.py        ✓ 9 modelos + 2 constantes exportadas
tests/test_models.py ✓ 11 tests, sin dependencias externas de ejecución
translator.py        ✓ CLAUDE_MODEL actualizado, SyntheticUserConfig importada
api/main.py          ✓ SyntheticUserConfig importada, no duplicada
Dockerfile           ✓ v1.48.0-jammy, sin latest, pwuser
.dockerignore        ✓ excluye .env, aidlc-docs/, tests/
```
