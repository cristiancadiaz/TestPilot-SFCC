# Objetivo de la tarea — 2 sesiones paralelas en Antigravity

> Documento de referencia para tener presente **por qué** estamos ejecutando 2 misiones paralelas en Antigravity, no solo cómo. Si en algún momento dudas si vale la pena el esfuerzo, vuelve aquí.

No es "hacer 2 cosas a la vez" — eso sería superficial. El ejercicio existe para hacerte experimentar **un cambio de paradigma** en cómo se construye software con agentes. Hay 5 objetivos apilados.

---

## 1. Cambiar la unidad de trabajo: del commit al artifact

En desarrollo tradicional, **un commit** es la unidad mental: escribes código → commiteas → revisas → mergeas. Lineal.

En desarrollo agéntico, **un artifact** (diff completo + tests + verificación) es la unidad. Tú no escribes el código — recibes un entregable completo y lo revisas.

Con **una sola sesión** puedes seguir engañándote pensando que estás "asistido" (autocomplete glorificado). Con **dos** ya no puedes leer el chat de ambas a la vez — te obliga a tratar cada sesión como una caja negra que produce un diff. Es la diferencia entre supervisar a un becario que te interrumpe vs. recibir el PR terminado de un mid-level.

> **En TestPilot:** Mission 1 te entrega `src/api/` como un PR cerrado. Mission 2 te entrega `src/baseline/` como otro PR cerrado. Tú no escribiste código — revisaste 2 artefactos.

---

## 2. Forzarte a diseñar trabajo verdaderamente independiente

Para que 2 agentes corran en paralelo sin pisarse, **tú tienes que descomponer el trabajo bien**. Esto es ingeniería real, no prompt engineering.

Si las 2 misiones tocaran los mismos archivos, no estarías haciendo paralelismo — estarías haciendo un merge hell. La calidad de tu decomposición se vuelve visible: si fallaste, lo ves en el conflicto.

> **En TestPilot:** Mission 1 toca solo `src/api/` y `tests/test_api_*`. Mission 2 toca solo `src/baseline/` y `tests/test_baseline_*`. Una única colisión esperada (`pyproject.toml`) — y porque es aditiva, es trivial de resolver. Eso es buena descomposición.

Esto es exactamente el skill que necesitas para liderar un equipo: saber partir el trabajo de modo que 3 personas (o 3 agentes) trabajen sin coordinarse minuto a minuto.

---

## 3. Internalizar la decision matrix (Claude Code vs Antigravity)

No hay una herramienta "mejor". Hay tareas distintas:

| Tarea | Herramienta | Por qué |
|---|---|---|
| Debugging de un test que falla *ahora* | Claude Code | Necesitas iterar segundo a segundo, ver stdout, intervenir |
| Refactor que toca 30 archivos *bien acotado* | Claude Code | Mantienes control línea por línea |
| Crear un módulo nuevo *bien especificado* | Antigravity | Lo lanzas y vuelves cuando hay diff |
| Implementar 3 features paralelas para revisar al final del día | Antigravity ×3 | Paralelismo real |
| Conversación exploratoria ("¿qué pasa si…?") | Claude Code | Antigravity asume que ya sabes qué quieres |

**No puedes internalizar esto leyéndolo — tienes que sentir la diferencia.** Las 2 sesiones paralelas son el primer "click" experiencial: te das cuenta de que mientras Antigravity trabaja, tú no estás pegado al chat. Estás haciendo otra cosa.

---

## 4. Demostrar control con `AGENTS.md` / `PRODUCT.md` / `specs/`

Esta es la prueba ácida del **Context Engineering** que se planteó en la sección 2 del codelab.

Dos agentes distintos, en sesiones distintas, **leyendo los mismos archivos de contexto**, deberían respetar los mismos invariantes:

- Cero contaminación
- Catálogo cerrado
- JSON Schema gate
- Module boundaries (Mission 1 no debe llamar boto3 directo; Mission 2 no debe llamar Anthropic SDK directo)

Si los 2 diffs salen coherentes entre sí sin que tú hayas re-explicado nada, **es la evidencia de que tu context engineering funciona.** Si salen contradictorios, sabes que `AGENTS.md` tiene huecos.

> **En TestPilot:** ambas misiones referencian `AGENTS.md`, `PRODUCT.md` y `specs/*.json`. Si Mission 1 expone un endpoint que acepta `environment_id: "production"`, sabes que tu contexto falló. Si Mission 2 emite alertas yellow con 5 runs, también. Las 2 sesiones son tu test cruzado del contexto.

---

## 5. Cambiar el rol del developer: de escritor a reviewer

La consecuencia económica del agentic development no es que escribes código más rápido — es que **dejas de escribir código**. Tu trabajo se vuelve:

- Diseñar el contexto (`AGENTS.md`, `PRODUCT.md`, schemas).
- Acotar misiones (los archivos en `docs/antigravity-missions/`).
- Aprobar/rechazar planes propuestos.
- Revisar diffs.
- Mantener invariantes.

Con **una sesión**, sigues sintiendo que "escribes con asistencia". Con **dos**, no puedes — no hay tiempo de leer ambas a la vez. Te obliga a confiar en el artefacto y revisar al final.

Es la transición **escritor → arquitecto/revisor**. Y es el cambio de identidad profesional que el curso quiere que sientas en carne propia.

---

## Lo que el codelab espera evidenciar (concreto)

Cuando entregues los 2 planes + 2 diffs, estás demostrando 4 cosas a la vez:

1. ✅ Sabes descomponer trabajo en unidades independientes.
2. ✅ Tu contexto (`AGENTS.md`, `PRODUCT.md`, `specs/`) es suficientemente bueno para que 2 agentes lo respeten sin tu intervención.
3. ✅ Entiendes cuándo Antigravity es la herramienta correcta (vs. Claude Code).
4. ✅ Cambiaste de modo "escritor de código" a modo "revisor de artefactos".

---

## La pregunta de fondo que quiere responder el ejercicio

> *"¿Puedo confiar lo suficiente en mi setup como para soltar 2 agentes en paralelo y aceptar que voy a recibir 2 PRs listos para revisar — sin interrumpirlos?"*

Si la respuesta es **sí**, has internalizado el paradigma. Si la respuesta es **"tuve que intervenir constantemente"**, tu context engineering todavía no está donde debería.

Las 2 sesiones son, esencialmente, un examen de **qué tan bueno es tu setup agéntico** — disfrazado de tarea de implementación.

---

*Documento de referencia · Clase 3 Hardcore AI · TestPilot SFCC · 2026-05-27*
