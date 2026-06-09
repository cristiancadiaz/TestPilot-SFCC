# Conceptos — TestPilot SFCC

Carpeta de **referencia conceptual** versionada. Su propósito es tener claros los
conceptos de *qué se está haciendo* y *por qué*, independientes del código y del
material de curso (que vive gitignored en `.hardcore-ai/`).

## Contenido

| Archivo | Qué explica |
|---|---|
| [`opensymphony-y-linear.md`](opensymphony-y-linear.md) | Qué es OpenSymphony, cómo usa Linear como tablero de trabajo, dónde encaja el skill `convert-tasks-to-linear`, y cómo se relaciona con el arnés de agentes de este repo. |
| [`arnes-propio-vs-opensymphony.md`](arnes-propio-vs-opensymphony.md) | Por qué se eligió el arnés propio de Claude Code (HITL) en vez del orquestador autónomo de OpenSymphony. Aclara que OpenSymphony-producto sí genera código desde Linear, pero aquí solo se usó su skill de publicación. |
| [`glosario.md`](glosario.md) | Definiciones canónicas de los términos del proyecto (metodología AI-DLC, ingeniería agéntica, invariantes de producto, stack). Copia versionada del glosario del vault Obsidian. |

## Relación con el resto de la documentación

- `CLAUDE.md` / `AGENTS.md` → reglas e invariantes operativos (qué hace cada agente, qué no tocar).
- `aidlc-docs/` → artefactos AI-DLC (requisitos, historias, ADRs, diseño).
- `docs/tasks/` → el paquete de tareas de la unidad U0 (lo que se siembra en Linear).
- **`docs/conceptos/` (esta carpeta)** → el *mapa mental*: definiciones y cómo encajan las piezas.

> Los conceptos aquí son explicativos, no normativos. La fuente de verdad de
> reglas duras sigue siendo `CLAUDE.md` / `AGENTS.md`.
