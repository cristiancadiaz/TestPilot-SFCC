# Antigravity Missions

Planes de misión diseñados para ejecutarse **en paralelo** sobre Antigravity Mission Control. Cada misión es un brief autocontenido que un agente externo (Antigravity) ejecuta en una rama independiente, sin colisionar con las otras.

> 📖 **Antes de ejecutar nada, lee** [`objetivo-de-la-tarea.md`](./objetivo-de-la-tarea.md) — explica el porqué del ejercicio (cambio de paradigma del commit al artifact, decision matrix Claude Code vs Antigravity, context engineering como test cruzado).

## Misiones activas

| Mission | Branch | Módulo objetivo | Estado |
|---|---|---|---|
| 1 | `feat/api-scaffolding` | `src/api/` (FastAPI + `/v1/run`) | 📋 Plan listo, ejecución pendiente en Antigravity |
| 2 | `feat/baseline-dynamodb` | `src/baseline/` (DynamoDB + p95 + bootstrap) | 📋 Plan listo, ejecución pendiente en Antigravity |

## Cómo se usa

0. Verificar [`../definition-of-ready.md`](../definition-of-ready.md) contra la misión que se va a ejecutar. Si falla algún punto, reconciliar la misión antes de abrir Antigravity.
1. Abrir Antigravity Mission Control.
2. Crear una sesión por misión (2 sesiones en paralelo).
3. En cada sesión, pegar el contenido del archivo `mission-N-*.md` como instrucción inicial.
4. Aprobar el plan que el agente proponga (revisar contra criterios de aceptación).
5. Dejar que el agente ejecute hasta producir un diff.
6. Revisar el diff visualmente en Antigravity Editor.
7. Una vez ambas misiones produzcan diff:
   - Hacer rebase de cada rama contra `main` (alguno tocará `pyproject.toml` segundo y deberá resolver merge).
   - Abrir 2 PRs separados.
   - `review-pr` skill sobre cada uno.
8. Mergear en orden: Mission 2 primero (sin deps de Mission 1), luego Mission 1.

## Convenciones de diseño de misiones

- **Independencia.** Cada misión toca módulos disjuntos. Una sola colisión: `pyproject.toml`. Esa colisión es manejable porque las dependencias son aditivas.
- **Acotación.** Cada misión es ~60–90 min de trabajo agéntico. Si tarda más, el plan estaba mal dimensionado.
- **Contexto-first.** Cada misión declara explícitamente qué archivos leer antes de empezar. El agente no debe descubrir el contexto por exploración libre — eso aumenta el costo de tokens y la varianza.
- **Constraints explícitas.** Cada misión declara qué NO puede tocar. Esto reemplaza el "hubiera estado bien que…" del review humano.
- **Verificación reproducible.** Cada misión incluye los comandos exactos de verificación al final. El agente debe pegarlos en el PR description.
- **Fuentes canónicas primero.** Si una misión contradice `PRODUCT.md`, `AGENTS.md` o `specs/*.json`, gana la fuente canónica y la misión debe corregirse antes de ejecutar.
