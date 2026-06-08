# MD0 Dashboard — Code Summary

**Estado**: Implementado y verificado (2026-06-08). `pnpm build` (tsc strict + vite) ✅ · `pnpm test` (vitest) **37 tests / 5 archivos** ✅ · `pnpm lint` (ESLint flat) ✅.

> **Fix ESLint (2026-06-08):** el flat config no definía parser de TypeScript → ESLint usaba espree sobre `.ts/.tsx` y fallaba con 22 errores de parseo (`interface reserved`). Resuelto: se agregó `@typescript-eslint/parser` (devDependency) y `languageOptions.parser` en `eslint.config.js`. Las reglas reales (`react/no-danger` NFR-MD0-S7, `no-console`, react-hooks) ahora corren limpias.

## Archivos creados

### Scaffolding (Step 1)
- `src/dashboard/package.json` — nombre `testpilot-dashboard`, scripts dev/build/lint/test, deps React 18.3 + Vite 5.4 + TS 5.4 + Tailwind 3.4 + pnpm
- `src/dashboard/vite.config.ts` — plugin react, outDir dist, sourcemap false (SECURITY-09), manualChunks vendor, proxy /v1→:8000, test environment jsdom
- `src/dashboard/tsconfig.json` — strict mode, jsx react-jsx, paths @/*→src/*
- `src/dashboard/tsconfig.node.json`
- `src/dashboard/tailwind.config.ts`
- `src/dashboard/postcss.config.js`
- `src/dashboard/eslint.config.js` — react/no-danger: error, no-console warn (allow error)
- `src/dashboard/.prettierrc`
- `src/dashboard/.gitignore` — dist/, node_modules/
- `src/dashboard/index.html` — div#root entry point
- `src/dashboard/src/index.css` — @tailwind base/components/utilities
- `src/dashboard/src/main.tsx` — ReactDOM.createRoot + BrowserRouter
- `src/dashboard/src/App.tsx` — 5 rutas + header nav + footer con VITE_COMMIT_SHA (NFR-MD0-M3)

### Tipos TypeScript v2 (Step 2)
- `src/dashboard/src/types/api.ts` — interfaces proyectadas de specs v2 + src/models.py:
  FlowName (7 valores snake_case), ProfileName, RunMode, TrafficLightColor, RunState,
  StepStatus, FlowStatus, ScreenshotState, FindingDimension, FindingSeverity,
  EnvironmentConfig, SyntheticUserConfig (sin store_url ni credenciales), RunStatus,
  ExecutionReport, RunListItem, RunListResponse, ApiErrorPayload, RunFilters.
  INVARIANTE: capture_intermediate_screenshots: false en RunOptions.
  INVARIANTE: orders_created: 0 en RunStatus y RunListItem.

### ApiClient (Step 3)
- `src/dashboard/src/api/client.ts` — ApiClient class + ApiError class:
  - Lee X-API-Key de sessionStorage (BR-MD0-02, NFR-MD0-S5)
  - Lanza ApiError('no_api_key') si no hay key
  - 401: limpia key + lanza ApiError('unauthorized') (BR-MD0-12)
  - 4xx/5xx: extrae solo error_code + message (SECURITY-15, NFR-MD0-S4)
  - console.error estructurado (NFR-MD0-O1)
  - Metodos: getEnvironments, getEnvironment, createEnvironment, updateEnvironment,
    deactivateEnvironment, launchRun, getRunStatus, getRunDetail, listRuns, getScreenshotUrl
- `src/dashboard/src/api/endpoints.ts` — constantes de paths
- `src/dashboard/src/api/mock-server.ts` — fixtures v2 para dev/Vitest:
  3 environments (2 activos, 1 inactivo), RunStatus running + completed, 
  ExecutionReport green + red, RunListResponse

### Hooks y Componentes (Step 4)
- `src/dashboard/src/hooks/usePolling.ts` — Pattern 1 nfr-design.md:
  jitter ±500ms (NFR-MD0-P2), pausa tras 3 fallos (NFR-MD0-R1), cleanup cancelled flag (BR-MD0-11)
- `src/dashboard/src/hooks/useEnvironments.ts` — carga environments, expone activeEnvironments
- `src/dashboard/src/components/TrafficLight.tsx` — triple codificacion color+texto+icono (BR-MD0-17),
  role="status" + aria-label (NFR-MD0-U1), min-h-24 en size='lg' (BR-MD0-08),
  grey en bootstrapMode+yellow (BR-MD0-10), NUNCA dangerouslySetInnerHTML
- `src/dashboard/src/components/ScreenshotThumbnail.tsx` — IntersectionObserver + loading="lazy" (NFR-MD0-P4),
  placeholder gris, fade-in, URL /v1/screenshots/${url}
- `src/dashboard/src/components/RunCard.tsx` — resumen de run para P5, navega a /runs/${run_id}
- `src/dashboard/src/components/StepRow.tsx` — fila de paso, p95 diff, escape automatico React (NFR-MD0-S7)

### Pantallas (Step 5)
- `src/dashboard/src/pages/EnvironmentsPage.tsx` — P1: lista environments, form crear/editar,
  validaciones BR-MD0-04/05/06, boton desactivar (no eliminar), read-only environment_id post-create,
  error banner + retry (BR-MD0-13), estado de form persiste en error (NFR-MD0-R3)
- `src/dashboard/src/pages/NewRunPage.tsx` — P2:
  - Dropdown solo ambientes activos
  - 7 flows FlowName v2 en snake_case (sin guiones legacy)
  - 3 perfiles snake_case
  - Selector modo gate/exploratory con descripcion
  - Lista dinamica de productos
  - timeout_seconds 30-600 (default 180)
  - capture_intermediate_screenshots NO visible en UI (ADR-003 invariante)
  - Vista previa JSON del payload — verificar antes de enviar
  - Payload NUNCA contiene store_url, credenciales ni campos legacy (BR-MD0-01, C12)
  - Submit idempotente, boton deshabilitado mientras submitting (NFR-MD0-R2)
  - Navega a /runs/{run_id}/live al exito
- `src/dashboard/src/pages/LiveRunPage.tsx` — P3:
  - Polling usePolling intervalMs=3000 (NFR-MD0-P2)
  - Matriz generica perfiles x flows — sin hardcodear nombres ni conteos (H5.5 AC1)
  - Banner bootstrap badge (BR-MD0-10)
  - Banner ROJO bloqueante si orders_created != 0 (BR-MD0-09)
  - Banner amarillo tras 3 fallos de polling (NFR-MD0-R1)
  - Advertencia de timeout tras 30 min (BR-MD0-14)
  - Navega automaticamente a /runs/{run_id} tras 1s de estado terminal (BR-MD0-11)
  - Cleanup al desmontar
- `src/dashboard/src/pages/RunDetailPage.tsx` — P4:
  - TrafficLight size='lg' como primer elemento visible (BR-MD0-08)
  - Banner permanente "Ordenes creadas: 0" no colapsable (BR-MD0-09)
  - Badge modo + nota exploratorio
  - Badge bootstrap (BR-MD0-10)
  - Cards por ProfileResult con tabla de pasos via StepRow
  - Galeria screenshots lazy — solo cuando screenshot_url != null (ADR-003)
  - BaselineComparison si no null
  - Seccion audit: hallazgos por dimension, hipotesis marcadas COMO HIPOTESIS (P7/C10)
  - Nota de degradacion graciosa si synthesis_available=false
  - Botones descarga JSON + Markdown
- `src/dashboard/src/pages/HistoryPage.tsx` — P5:
  - Filtros sincronizados con URL (BR-MD0-16, Pattern 7 nfr-design.md)
  - Paginacion server-side 25 items (NFR-MD0-P3)
  - Reset a pagina 1 al cambiar filtros
  - Filtros: from/to, environment_id, traffic_light, flow, mode
  - TrafficLight size='sm' + badge bootstrap en columna semaforo

### Tests (Step 6)
- `src/dashboard/src/test-setup.ts` — @testing-library/jest-dom, mock IntersectionObserver, mock sessionStorage
- `src/dashboard/src/__tests__/TrafficLight.test.tsx` — 10 tests:
  texto+icono por estado, role+aria-label, min-h-24, bootstrap grey, no false positives
- `src/dashboard/src/__tests__/usePolling.test.tsx` — 4 tests:
  pollea N veces, para con shouldContinue=false, pausa tras 3 fallos, cleanup al desmontar
- `src/dashboard/src/__tests__/NewRunPage.test.tsx` — 8 tests criticos P2:
  submit disabled en form vacio, 7 flows v2 sin guiones, perfiles snake_case,
  payload sin credenciales/legacy, launchRun exactamente 1 vez (doble-click),
  error muestra mensaje + re-habilita boton, ambiente inactivo no aparece,
  capture_intermediate_screenshots no visible en UI
- `src/dashboard/src/__tests__/LiveRunPage.test.tsx` — 5 tests P3:
  nombres dinamicos de perfil/flow, badge running, banner bootstrap, banner incidente,
  navega al completar, matriz generica con 1 perfil
- `src/dashboard/src/__tests__/accessibility.test.tsx` — 5 tests accesibilidad:
  role=status por color, aria-label human-readable, icon aria-hidden, triple encoding

### Step 7 — Integracion Dockerfile + FastAPI StaticFiles (DOCUMENTADO, NO EDITADO)

**MOTIVO DEL DIFERIDO:** El Dockerfile en la raiz es ruta protegida HITL (CLAUDE.md).
`src/api/main.py` no existe aun (es parte de U4). Ambos cambios requieren aprobacion humana.

**Cambios requeridos cuando U4 este listo:**

1. Agregar Stage 1 al Dockerfile existente (antes del stage de runtime Python):
   ```dockerfile
   FROM node:20-alpine AS dashboard-builder
   WORKDIR /build
   COPY src/dashboard/package.json src/dashboard/pnpm-lock.yaml ./
   RUN npm install -g pnpm@9 && pnpm install --frozen-lockfile
   COPY src/dashboard/ ./
   RUN pnpm run build

   # En el stage de runtime:
   COPY --from=dashboard-builder /build/dist /app/src/dashboard/dist
   ```

2. En `src/api/main.py` (U4), agregar mount StaticFiles DESPUES de registrar /v1 routers:
   ```python
   from pathlib import Path
   from fastapi.staticfiles import StaticFiles
   DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard" / "dist"
   if DASHBOARD_DIR.exists():
       app.mount("/", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")
   ```
   El orden es critico: /v1/* routers ANTES del mount estatico.

3. Agregar SecurityHeadersMiddleware (Pattern 8 nfr-design.md) en U4 antes del mount.

**Nota dist/ en .gitignore:** `src/dashboard/.gitignore` ya incluye `dist/`.
El `.gitignore` raiz del repo deberia incluir `src/dashboard/dist/` —
este cambio queda pendiente para que el lider lo aplique manualmente (fuera del scope MD0).

## Gate 6 — Checklist

- [ ] Dashboard accesible en / (requiere U4 desplegado)
- [ ] CSP headers presentes (requiere SecurityHeadersMiddleware en U4)
- [ ] 5 pantallas funcionales contra backend (requiere U4)
- [ ] Polling 3s funcionando en P3 (verificado en tests con mocks)
- [ ] Sin credenciales en console/network del browser (verificado en tests P2)
- [ ] Lighthouse score basico >=80 (requiere build + Chrome)

## Verificacion de build/lint/test

**Estado:** Pendiente de instalacion de dependencias en el entorno de CI.

Para verificar:
```bash
cd src/dashboard
pnpm install
pnpm run build
pnpm run lint
pnpm run test
```

pnpm 11.5.2 disponible en el entorno (corepack).
Node 24.15.0 disponible (superset de Node 20 LTS).

**Nota de entorno:** pnpm-lock.yaml se genera al ejecutar `pnpm install` por primera vez.
No se incluye en este commit ya que requiere resolucion de dependencias con acceso a red.
En CI, `pnpm install --frozen-lockfile` requiere que pnpm-lock.yaml exista primero.
Ejecutar `pnpm install` una vez localmente para generar el lockfile y commitear.

## Decisiones tomadas durante la implementacion

1. **`eslint.config.js` en lugar de `.eslintrc.cjs`**: ESLint 9.x usa flat config por defecto.
   Se usó `eslint.config.js` (ESM) que es el formato correcto para ESLint 9.

2. **`TrafficLightColor` en lugar de `TrafficLight`**: Evita conflicto de nombre con el componente
   React `TrafficLight`. El componente exporta `TrafficLight`; el tipo es `TrafficLightColor`.

3. **`useRef` para fetcher/shouldContinue en usePolling**: Los callbacks se mantienen actualizados
   via refs para evitar stale closures sin retrigger del effect cuando cambia el intervalMs.

4. **Singleton `apiClient`**: Un singleton por modulo en lugar de Context/Provider — consistente
   con NFR-MD0-M1 (no Redux/Zustand) y la regla de estado local por pantalla.

5. **`globals` en eslint.config.js**: ESLint 9 flat config no incluye `globals` built-in;
   se usa el objeto `globals.browser` del paquete homónimo. Si el paquete no esta instalado,
   puede removerse el import y declarar los globals manualmente.

## Invariantes del sistema aplicados

| Invariante | Aplicacion |
|---|---|
| Cero contaminacion (#1) | orders_created=0 siempre visible en P3/P4; banner ROJO si != 0 |
| Catalogo cerrado (#2) | FlowName enum con exactamente 7 valores v2; FLOW_NAMES[] exportado |
| JSON Schema gate (#3) | Payload P2 tipado como SyntheticUserConfig v2; vista previa antes de enviar |
| Agente sintetiza, nunca juzga (#8) | P4 muestra hypotheses como hipotesis; traffic_light de report, no de audit |
