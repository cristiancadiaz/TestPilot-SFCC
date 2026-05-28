# Tech Stack Decisions — MD0 Dashboard Web Interno

## Decisión D-MD0-01: HTML + Vanilla JS vs React vs Vue

### Contexto
El dashboard tiene 5 pantallas con formularios, tablas, polling, y renderizado de reportes. No requiere SPA compleja (sin enrutamiento profundo, sin estado global compartido entre pantallas, sin componentes ricamente interactivos).

### Opciones consideradas

| Opción | Pros | Contras |
|---|---|---|
| **HTML + Vanilla JS + Fetch API** | Cero build pipeline; un solo archivo HTML por pantalla; despliegue trivial; cero dependencias | Más boilerplate en renderizado; sin componentización; difícil escalar a >5 pantallas |
| **React + Vite** | Componentización; ecosystem maduro; muchos devs lo saben; HMR rápido | Build pipeline (Vite); ~150 KB bundle base; overhead de aprendizaje para QA |
| **Vue 3 + Vite** | Más ligero que React; sintaxis cercana a HTML/JS plano | Menos adoptado en el equipo PASH; necesita justificación |
| **HTMX + Jinja** | Server-side rendering; menos JS; integra natural con FastAPI | Acopla frontend al backend; cambios de UI requieren redeploy backend |

### Decisión recomendada para alineación con equipo
**React + Vite + TypeScript + Tailwind CSS**

**Razones:**
1. **Adopción del equipo:** la mayoría de devs PASH tienen experiencia React; reduce ramp-up.
2. **Componentización:** facilita reusar el componente `<TrafficLight>`, `<RunCard>`, `<StepRow>` en P3/P4/P5.
3. **Type safety:** TypeScript reduce errores de integración con contratos del backend (los modelos del backend se proyectan como interfaces TS).
4. **Tailwind:** clases utilitarias evitan diseñar CSS desde cero; el dashboard es funcional, no de marca.
5. **Vite:** build rápido (<2 s en dev), bundle optimizado (~200 KB gzipped target).

**Trade-off aceptado:** introduce build pipeline (que U0 no tenía); se mitiga con un `Dockerfile` separado para el dashboard que se construye en CI.

---

## Decisión D-MD0-02: Real-time updates — Polling vs SSE vs WebSocket

### Contexto
P3 (Vista en Tiempo Real) requiere actualizar estado de run cada pocos segundos mientras corre.

### Opciones

| Opción | Pros | Contras |
|---|---|---|
| **Polling HTTP cada 3 s** | Simple; sin estado en backend; robusto a desconexión; escalable | Carga backend en idle (mínima con cap de 3 s) |
| **Server-Sent Events (SSE)** | Push real-time; menos requests; conexión persistente | Requiere endpoint dedicado en FastAPI; complejidad de manejo de reconnect |
| **WebSocket** | Bidireccional; mínimo overhead | Overkill para flujo unidireccional read-only; complejo de operar |

### Decisión
**Polling cada 3 s con jitter ±500 ms** (NFR-MD0-P2).

**Razones:**
- Pasos típicos duran 5–30 s → 3 s de cadencia es indistinguible de real-time para el usuario.
- ~3 usuarios simultáneos × 20 polls/min × 3 endpoints = ~180 req/min de overhead. Aceptable.
- Cero estado en backend; cualquier instancia FastAPI responde.
- Robustez: si la red se cae 10 s, se pierden ~3 polls — recovery automático al volver.

**Cuándo migrar a SSE:** cuando se tengan >20 usuarios concurrentes en P3, o cuando la cadencia deseada baje a <1 s.

---

## Decisión D-MD0-03: Estado del cliente — Local hooks vs Redux

### Contexto
El dashboard tiene poca data compartida entre pantallas. P1, P2, P5 son independientes. P3 → P4 comparten `run_id` (via URL). P1 → P2 comparten lista de ambientes (puede refetch).

### Decisión
**Estado local con React hooks** (`useState`, `useEffect`, custom hooks como `usePolling`, `useEnvironments`).

**Sin Redux, Zustand, ni Recoil en MVP.**

**Razón:** overhead de configurar store global no se justifica con 5 pantallas. Si emerge necesidad real (ej. presence de N usuarios mirando el mismo run, notificaciones globales), revisar en post-MVP.

---

## Decisión D-MD0-04: Hosting del dashboard

### Opciones

| Opción | Pros | Contras |
|---|---|---|
| **FastAPI sirve estáticos** (mismo proceso) | Un solo deploy; mismo origen, sin CORS | Acopla deploy del frontend al backend |
| **S3 + CloudFront** (estáticos separados) | Deploy independiente; CDN; cache fuerte | Requiere setup CORS; otra infra a operar |
| **Docker estático nginx** (sidecar en mismo ECS task) | Deploy separable; sin AWS extra | Más recursos por task |

### Decisión MVP
**FastAPI sirve estáticos del dashboard build** desde `src/dashboard/dist/`.

**Razón:**
- Mismo origen → sin configuración CORS.
- Un solo deploy en MVP — reduce coordinación.
- ~200 KB bundle no sobrecarga FastAPI.
- Decisión revisable en sprint 4 si el equipo necesita ciclos de deploy frontend más rápidos.

**Configuración:**
```python
# en src/api/main.py
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="src/dashboard/dist", html=True), name="dashboard")
```

---

## Decisión D-MD0-05: Build pipeline para el dashboard

### Decisión
- **Build local:** `pnpm install && pnpm run build` → output a `src/dashboard/dist/`.
- **CI:** mismo comando antes del `docker build` del backend; los archivos `dist/` se copian al image.
- **No subir `dist/` al repo** — se construye siempre.

**Tooling fijado:**
- Node 20 LTS
- pnpm 9 (lockfile commited)
- Vite 5
- TypeScript 5.4
- Tailwind 3.4

---

## Resumen de stack final para MD0

| Capa | Tecnología | Versión pinned |
|---|---|---|
| Lenguaje | TypeScript | 5.4.x |
| Framework | React | 18.3.x |
| Build | Vite | 5.4.x |
| Estilos | Tailwind CSS | 3.4.x |
| HTTP client | Fetch API (nativo) | — |
| Testing | Vitest + React Testing Library | 1.x / 16.x |
| Lint | ESLint + Prettier | 9.x / 3.x |
| Package mgr | pnpm | 9.x |
| Runtime hosting | FastAPI StaticFiles | — |

**Total dependencies estimadas:** ~25 direct, ~400 transitive (estándar React+Vite). Auditadas con `pnpm audit` en CI (NFR-MD0-S1).
