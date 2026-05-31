# progress/ — Estado transitorio de orquestación

Working dir para el **estado efímero** del arnés de agentes AI-DLC. NO contiene
entregables formales: los artefactos de cada etapa viven en `aidlc-docs/<fase>/<etapa>/`
y el registro de decisiones en `aidlc-docs/audit.md`.

## Qué va aquí

- `current.md` — qué etapa/artefacto está en curso ahora mismo (apoya
  `session-continuity.md`: permite reanudar una sesión interrumpida).
- Notas de estado `blocked` que un `implementer` deja al detenerse.
- Scratchpad de coordinación entre `leader` ↔ subagentes durante una sesión.

## Qué NO va aquí

- ❌ Documentación AI-DLC (requirements, user-stories, ADRs, C4, NFR, diseño) →
  `aidlc-docs/`.
- ❌ Registro de inputs del humano / aprobaciones → `aidlc-docs/audit.md`.
- ❌ Código de aplicación → `src/`, `tests/` (fase futura).

## Versionado

Solo este `README.md` se versiona. Los archivos transitorios (`current.md`,
notas de sesión) están en `.gitignore` — son estado local, no historia del repo.
