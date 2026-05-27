# specs/

Contratos versionados de la API de TestPilot SFCC. Esta carpeta es la **source of truth** del contrato `/v1/run` — cualquier cambio de campo es breaking y obliga a bump de versión.

## Archivos

| Archivo | Propósito |
|---|---|
| `synthetic-user-config.schema.json` | JSON Schema del payload de entrada de `POST /v1/run`. Validado por `src/agents/` antes de levantar cualquier browser. |

## Reglas de cambio

1. **Cualquier rename, remove o type change** de un campo existente → bump a `v2/`, mantener `v1/` como deprecated por al menos 1 sprint.
2. **Adición de campo opcional** (`required: false`) → se permite sin bump.
3. **Adición de un valor al `enum` de `flow` o `profile`** → requiere PR explícito con review de tech lead. El catálogo cerrado es intencional, ver `CLAUDE.md` § Hard Invariants.
4. **Los `examples`** del schema deben validar contra el schema mismo en CI.

## Cómo se consume

- Runtime: `src/agents/` lo carga al iniciar y valida cada `SyntheticUserConfig` antes de devolverlo al orquestador.
- Tests: `tests/test_agents_validation.py` debe probar que ejemplos válidos pasan y que payloads malformados son rechazados con error descriptivo.
- Skill `validate-synthetic-config`: usa este schema vía `.claude/skills/validate-synthetic-config/scripts/validate.py`.
