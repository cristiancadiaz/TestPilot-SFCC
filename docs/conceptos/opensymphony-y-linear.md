# OpenSymphony y Linear — cómo encajan en TestPilot SFCC

> Documento conceptual. Explica qué es OpenSymphony, por qué usa Linear, dónde
> entra el skill `convert-tasks-to-linear` que instalamos, y cómo todo esto se
> relaciona con el arnés de agentes (`leader → implementer → reviewer`) de este
> repo. No es normativo; para reglas duras ver `CLAUDE.md` / `AGENTS.md`.

---

## 1. Qué es OpenSymphony (el sistema completo)

OpenSymphony es un **demonio autónomo** (implementación en Rust de la spec de
OpenAI Symphony) que **convierte issues de Linear en código, solo**. Su objetivo
es que el equipo gestione *trabajo* en lugar de *supervisar agentes de código*.

El bucle que corre de forma continua:

```
+--------------------------- OpenSymphony (daemon Rust) ---------------------------+
|                                                                                  |
|  1. POLL       LinearClient consulta Linear cada cierto intervalo                |
|     |          -> normaliza los issues a su modelo de dominio                    |
|  2. FILTRA     elige issues "elegibles" (estado correcto, sin bloqueos,          |
|     |           dentro del limite de concurrencia)                               |
|  3. CLAIM      reclama el issue (Unclaimed -> Claimed)                           |
|     |                                                                            |
|  4. WORKSPACE  WorkspaceManager crea un directorio AISLADO solo para ese issue   |
|     |                                                                            |
|  5. SPAWN      lanza un agente OpenHands (via WebSocket) en ese workspace        |
|     |          el agente: planifica -> implementa -> valida -> arma el PR        |
|  6. MONITOR    detecta stalls y reintentos (RetryQueue), guarda snapshots        |
|     |                                                                            |
|  7. WRITE-BACK un servidor linear-mcp deja que el agente COMENTE y CAMBIE el     |
|     |           estado del issue en Linear (Running -> Done) y enlace el PR       |
|     +--------- repite con el siguiente issue elegible -------------------------+ |
+----------------------------------------------------------------------------------+
```

Componentes principales del sistema:

| Capa | Componentes |
|---|---|
| Política | Definiciones de workflow, skills de agente |
| Configuración | `WorkflowDefinition`, resolución de entorno |
| Coordinación | `Scheduler`, `RetryQueue`, `SnapshotStore` |
| Ejecución | `WorkspaceManager`, `OpenHandsClient`, `IssueSessionRunner` |
| Observabilidad | Control Plane API, TUI de terminal |

## 2. Linear como "control plane"

El insight central: **Linear es la cola de trabajo y el tablero de control.**
OpenSymphony no tiene su propia UI de tareas — usa Linear como fuente de verdad.

- Un issue en estado elegible = "hay trabajo que hacer".
- El cambio de estado (Todo → In Progress → Done) = "el trabajo avanzó / terminó".
- **Read path:** el daemon hace polling de Linear y normaliza los issues.
- **Write path:** los agentes comentan y transicionan issues vía un servidor
  `linear-mcp` (Model Context Protocol).

Todo el ciclo gira alrededor de esos issues.

## 3. Dónde encaja el skill `convert-tasks-to-linear`

Ese skill es **la rampa de entrada** del ciclo: el paso que *siembra* Linear. El
daemon no inventa issues — alguien tiene que ponerlos ahí. Eso es exactamente lo
que hace nuestro paquete de tareas:

```
aidlc-docs           docs/tasks/            [convert-tasks-to-linear]      issues en
(planeacion)   --->  (task package)  --->   valida -> dry-run -> apply  -->  Linear  --> (de aqui, el motor de ejecucion)
                                             ^ ESTO es lo que instalamos
```

Sin issues en Linear, el demonio (o cualquier motor de ejecución) no tiene nada
que hacer. El skill es el puente **planeación → Linear**; lo que viene *después*
es el motor que toma cada issue y lo vuelve código.

El skill `convert-tasks-to-linear` se apoya en un skill companion `linear/`
(helper GraphQL) para hablar con la API de Linear. Ambos están instalados en
`.agents/skills/`. Comandos:

- `validate` — valida el paquete localmente (no escribe en Linear).
- `dry-run` — muestra las olas de creación sin publicar.
- `apply --project-slug <slug>` — publica los issues y genera
  `docs/tasks/linear-publish.yaml` (mapeo task → issue: key, id, URL).

## 4. La bifurcación: dos motores de ejecución posibles

Una vez sembrados los issues en Linear, hay **dos formas** de consumirlos. Este
repo eligió la Ruta B.

| | Ruta A — OpenSymphony completo | Ruta B — Arnés Claude Code (este repo) |
|---|---|---|
| Quién implementa el issue | Agente OpenHands autónomo | `implementer` / `reviewer` conducidos por el `leader` |
| Orquestador | Demonio Rust (polling, workspaces, retries) | El `leader` desde el loop principal de Claude Code |
| Infraestructura | Daemon Rust + OpenHands + `linear-mcp` corriendo | Ya instalada (Claude Code) |
| Autonomía | Total (corre sin intervención) | Semi — con puertas de aprobación humana (HITL) |
| Estado en este repo | **No instalado** | **Listo** |
| Rol de Linear | Control plane del daemon | Tablero de tracking + fuente de los issues a tomar |

**En las dos rutas Linear cumple el mismo papel** (cola/tablero de unidades de
trabajo) y **el skill de conversión es el mismo punto de partida.** Lo que cambia
es *quién* toma cada issue y lo convierte en código.

## 5. Estado actual en TestPilot SFCC

Este repo **no corre** el demonio Rust ni OpenHands. **Replicó el contrato de
planeación** de OpenSymphony (el task package en `docs/tasks/` + el skill de
conversión) y usa **su propio arnés de Claude Code como motor de ejecución**:
`leader → implementer → reviewer`, con disciplina HITL.

Razones de la decisión:

- La Ruta A es pesada (runtime Rust + OpenHands + `linear-mcp`), totalmente
  autónoma, y no encaja bien con la disciplina HITL del proyecto ni con Windows.
- El valor de OpenSymphony que sí adoptamos es **su contrato de tareas y el uso de
  Linear como tablero** — no su runtime.

Consecuencia práctica: lo que sembremos en Linear con `apply` sirve igual para
ambas rutas (no es trabajo perdido). El camino natural hoy es la Ruta B —
el "E5: Code Generation de U0".

## 6. La cadena completa (referencia)

```
AI-DLC docs -> (task package) -> validate -> dry-run -> [Linear]
  -> motor de ejecucion (Ruta B: leader -> implementer -> reviewer)
  -> PR + Evidence -> AI review -> memory capture -> docs sync
```

Partes en vivo hoy en este repo: **generación + validación + dry-run** del
paquete. El resto queda documentado en `docs/tasks/SETUP.md` para activarse con
aprobación humana.

---

### Glosario relacionado

Ver [`glosario.md`](glosario.md) para: AI-DLC, Unit of Work, MCP, Skill,
Subagente, y los invariantes de producto (zero contamination, closed flow
catalog, JSON Schema gate, p95, bootstrap, traffic light).

### Fuentes

- OpenSymphony — https://github.com/kumanday/OpenSymphony
- Template (skills) — https://github.com/kumanday/OpenSymphony-template
- Contrato del skill — `.agents/skills/convert-tasks-to-linear/SKILL.md`
