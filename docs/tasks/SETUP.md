# Estación 7 — Setup diferido y validación

Alcance elegido: **Paquete + dry-run** (contrato OpenSymphony replicado manualmente, sin binario).
La cola está lista; aquí queda documentado el setup en vivo (Linear, AI-PR-review, memoria) para activarlo cuando se decida.

## 1. Validación del paquete (dry-run manual)

Réplica de lo que haría `convert_tasks_to_linear.py validate`. Resultado: ver el chequeo ejecutado en el cierre de esta entrega. Criterios verificados:

- [x] `docs/tasks/task-package.yaml` existe y parsea.
- [x] Los 6 task files declarados en el manifest existen.
- [x] Los 2 milestones del frontmatter de cada tarea coinciden con los del manifest.
- [x] `blockedBy` / `blocks` / `parent` referencian IDs válidos del mismo manifest.
- [x] Cada tarea referencia los artefactos AI-DLC que necesita (sección Context).
- [x] Acceptance criteria medibles y test plans con comandos.
- [x] No hay ciclos en el grafo de dependencias.

## 2. Publicar en Linear (diferido)

Requiere: workspace Linear + token + `project-slug` (+ `team-key` si hay varios teams), y el tooling de OpenSymphony instalado en `.ai/tooling/`.

> **El tooling es LOCAL (no versionado).** `.ai/tooling/` está en `.gitignore` (código de terceros, re-descargable). El resto de `.ai/` (p. ej. `roster.md`) sí se versiona. Para reinstalarlo desde cero, ver la receta más abajo.

### Receta de instalación del tooling (local)

```bash
# 1. Copiar las dos carpetas del template de OpenSymphony a .ai/tooling/
for f in $(gh api "repos/kumanday/OpenSymphony-template/git/trees/main?recursive=1" \
    --jq '.tree[] | select(.type=="blob") | .path | select(test("^\\.agents/skills/(convert-tasks-to-linear|linear)/"))'); do
  dest=".ai/tooling/${f#.agents/skills/}"
  mkdir -p "$(dirname "$dest")"
  gh api "repos/kumanday/OpenSymphony-template/contents/$f" -H "Accept: application/vnd.github.raw" > "$dest"
done

# 2. Reparar rutas hardcodeadas del template (.agents/skills/ -> .ai/tooling/)
grep -rl '\.agents/skills/' .ai/tooling | xargs sed -i 's#\.agents/skills/#.ai/tooling/#g'

# 3. Fix Windows (PENDIENTE en la copia actual): el conversor llama al helper con
#    "python3" (stub de Microsoft Store que NO ejecuta). Cambiar a sys.executable en
#    .ai/tooling/convert-tasks-to-linear/scripts/convert_tasks_to_linear.py (línea ~564).
```

### Credenciales (nunca en el repo)

El `LINEAR_API_KEY` vive en `.linear.env` (raíz, gitignored). Cargarlo en la sesión antes de cualquier comando: `set -a; . ./.linear.env; set +a`. Project-slug actual: `testpilot-sfcc-6be34d6b900c` (team único `CHR`, sin `--team-key`).

```bash
# Validar e inspeccionar antes de publicar
uv run --script .ai/tooling/convert-tasks-to-linear/scripts/convert_tasks_to_linear.py validate  --manifest docs/tasks/task-package.yaml
uv run --script .ai/tooling/convert-tasks-to-linear/scripts/convert_tasks_to_linear.py dry-run   --manifest docs/tasks/task-package.yaml
# Publicar (issues en estado Todo)
uv run --script .ai/tooling/convert-tasks-to-linear/scripts/convert_tasks_to_linear.py apply --manifest docs/tasks/task-package.yaml --project-slug [project-slug]
```
Salida esperada: `docs/tasks/linear-publish.yaml` con `issueIdentifier`/URL/`issueId` por TASK, milestones y blockers reflejados.

## 3. AI-PR-review automatizado (diferido — ruta HITL)

`.github/workflows/` es ruta protegida (HITL). Implementarlo requiere aprobación humana. Setup a crear cuando se active:

- `.github/workflows/ai-pr-review.yml` — workflow **advisory**, same-repo por defecto, fijado al SHA de la action.
- `.github/pull_request_template.md` — sección **Evidence** obligatoria.
- `.ai/tooling/custom-codereview-guide.md` — guía de review.
- `docs/ai-pr-review-human-setup.md` — setup humano.
- Secret: `AI_REVIEW_API_KEY`. Variables: `AI_REVIEW_PROVIDER_KIND`, `AI_REVIEW_MODEL_ID`, `AI_REVIEW_BASE_URL`, `AI_REVIEW_STYLE`, `AI_REVIEW_REQUIRE_EVIDENCE`. Label de rerun: `review-this`.
- Branch protection: aprobación humana + conversaciones resueltas (la IA es advisory; el gate de merge es humano).

> Complementa al ya existente: skill `review-pr` y agente `flow-guardian` cubren los invariantes TestPilot en el review.

## 4. Memoria evolutiva (diferido)

Requiere el CLI `opensymphony` (no instalado). Dry-run previsto por tarea cerrada:

```bash
opensymphony memory init --dry-run
opensymphony memory context --issue [issue-id]
opensymphony memory capture [issue-id] --dry-run
opensymphony memory sync-docs --since-last-sync --dry-run
opensymphony memory lint --public-docs
```
Captura propuesta por tarea: decisión validada, invariante tocado, validación útil, review feedback repetido, docs afectadas.

## 5. Documentación que debería evolucionar (propuesta)

Al cerrar U0, deberían actualizarse:
- `aidlc-docs/aidlc-state.md` → marcar U0 en Construction.
- `aidlc-docs/construction/u0/code/code-summary.md` → resumen real (TASK-006).
- `AGENTS.md` / `CLAUDE.md` → confirmar versión de imagen Playwright y modelo Claude usados.
- `docs/tasks/linear-publish.yaml` → cuando se publique.

## Cadena completa (referencia)

```
AI-DLC docs → (este paquete) → validate → dry-run → [Linear] → arnés (leader→implementer→reviewer) → PR + Evidence → AI review → memory capture → docs sync
```
Partes en vivo hoy: generación + validación + dry-run. El resto queda documentado arriba.
