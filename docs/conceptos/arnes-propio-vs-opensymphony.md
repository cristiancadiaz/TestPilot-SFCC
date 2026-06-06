# Por qué un arnés propio en vez de orquestar con OpenSymphony

> Documento conceptual. Explica la decisión de usar el **arnés propio de Claude
> Code** (`leader → implementer → reviewer`, con puertas HITL) como motor de
> ejecución, en lugar del **orquestador autónomo de OpenSymphony**. No es
> normativo; las reglas duras viven en `CLAUDE.md` / `AGENTS.md`. Complementa a
> [`opensymphony-y-linear.md`](opensymphony-y-linear.md).

---

## 0. Aclaración previa: qué ES OpenSymphony vs qué usamos

Un malentendido común — y entendible, porque hay **dos cosas con el mismo nombre**:

| | Qué es | ¿Está en TestPilot? |
|---|---|---|
| **OpenSymphony (producto)** | Un **daemon autónomo** que toma issues de Linear y **genera código solo** (vía agentes OpenHands en workspaces aislados). | ❌ **No.** No corre en este repo. |
| **OpenSymphony (template/skill)** | Solo el skill `convert-tasks-to-linear`: **publica** el task package en Linear (sembrar el tablero). | ✅ **Sí**, local en `.ai/tooling/`. |

**Conclusión clave:** sí, OpenSymphony-producto *es* "una herramienta que ejecuta
las tareas de Linear y genera código" — esa intuición es correcta. Pero **en
TestPilot solo se usó la mitad delantera** (publicar el backlog). La parte que
*ejecuta y genera código* la hace **tu arnés de Claude Code**, no OpenSymphony.

```
   OpenSymphony-producto (NO usado)        Lo que SÍ se usa en TestPilot
   =============================           =============================
   Linear --> daemon --> OpenHands         AI-DLC docs --> task package
          (genera codigo solo)                 --> convert-tasks-to-linear
                                                 --> Linear (tablero)
                                                 --> ARNES PROPIO (Claude Code)
                                                     genera el codigo, con HITL
```

---

## 1. Lo que comparten (por eso "casi no hay diferencia" en una capa)

Ambos enfoques usan la misma columna vertebral:

- **Mismo tablero:** Linear como cola de trabajo / control plane.
- **Misma semilla:** el task package publicado con `convert-tasks-to-linear`.
- **Mismo "qué hacer":** issues, milestones y blockers idénticos.
- **Mismo ciclo lógico:** tomar issue → planificar → implementar → validar → PR → cerrar.

Si solo importa "qué se construye y en qué orden", **son intercambiables**. Lo
sembrado en Linear sirve para los dos.

---

## 2. Dónde difieren (por eso "sí hay mucha diferencia" en otra capa)

| Dimensión | Arnés propio (Ruta B) | OpenSymphony (Ruta A) |
|---|---|---|
| **Control** | Human-in-the-loop; el humano conduce el `leader` | Autónomo: el daemon hace polling y reclama issues solo |
| **Motor de ejecución** | Subagentes Claude Code (`implementer`/`reviewer`) | Agentes OpenHands en workspaces aislados |
| **Disparo** | El humano elige el issue y arranca | El daemon detecta issues "elegibles" y arranca solo |
| **Infraestructura** | Cero extra (ya tienes Claude Code) | Daemon Rust + runtime OpenHands + servidor `linear-mcp` |
| **Concurrencia** | Secuencial, acotada por la atención humana | N issues en paralelo, cada uno su workspace |
| **Aislamiento** | Un working tree (worktrees opcional) | Workspace determinista por issue |
| **Fallos** | El humano nota y reintenta | RetryQueue, detección de stalls, snapshots |
| **Visibilidad** | Total (se ve en la sesión) | Control Plane API + TUI |
| **Velocidad sin humano** | Nula (requiere presencia) | Alta (corre de noche, sin supervisión) |

---

## 3. El eje que de verdad importa: autonomía vs gobernanza

No es "cuál es mejor" en abstracto — es **qué nivel de autonomía tolera el
proyecto**. TestPilot tiene una gobernanza HITL **dura**:

- Invariantes no negociables: zero contamination, catálogo cerrado de flows,
  `orders_created == 0`, nunca producción.
- Rutas que **exigen confirmación humana**: `specs/`, `infra/`,
  `src/executor/flows/`, `.github/workflows/`.
- Permisos *deny-by-default* en `.claude/settings.json`.
- Agente `flow-guardian` + skill `review-pr` existen para **frenar** cambios que
  violen invariantes.

➡️ **Una flota OpenHands totalmente autónoma escribiendo en `flows/` o `specs/`
sin pasar por un humano violaría las propias reglas del proyecto.** La autonomía
de OpenSymphony no es solo "más potente": es **incompatible con el modelo de
gobernanza definido**. Por eso se eligió el arnés propio.

---

## 4. La decisión: por qué el arnés propio (Ruta B)

1. **Fit de gobernanza.** Los invariantes y rutas protegidas piden HITL — que es
   exactamente lo que el arnés propio da y lo que OpenSymphony evita.
2. **Costo/infra proporcional.** Para U0–U4 (pocas unidades), montar daemon Rust
   + OpenHands + `linear-mcp` no se justifica. Claude Code ya está instalado.
3. **Trazabilidad y control.** Cada paso es visible y aprobable; encaja con el
   ciclo AI-DLC (puertas de aprobación, `audit.md`, checkboxes de estado).
4. **Reutilización del contrato, no del runtime.** El valor de OpenSymphony que sí
   se adoptó es su **contrato de tareas + Linear como tablero**, no su motor.

---

## 5. No es binario: híbridos posibles

Si más adelante se quiere *algo* de la potencia de OpenSymphony sin el daemon:

1. **Paralelismo sin daemon:** correr subagentes de Claude Code en **git
   worktrees** aislados y en background — da concurrencia y aislamiento (lo que
   más aporta OpenSymphony) manteniendo las puertas HITL.
2. **OpenHands como motor, gate humano:** usar OpenHands para *implementar*, pero
   dejar el **merge** como decisión humana (branch protection).
3. **Autonomía por zona:** dejar autónomas solo unidades sin rutas protegidas
   (ej. U0 models/tests, MD0 dashboard) y mantener HITL estricto en
   `flows`/`specs`/`infra`. El catálogo cerrado de flows hace esto viable.

---

## 6. Cuándo reconsiderar OpenSymphony

- **Hoy (U0–U4):** el arnés propio es la elección correcta.
- **Reconsiderar si:** el backlog crece a *decenas de issues repetitivos y de bajo
  riesgo* (ej. selectores, flows rutinarios post-MVP) donde la supervisión humana
  se vuelve el cuello de botella.
- **Paso intermedio natural** antes de pensar en el daemon: explotar **worktrees +
  background agents** de Claude Code para paralelizar el arnés propio.

---

## Resumen

- **Conceptualmente son primos:** mismo backbone (Linear + task package).
- **Operativamente son opuestos:** conducido-HITL vs autónomo-flota.
- **Para TestPilot la diferencia importa por *fit de gobernanza*, no por potencia:**
  los invariantes y rutas protegidas piden HITL → arnés propio.
- **Y el malentendido se resuelve así:** OpenSymphony-producto sí genera código
  desde Linear; pero en este repo solo se usó su skill de *publicación*, no su
  motor de ejecución.

### Relacionados
- [`opensymphony-y-linear.md`](opensymphony-y-linear.md) — cómo encaja Linear y el skill.
- [`glosario.md`](glosario.md) — términos (MCP, Skill, Subagente, arnés).
