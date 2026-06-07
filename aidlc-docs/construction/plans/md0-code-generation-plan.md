# MD0 Dashboard Web Interno — Code Generation Plan

> DEUDA DE RECONCILIACION: Los documentos `md0/functional-design/domain-entities.md`,
> `business-logic-model.md` y `business-rules.md` son pre-realineacion. Usan nombres
> con guiones (`mobile-co`, `checkout-full`) y campos inexistentes en v2
> (`screenshot_on_success`, `screenshot_on_error`). Este plan usa el contrato v2 real
> (specs/ v2, aprobado HITL 2026-06-03). Reconciliar esos documentos es deuda aparte
> — no bloquea la implementacion.

---

## Unit Context

| Atributo | Valor |
|---|---|
| Tipo | Greenfield (nueva carpeta `src/dashboard/`) |
| Stack | TypeScript 5.4 + React 18.3 + Vite 5.4 + Tailwind 3.4 + pnpm 9 |
| Testing | Vitest 1.x + React Testing Library 16.x |
| Lint | ESLint 9.x + Prettier 3.x |
| Ubicacion de codigo | `src/dashboard/` |
| Salida de build | `src/dashboard/dist/` (NO commited al repo — generado en CI) |
| Hosting | FastAPI `StaticFiles` desde `src/dashboard/dist/` (Decision D-MD0-04) |
| Dependencia de runtime | Consume API de U4 via mocks hasta que U4 este listo |
| Estrategia dev | Vite dev server en `:5173` con proxy `/v1 -> :8000`; U4 puede estar ausente |
| Node runtime | Node 20 LTS |

**Dependencias con otros artefactos:**

- U0 (`src/models.py`): fuente de verdad de tipos; MD0 proyecta interfaces TS a partir de
  los modelos Pydantic y de los schemas v2 en `specs/`.
- U4 (API Endpoints): MD0 consume sus endpoints REST. Durante el desarrollo de MD0 se
  usan mocks; integracion real ocurre cuando U4 este desplegado.
- `specs/synthetic-user-config.schema.json` (v2): contrato de `POST /v1/run`.
- `specs/execution_report.schema.json` (v2): contrato del reporte que renderiza P4.

---

## Steps

### Step 1: Scaffolding Vite + React + TS + Tailwind + pnpm en `src/dashboard/` [ ]

Crear el arbol de directorios y archivos de configuracion base. Ningun archivo de
aplicacion todavia — solo la estructura y el toolchain.

**Archivos a crear:**

```
src/dashboard/
├── package.json
├── pnpm-lock.yaml           (generado por pnpm install; commited)
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── tailwind.config.ts
├── postcss.config.js
├── .eslintrc.cjs            (ESLint 9, react/no-danger: error, no console fuera de error)
├── .prettierrc
├── index.html               (entry point Vite — incluye div#root)
├── src/
│   ├── main.tsx             (ReactDOM.createRoot + BrowserRouter)
│   ├── App.tsx              (routing de 5 rutas)
│   ├── api/
│   ├── components/
│   ├── hooks/
│   ├── pages/
│   └── types/
└── .gitignore               (dist/ node_modules/)
```

**Contenido clave de `package.json`:**
- `name`: `testpilot-dashboard`
- Scripts: `dev`, `build` (`tsc && vite build`), `preview`, `lint`, `test`
- `dependencies`: `react@18.3.x`, `react-dom@18.3.x`, `react-router-dom@6.x`
- `devDependencies`: `vite@5.4.x`, `@vitejs/plugin-react`, `typescript@5.4.x`,
  `tailwindcss@3.4.x`, `postcss`, `autoprefixer`, `@types/react`, `@types/react-dom`,
  `vitest@1.x`, `@testing-library/react@16.x`, `@testing-library/jest-dom`,
  `@testing-library/user-event`, `jsdom`, `eslint@9.x`, `prettier@3.x`,
  `eslint-plugin-react`, `eslint-plugin-react-hooks`

**Contenido clave de `vite.config.ts`:**
- Plugin `@vitejs/plugin-react`
- `build.outDir`: `dist`
- `build.sourcemap`: `false` (SECURITY-09 — no exponer source maps en prod)
- `build.rollupOptions.output.manualChunks`: `{ vendor: ['react', 'react-dom'] }`
- `server.proxy`: `{ '/v1': 'http://localhost:8000' }` (dev proxy a FastAPI)
- `test.environment`: `jsdom`
- `test.setupFiles`: `['./src/test-setup.ts']`

**Contenido de `tsconfig.json`:** strict mode, `jsx: react-jsx`, paths alias `@/*` -> `src/*`.

**Verificacion del step:**
- `cd src/dashboard && pnpm install` — sin errores
- `pnpm run build` — genera `dist/` con `index.html` + assets
- `pnpm run lint` — exit 0
- `pnpm run test` — 0 tests, exit 0 (suite vacia)

---

### Step 2: Tipos TypeScript proyectados del contrato v2 (`src/dashboard/src/types/api.ts`) [ ]

Crear las interfaces TS que replican los contratos v2 de los schemas JSON y los modelos
Pydantic del backend. El dashboard es un cliente puro — nunca define su propio modelo de
dominio.

**IMPORTANTE — nombres v2 correctos (snake_case):**
- Perfiles: `mobile_co`, `desktop_co`, `desktop_ec` (NO guiones)
- Flows: `checkout_full`, `checkout_card_declined`, `search_and_filter`,
  `browse_discounted_products`, `pdp_validation`, `cart_review`, `full_journey`
- Modos: `gate`, `exploratory`
- Campos de config: `schema_version`, `environment_id`, `flows`, `profiles`, `products`,
  `options.timeout_seconds`, `options.capture_intermediate_screenshots` (const false)
- NO existen `screenshot_on_success` ni `screenshot_on_error` en v2

**Interfaces a definir en `types/api.ts`:**

```typescript
// --- Enums y literales ---
export type FlowName =
  | 'checkout_full'
  | 'checkout_card_declined'
  | 'search_and_filter'
  | 'browse_discounted_products'
  | 'pdp_validation'
  | 'cart_review'
  | 'full_journey';

export type ProfileName = 'mobile_co' | 'desktop_co' | 'desktop_ec';
export type RunMode = 'gate' | 'exploratory';
export type TrafficLight = 'green' | 'yellow' | 'red';
export type RunState = 'queued' | 'running' | 'completed' | 'failed';
export type StepStatus = 'success' | 'failed' | 'skipped';
export type FlowStatus = 'success' | 'failed' | 'error';
export type ScreenshotState = 'fail' | 'final' | 'finding' | 'critical';
export type FindingDimension =
  | 'commerce_integrity'
  | 'performance'
  | 'locale_correctness'
  | 'accessibility'
  | 'client_health'
  | 'content_integrity';
export type FindingSeverity = 'info' | 'warning' | 'critical';

// --- Config de ambiente ---
export interface EnvironmentConfig {
  environment_id: string;            // ^[a-z][a-z0-9_-]{2,31}$, read-only post-create
  display_name: string;
  store_url: string;                 // https URL
  env_access_secret_path: string;
  shopper_secret_path: string;
  anti_bot_whitelisted: boolean;
  active: boolean;
  created_at: string;                // ISO 8601
  updated_at: string;
}

// --- Request de run (POST /v1/run) ---
export interface SyntheticUserConfig {
  schema_version: 'v2';
  environment_id: string;
  flows: FlowName[];
  mode?: RunMode;                    // default 'gate' si omitido
  profiles: ProfileName[];
  products: Array<{
    search_term: string;
    validate_variant?: boolean;
  }>;
  options?: {
    timeout_seconds?: number;
    capture_intermediate_screenshots: false;  // INVARIANTE — siempre false
  };
}

// --- Estado de run en vivo (GET /v1/runs/{id}/status) ---
export interface ProfileRunStatus {
  profile_id: ProfileName;
  flow_name: FlowName;
  state: 'pending' | 'running' | 'success' | 'failed' | 'error';
  current_step: string | null;
  steps_completed: number;
  steps_total: number;
  duration_ms: number;
}

export interface RunStatus {
  run_id: string;
  state: RunState;
  mode: RunMode;
  started_at: string;
  environment_id: string;
  profile_statuses: ProfileRunStatus[];
}

// --- Reporte completo (GET /v1/runs/{id}) ---
export interface StepResult {
  name: string;
  status: StepStatus;
  phase?: 'setup' | 'flow';
  duration_ms: number;
  error: string | null;
  screenshot_url: string | null;
  screenshot_state: ScreenshotState | null;
  finding_dimension: FindingDimension | null;
}

export interface FlowResult {
  flow_name: FlowName;
  status: FlowStatus;
  steps: StepResult[];
  duration_ms: number;
}

export interface BrowserProfile {
  name: ProfileName;
  viewport_width: number;
  viewport_height: number;
  locale: string;
  user_agent: string;
  is_mobile: boolean;
}

export interface ProfileResult {
  profile: BrowserProfile;
  flow_result: FlowResult;
  traffic_light: TrafficLight;
  network_summary: NetworkSummary | null;
}

export interface BaselineComparison {
  p95_ms: number;
  current_ms: number;
  bootstrap_mode: boolean;
  runs_count: number;
}

export interface AuditFinding {
  dimension: FindingDimension;
  severity: FindingSeverity;
  page_url: string;
  step: string | null;
  data: Record<string, unknown>;
  evidence_refs: string[];
  requires_human_review: boolean;
}

export interface AuditHypothesis {
  text: string;
  confidence: number;
  requires_human_review: boolean;
}

export interface AuditReport {
  findings: AuditFinding[];
  hypotheses?: AuditHypothesis[];
  synthesis_available: boolean;
  document_md_url: string | null;
}

export interface NetworkSummary {
  total_requests: number;
  failed_requests: number;
  controllers?: Array<{ pattern: string; count: number; p95_ms: number }>;
  web_vitals?: { lcp_ms: number | null; cls: number | null; ttfb_ms: number | null } | null;
  har_url?: string | null;
}

export interface ExecutionReport {
  run_id: string;
  environment_id: string;
  mode: RunMode;
  started_at: string;
  finished_at: string;
  duration_ms: number;
  traffic_light: TrafficLight;
  bootstrap_mode: boolean;
  profile_results: ProfileResult[];
  baseline_comparison: BaselineComparison | null;
  audit: AuditReport | null;
}

// --- Historial (GET /v1/runs) ---
export interface RunListItem {
  run_id: string;
  environment_id: string;
  display_name: string;
  started_at: string;
  finished_at: string;
  duration_ms: number;
  traffic_light: TrafficLight;
  bootstrap_mode: boolean;
  mode: RunMode;
  profiles_executed: ProfileName[];
  flows_executed: FlowName[];
  orders_created: 0;                // invariante — siempre 0
}

export interface RunListResponse {
  items: RunListItem[];
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
}

// --- Errores de API ---
export interface ApiErrorPayload {
  error_code: string;
  message: string;
  details?: Record<string, unknown>;
}
```

**Verificacion del step:**
- `pnpm run build` — compila sin errores de tipos
- Tipos cubren todos los campos requeridos de `specs/synthetic-user-config.schema.json`
  y `specs/execution_report.schema.json` v2

---

### Step 3: ApiClient con capa mockeable (`src/dashboard/src/api/client.ts`) [ ]

Implementar el cliente HTTP centralizado con autenticacion por `X-API-Key` y una capa
de mock intercambiable para el desarrollo de MD0 antes de que U4 este listo.

**Estructura de archivos:**

```
src/dashboard/src/api/
├── client.ts          (ApiClient class + ApiError class)
├── mock-server.ts     (MSW handlers o fixtures en memoria)
└── endpoints.ts       (constantes de paths + tipado de request/response)
```

**Implementacion de `client.ts`:**

La clase `ApiClient` debe:
- Leer `X-API-Key` de `sessionStorage` (clave `testpilot_api_key`)
- Lanzar `ApiError('no_api_key', ...)` si no hay key configurada
- En cada fetch: incluir `Content-Type: application/json` y `X-API-Key`
- En 401: limpiar key de `sessionStorage` y lanzar `ApiError('unauthorized', ...)`
  (BR-MD0-12)
- En 4xx/5xx: extraer `error_code` y `message` del body JSON; lanzar `ApiError`
  con esos valores; NUNCA exponer el body crudo (SECURITY-15, NFR-MD0-S4)
- Patron de submit idempotente: el caller gestiona el estado `submitting` — el client
  no lo maneja internamente

**Metodos del ApiClient:**

```typescript
// Environments
getEnvironments(): Promise<EnvironmentConfig[]>
getEnvironment(id: string): Promise<EnvironmentConfig>
createEnvironment(data: Omit<EnvironmentConfig, 'created_at' | 'updated_at'>): Promise<EnvironmentConfig>
updateEnvironment(id: string, data: Partial<EnvironmentConfig>): Promise<EnvironmentConfig>
deactivateEnvironment(id: string): Promise<void>

// Runs
launchRun(config: SyntheticUserConfig): Promise<{ run_id: string }>
getRunStatus(runId: string): Promise<RunStatus>
getRunDetail(runId: string): Promise<ExecutionReport>
listRuns(filters: RunFilters): Promise<RunListResponse>

// Screenshots (lazy)
getScreenshotUrl(runId: string, path: string): string  // retorna URL relativa /v1/...
```

**RunFilters type:**

```typescript
export interface RunFilters {
  from?: string;                     // ISO date
  to?: string;
  environment_id?: string;
  traffic_light?: TrafficLight;
  flow?: FlowName;
  mode?: RunMode;
  page?: number;
  page_size?: number;
}
```

**Capa mock (`mock-server.ts`):**
- Usar Mock Service Worker (MSW) en modo browser para dev, o fixtures en memoria para Vitest
- Fixtures de ejemplo para cada endpoint: al menos 2 environments, 1 run en estado
  `running`, 1 run terminado con `traffic_light: 'green'`, 1 run con `traffic_light: 'red'`
- La fixture de `RunStatus` debe devolver `mode: 'gate'` y nombres de perfiles en
  snake_case: `mobile_co`, `desktop_co`, `desktop_ec`
- El mock de `launchRun` devuelve `{ run_id: 'mock-uuid-1234' }` con delay simulado de 200ms

**Verificacion del step:**
- `pnpm run build` — sin errores de tipos
- Existe al menos una fixture de run con campos v2 correctos (snake_case, `mode`, sin
  `screenshot_on_success`)

---

### Step 4: Componentes core y hooks (`src/dashboard/src/components/` y `hooks/`) [ ]

Implementar los bloques reutilizables que usaran las 5 pantallas. Cada componente con
su test unitario en el mismo directorio o en `src/dashboard/src/__tests__/`.

**4a. Hook `usePolling` (`hooks/usePolling.ts`)**

Implementar segun el diseno en `nfr-design.md` (Patron 1):
- Parametros: `fetcher: () => Promise<T>`, `intervalMs: number`,
  `shouldContinue: (data: T) => boolean`
- Retorna: `{ data: T | null; error: ApiErrorPayload | null; isPolling: boolean }`
- Jitter: `Math.random() * 1000 - 500` (±500ms — NFR-MD0-P2)
- Pausa tras 3 fallos consecutivos — NFR-MD0-R1
- Cleanup con flag `cancelled` en el `useEffect` return — BR-MD0-11
- El `shouldContinue` recibe el dato y devuelve false cuando el run esta en estado terminal

**Test de `usePolling`:**
- Pollea N veces mientras `shouldContinue` retorna true
- Para cuando `shouldContinue` retorna false
- Para tras 3 fallos consecutivos
- No sigue polleando tras desmontar el componente (cleanup)

**4b. Hook `useEnvironments` (`hooks/useEnvironments.ts`)**

- Carga lista de environments al montar
- Expone: `environments`, `loading`, `error`, `refetch()`
- Solo ambientes `active=true` se exponen en el selector de P2 (filtro en hook)

**4c. Componente `<TrafficLight>` (`components/TrafficLight.tsx`)**

Implementar segun el diseno en `nfr-design.md` (Patron 3):
- Props: `color: TrafficLight`, `size?: 'sm' | 'lg'`, `bootstrapMode?: boolean`
- Triple codificacion: color de fondo + texto explicito + icono (BR-MD0-17)
- En `size='lg'`: altura minima 96px (BR-MD0-08)
- En `bootstrapMode=true && color='yellow'`: renderiza como gris — BR-MD0-10
- `role="status"` + `aria-label` para screen readers (NFR-MD0-U1)
- NUNCA `dangerouslySetInnerHTML` (NFR-MD0-S7)

**Test de `<TrafficLight>`:**
- Renderiza 'OK' en verde, 'Alerta' en amarillo, 'Fallo' en rojo
- En bootstrap mode, amarillo se renderiza gris
- Tiene `role="status"` y `aria-label` correcto

**4d. Componente `<ScreenshotThumbnail>` (`components/ScreenshotThumbnail.tsx`)**

Implementar segun el diseno en `nfr-design.md` (Patron 5):
- Props: `url: string`, `alt: string`
- Lazy load via `IntersectionObserver` (hook `useInView`) — NFR-MD0-P4
- `loading="lazy"` nativo como defensa adicional
- Placeholder gris hasta cargar; fade-in con `opacity`
- La URL se construye como `/v1/screenshots/${url}` (path relativo, mismo origen)

**4e. Componente `<RunCard>` (`components/RunCard.tsx`)**

Vista resumen de un run para P5 History. Props: `item: RunListItem`.
- Muestra: `display_name`, timestamp `started_at`, `traffic_light` (via `<TrafficLight size='sm'>`),
  `duration_ms` formateado, badge `mode` (gate vs exploratory con color diferente),
  badge `bootstrap_mode` si aplica
- Click navega a `/runs/${run_id}`

**4f. Componente `<StepRow>` (`components/StepRow.tsx`)**

Fila de paso en la tabla de P4. Props: `step: StepResult`, `p95Ms?: number`.
- Muestra: `name`, `status` (icono + texto), `duration_ms`, diferencia vs p95 si `p95Ms` disponible
- Si `screenshot_url` existe: `<ScreenshotThumbnail>` inline en miniatura
- Si `error` no es null: texto de error escapado automaticamente por React (NFR-MD0-S7)
- Color de fondo segun `status`: verde/rojo/gris para success/failed/skipped

**Verificacion del step:**
- `pnpm run test` — todos los tests de componentes pasan
- `pnpm run lint` — exit 0

---

### Step 5: Las 5 pantallas (`src/dashboard/src/pages/`) [ ]

Implementar cada pantalla como componente React conectado al `ApiClient`.
El enrutamiento usa React Router v6 con las siguientes rutas en `App.tsx`:

```
/environments          → EnvironmentsPage
/runs/new              → NewRunPage
/runs/:runId/live      → LiveRunPage
/runs/:runId           → RunDetailPage
/runs                  → HistoryPage
/                      → redirect a /runs
```

**5a. P1 — `EnvironmentsPage` (`pages/EnvironmentsPage.tsx`)**

- Lista todos los environments (activos e inactivos con badge visual)
- Formulario de creacion/edicion con validaciones BR-MD0-04 a BR-MD0-06:
  - `environment_id`: regex `^[a-z][a-z0-9_-]{2,31}$` — validacion inmediata
  - `store_url`: regex `^https://[a-z0-9.-]+(/.*)?$` — rechaza HTTP plano con mensaje
  - `env_access_secret_path` y `shopper_secret_path`: regex
    `^testpilot/[a-z][a-z0-9_-]+/[a-z][a-z0-9_-]+$`
- Boton "Desactivar" en lugar de eliminar (invariante de trazabilidad — business-logic-model.md)
- `environment_id` es read-only tras creacion
- Ninguna credencial real en el formulario ni en los responses renderizados (BR-MD0-01)
- Manejo de error 5xx con banner no-bloqueante + boton de reintento (BR-MD0-13)
- NFR-MD0-U1: navegacion completa por teclado

**5b. P2 — `NewRunPage` (`pages/NewRunPage.tsx`)**

- Dropdown de `environment_id`: solo ambientes `active=true`
- Lista dinamica de productos: boton "Agregar producto", cada item tiene `search_term`
  (input) y `validate_variant` (checkbox, default true)
- Checkboxes de flows: todos los valores del enum `FlowName` v2 (7 valores incluyendo
  `full_journey`), sin hardcodear nombres legacy con guiones
- Checkboxes de perfiles: `mobile_co`, `desktop_co`, `desktop_ec` (snake_case)
- Selector de modo: `gate` (default) / `exploratory` — con descripcion de cada uno
- Campo `options.timeout_seconds` (opcional, default 180, rango 30-600)
- `capture_intermediate_screenshots` NO se muestra en UI — es constante `false`
  (INVARIANTE — ADR-003; la politica de evidencia es server-side)
- Vista previa del JSON que se enviara: muestra `SyntheticUserConfig` v2 con los valores
  actuales del form — el usuario puede verificar antes de lanzar
- Validaciones BR-MD0-07 antes de submit:
  - >= 1 producto
  - >= 1 flow seleccionado
  - >= 1 perfil seleccionado
  - Ambiente seleccionado y `active=true`
- Submit idempotente: boton deshabilitado mientras `submitting=true` (NFR-MD0-R2,
  Patron 6 de nfr-design.md)
- Al exito: navegar a `/runs/{run_id}/live`
- El payload NUNCA incluye `store_url`, credenciales ni campos inexistentes en v2
  (BR-MD0-01, C12)

**5c. P3 — `LiveRunPage` (`pages/LiveRunPage.tsx`)**

- Encabezado: `environment_id`, timestamp de inicio, badge de modo (`gate`/`exploratory`)
- Matriz generica perfiles x flows: filas = `profile_statuses[].profile_id`,
  columnas = flows activos en el run — sin hardcodear nombres de flows ni numero de
  perfiles (H5.5 AC1)
- Cada celda muestra estado: `pending` / `running` / `success` / `failed` / `error`
  con color y texto
- Por cada fila de perfil: indicador de duracion acumulada `duration_ms`
- Polling via hook `usePolling` con `intervalMs=3000`:
  `shouldContinue`: retorna `true` si `state in ['queued', 'running']`
- Al detectar estado terminal (`completed` o `failed`): detener polling, navegar
  automaticamente a `/runs/{run_id}` tras 1 segundo de delay visual (BR-MD0-11)
- Banner `bootstrap_mode=true`: badge azul "Aprendizaje (X/14)" (BR-MD0-10)
- Banner `orders_created` si el campo aparece != 0: banner ROJO bloqueante con mensaje
  de incidente (BR-MD0-09) — aunque el invariante garantiza que siempre es 0
- Manejo de desconexion: tras 3 fallos consecutivos en polling, banner amarillo
  "Conexion interrumpida — reintentando en 30 s" (NFR-MD0-R1)
- Timeout de run: si polling no detecta finalizacion tras 30 min, banner de advertencia
  (BR-MD0-14)
- Cleanup de polling al desmontar componente (BR-MD0-11)

**5d. P4 — `RunDetailPage` (`pages/RunDetailPage.tsx`)**

- Primer elemento visible: `<TrafficLight color={report.traffic_light} size='lg'>`
  (BR-MD0-08)
- Banner permanente "Ordenes creadas: 0" — siempre visible, no colapsable (BR-MD0-09)
  Si `orders_created != 0`: banner ROJO bloqueante
- Badge de modo (`gate`/`exploratory`) — runs exploratorios con nota "No cuenta para
  decision de deploy"
- Banner bootstrap si `bootstrap_mode=true` (BR-MD0-10)
- Seccion de resumen por perfil: cards para cada `ProfileResult` con:
  - Nombre del perfil, flow ejecutado, `traffic_light` individual, `duration_ms`
- Tabla de pasos por perfil × flow: usa `<StepRow>` con datos de `BaselineComparison`
  si disponible
- Galeria de screenshots: `<ScreenshotThumbnail>` lazy load, ordenada por path
  `{run_id}/{perfil}/{flujo}/{paso}-{state}.png`; solo aparece cuando `screenshot_url`
  no es null (la politica de evidencia es ADR-003 server-side — el dashboard solo
  renderiza lo que viene)
- Seccion `BaselineComparison`: tabla p95 vs current por paso; omitida si
  `baseline_comparison=null` (bootstrap)
- Seccion `audit`: si `audit != null`, lista de hallazgos por dimension con severidad,
  hipotesis del agente (marcadas como hipotesis, no hechos — BR-MD0-10 / P7/C10);
  si `synthesis_available=false`, nota de degradacion graciosa
- Botones: descargar reporte JSON, descargar reporte Markdown
- Cache HTTP: responses de runs terminados son inmutables — no cachear en localStorage
  (BR-MD0-15); el cache HTTP nativo del browser (60s) es suficiente

**5e. P5 — `HistoryPage` (`pages/HistoryPage.tsx`)**

- Tabla paginada, 25 items por pagina, server-side (NFR-MD0-P3)
- Filtros sincronizados con URL (Patron 7 de nfr-design.md, BR-MD0-16):
  - Rango de fechas (`from`, `to`; default: ultimos 7 dias)
  - `environment_id` (dropdown)
  - `traffic_light` (multi-select: green/yellow/red/todos)
  - `flow` (dropdown con enum FlowName v2)
  - `mode` (gate/exploratory/todos)
- Columnas de tabla: fecha/hora, ambiente, semaforo (`<TrafficLight size='sm'>`),
  duracion, modo, perfiles ejecutados (chips), boton "Ver detalle" -> P4
- Badge `bootstrap_mode` en columna de semaforo
- Paginacion con botones Anterior / Siguiente + pagina actual / total
- Al cambiar filtros: reset a pagina 1, actualizar URL query string

**Verificacion del step:**
- Todas las pantallas renderizan sin errores con los mocks del Step 3
- `pnpm run lint` — exit 0

---

### Step 6: Tests Vitest + RTL para P2, P3 y componentes core [ ]

Tests unitarios de componentes y pantallas criticas. Segun NFR-MD0-M2, no se hacen
tests E2E — solo tests de unidad con RTL.

**6a. Tests de `<TrafficLight>` (ya cubiertos en Step 4c, verificar completitud)**

- Renderiza texto + icono en cada estado
- Bootstrap mode: yellow -> gris
- Accesibilidad: `role="status"` presente, `aria-label` correcto

**6b. Tests de `usePolling`** (ya cubiertos en Step 4a)

**6c. Tests de `NewRunPage` (P2 — validacion de formulario -> payload v2)**

Estos tests son los mas criticos porque P2 construye el `SyntheticUserConfig` v2
que se envia a `POST /v1/run`.

- Formulario vacio: boton "Lanzar" deshabilitado hasta que haya al menos 1 producto,
  1 flow, 1 perfil y un ambiente seleccionado
- Seleccion de flows: los checkboxes tienen los 7 valores del enum v2 en snake_case;
  ninguno tiene guion (`checkout-full` no debe existir en el DOM)
- Seleccion de perfiles: los checkboxes son `mobile_co`, `desktop_co`, `desktop_ec`
  (con guion bajo, no guion)
- Payload generado: completar el formulario y verificar que el JSON de vista previa
  contiene `schema_version: 'v2'`, no contiene `screenshot_on_success`, no contiene
  `screenshot_on_error`, no contiene `store_url`, no contiene credenciales
- Submit exitoso: `launchRun` llamado con payload valido -> navega a live view
- Submit fallido (error de API): muestra mensaje de error, boton re-habilitado
- Doble-click en submit: `launchRun` llamado exactamente 1 vez (idempotencia NFR-MD0-R2)
- Ambiente inactivo seleccionado: error de validacion antes de enviar

**6d. Tests de `LiveRunPage` (P3 — polling)**

- Polling inicia al montar con estado `running`
- Polling se detiene cuando el estado cambia a `completed` o `failed`
- Polling se cancela al desmontar el componente (no genera updates en estado desmontado)
- La matriz de pantalla muestra los perfiles y flows del RunStatus (sin hardcodear nombres)
- Banner de incidente aparece si `orders_created != 0` (aunque nunca ocurra en prod)
- Banner de bootstrap aparece si `bootstrap_mode=true`

**6e. Test de accesibilidad basica (transversal)**

Para `<TrafficLight>` y el formulario de P2: verificar que `axe-core` no reporta
violaciones criticas (usar `@axe-core/react` o `jest-axe`).

**Archivo de configuracion de tests:**

`src/dashboard/src/test-setup.ts`:
```typescript
import '@testing-library/jest-dom';
// Mock de IntersectionObserver para tests de ScreenshotThumbnail
global.IntersectionObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(), unobserve: vi.fn(), disconnect: vi.fn(),
}));
```

**Verificacion del step:**
- `pnpm run test` — todos los tests pasan, exit 0
- Los tests de P2 verifican explicitamente que el payload v2 no contiene nombres legacy

---

### Step 7: Integracion con Dockerfile multi-stage y FastAPI StaticFiles [ ]

Actualizar el `Dockerfile` y `src/api/main.py` para integrar el build del dashboard.

**7a. Actualizar `Dockerfile`**

Agregar Stage 1 de build del dashboard al `Dockerfile` existente (U0), segun el
diseno en `infrastructure-design.md`:

```dockerfile
# Stage 1: build del dashboard
FROM node:20-alpine AS dashboard-builder
WORKDIR /build
COPY src/dashboard/package.json src/dashboard/pnpm-lock.yaml ./
RUN npm install -g pnpm@9 && pnpm install --frozen-lockfile
COPY src/dashboard/ ./
RUN pnpm run build
```

En el stage de runtime (Python), agregar:
```dockerfile
COPY --from=dashboard-builder /build/dist /app/src/dashboard/dist
```

**NOTA:** El `Dockerfile` en `infra/` o en la raiz es una ruta protegida que requiere
HITL (ver `CLAUDE.md`). Este step documenta el cambio requerido; la edicion del
Dockerfile debe hacerse con aprobacion humana.

**7b. Actualizar `src/api/main.py`**

Agregar el mount de StaticFiles al final del setup de la app (despues de los routers /v1):

```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles

DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard" / "dist"
if DASHBOARD_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(DASHBOARD_DIR), html=True),
        name="dashboard",
    )
```

El orden de registro es critico: los routers `/v1/*` DEBEN registrarse antes del mount
estatico para que las rutas de API tengan prioridad (deployment-architecture.md).

El `SecurityHeadersMiddleware` (diseno en `nfr-design.md` Patron 8 y
`infrastructure-design.md` seccion 5) aplica CSP headers a responses HTML. Este
middleware ya esta documentado en el diseno de U4 — verificar que se incluya al
registrar MD0.

**7c. Agregar `dist/` a `.gitignore`**

Verificar que `src/dashboard/dist/` esta en `.gitignore` del repo raiz. Si no, agregarlo.
(Decision D-MD0-05: dist/ no se commitea)

**Verificacion del step:**
- `docker build .` incluye el Stage 1 y genera la imagen con `dist/` incorporado
- `curl http://localhost:8000/` desde la imagen levantada devuelve `index.html`
- `curl http://localhost:8000/v1/health` sigue respondiendo (API no bloqueada por
  el mount estatico)
- `src/dashboard/dist/` aparece en `.gitignore`

---

### Step 8: Placeholder de codigo-summary [ ]

Crear el archivo de resumen de codigo para MD0. Este archivo se completa con detalles
reales al finalizar la implementacion; se crea ahora como placeholder para que el
reviewer pueda verificar la existencia del artefacto.

**Crear `aidlc-docs/construction/md0/code/code-summary.md`:**

```markdown
# MD0 Dashboard — Code Summary

**Estado**: PLACEHOLDER — completar al finalizar la implementacion de MD0.

## Archivos creados

(Listar al completar cada Step)

## Gate 6 — Checklist

- [ ] Dashboard accesible en /
- [ ] CSP headers presentes
- [ ] 5 pantallas funcionales contra backend
- [ ] Polling 3s funcionando en P3
- [ ] Sin credenciales en console/network del browser
- [ ] Lighthouse score basico >=80

## Notas de implementacion

(Completar con decisiones tomadas durante la implementacion)
```

**Verificacion del step:**
- Archivo existe en la ruta correcta
- No reemplaza ni sobrescribe `aidlc-docs/audit.md`

---

## Traceability

### Historias de usuario cubiertas

| Historia | Pantalla/Componente | AC clave |
|---|---|---|
| H5.1 — Registro de ambientes | P1 `EnvironmentsPage` | AC1-AC4: form con validaciones, sin credenciales |
| H5.2 — Lanzamiento de run | P2 `NewRunPage` | AC1: JSON pre-rellenado; AC2: sin credenciales en payload; AC3: POST + run_id; AC4: validacion previa |
| H5.3 — Vista en tiempo real | P3 `LiveRunPage` | AC1: estado por perfil; AC2: polling (3s, no 5s — segun nfr-requirements.md); AC3: semaforo individual |
| H5.4 — Historial de ejecuciones | P5 `HistoryPage` | AC1-AC4: tabla con semaforos, filtros por ambiente/flow/fecha |
| H5.5 — Matriz generica de flows | P3 `LiveRunPage` | AC1: sin hardcodear nombres de flows; AC2: estado por celda; AC3: enlace a auditoria; AC4: cap 10 runs visible |
| H0.1 (transversal) | `types/api.ts` | Tipos proyectados desde `src/models.py` y specs v2 |

### NFR cubiertos por Step

| NFR | Step | Implementacion |
|---|---|---|
| NFR-MD0-P1 LCP < 2s | S1 | Bundle split vendor chunk; `manualChunks` en Vite |
| NFR-MD0-P2 Polling 3s ±500ms | S4a, S6d | `usePolling` con jitter ±500ms |
| NFR-MD0-P3 Payload historial < 500ms | S5e | Paginacion server-side 25 items |
| NFR-MD0-P4 Lazy load screenshots | S4d, S5d | `IntersectionObserver` en `<ScreenshotThumbnail>` |
| NFR-MD0-S1 Sin credentials en codigo | S2, S3 | Sin secrets en `types/api.ts` ni en `client.ts` |
| NFR-MD0-S2 Validacion cliente + servidor | S5b | BR-MD0-04 a BR-MD0-07 en P2 |
| NFR-MD0-S3 API key en cada request | S3 | `ApiClient` inyecta `X-API-Key` siempre |
| NFR-MD0-S4 Sin stack traces al usuario | S3 | `ApiClient` extrae solo `error_code` + `message` |
| NFR-MD0-S5 No localStorage sensible | S3, S5 | Solo `sessionStorage` para API key; nada mas |
| NFR-MD0-S6 CSP estricto | S7 | `SecurityHeadersMiddleware` en FastAPI (U4) |
| NFR-MD0-S7 XSS en renderizado | S4f, S5 | React escape automatico; ESLint `react/no-danger: error` |
| NFR-MD0-R1 Desconexion en polling | S4a, S5c | 3 fallos -> pausa + banner (implementado en `usePolling`) |
| NFR-MD0-R2 Submit idempotente | S5b, S6c | Estado `submitting` en P2; test de doble-click |
| NFR-MD0-R3 Estado consistente tras error | S5a | Formulario P1 mantiene valores al fallar PUT |
| NFR-MD0-U1 Teclado WCAG 2.1 AA | S5a, S5b, S6e | Formularios Tab/Enter; test de accesibilidad |
| NFR-MD0-U2 Contraste WCAG AA | S4c | Triple codificacion en `<TrafficLight>` |
| NFR-MD0-U3 Browsers Chrome/Firefox/Edge >=120 | S1 | Vite targets en `tsconfig.json` |
| NFR-MD0-M1 Sin Redux/Zustand | S3, S4 | Estado local por pantalla; solo custom hooks |
| NFR-MD0-M2 Sin tests E2E | S6 | Solo tests de componente con Vitest + RTL |
| NFR-MD0-M3 Commit SHA en footer | S5 | Footer con `import.meta.env.VITE_COMMIT_SHA` |
| NFR-MD0-O1 Console logs estructurados | S3 | `ApiClient`: `console.error({ endpoint, status, error_code })` |

### Reglas de negocio verificadas por tests

| Regla | Test | Step |
|---|---|---|
| BR-MD0-01 Credenciales nunca en cliente | Test de payload P2 no contiene `password`/`store_url` | S6c |
| BR-MD0-02 API key en sessionStorage | `ApiClient` usa `sessionStorage`, no `localStorage` | S3 |
| BR-MD0-07 Validacion de payload v2 | Tests de formulario P2 | S6c |
| BR-MD0-08 Semaforo destacado 96px | Test de `<TrafficLight size='lg'>` | S6a |
| BR-MD0-09 Banner orders_created | Test de P3 con `orders_created != 0` | S6d |
| BR-MD0-10 Badge bootstrap | Tests de P3 y `<TrafficLight bootstrapMode>` | S6a, S6d |
| BR-MD0-11 Polling se detiene | Test de `usePolling` con estado terminal | S6b |
| BR-MD0-12 401 descarta key | Test de `ApiClient` con mock 401 | S3 |
| BR-MD0-16 Filtros en URL | `useRunFilters` sincroniza con `useSearchParams` | S5e |
| BR-MD0-17 Contraste semaforos | Test accesibilidad con axe-core | S6e |

### Invariantes del sistema aplicados en MD0

| Invariante | Aplicacion en MD0 |
|---|---|
| Cero contaminacion (Hard Invariant #1) | `orders_created=0` siempre visible en P3/P4; banner ROJO si != 0 |
| Catalogo cerrado (#2) | Enum `FlowName` en `types/api.ts` tiene exactamente los 7 valores del spec v2; P2 no permite entrada libre |
| JSON Schema gate (#3) | El payload de P2 se valida contra el shape de `SyntheticUserConfig` en el frontend (UX); la validacion autoritativa es Pydantic en el backend |
| Agente sintetiza, nunca juzga (#8) | P4 renderiza `audit.hypotheses` como hipotesis (texto con `confidence`); el `traffic_light` viene de `execution_report.traffic_light`, nunca del campo `audit` |

### Decisiones de diseno referenciadas

| Decision | Artefacto origen | Impacto en plan |
|---|---|---|
| D-MD0-01: React + Vite + TS + Tailwind | `nfr-requirements/tech-stack-decisions.md` | Step 1 |
| D-MD0-02: Polling 3s ± jitter | `nfr-requirements/tech-stack-decisions.md` | Step 4a |
| D-MD0-03: Estado local con hooks | `nfr-requirements/tech-stack-decisions.md` | Step 4, no Redux |
| D-MD0-04: FastAPI StaticFiles | `nfr-requirements/tech-stack-decisions.md` | Step 7b |
| D-MD0-05: No commitar dist/ | `nfr-requirements/tech-stack-decisions.md` | Step 1, Step 7c |
| ADR-003: Evidencia dirigida por hallazgos | `inception/architecture/adrs/adr-003-*.md` | P4 renderiza solo `screenshot_url` cuando viene; no agrega capturas |
| C12: NL nunca llega al executor | `CLAUDE.md` hard invariants | P2 envia payload estructurado v2 validado |

---

## Gate 6 — Tras MD0

Los criterios de aprobacion para esta unidad son los definidos en
`aidlc-docs/construction/plans/build-sequence.md`:

```
- [ ] Dashboard accesible en /
- [ ] CSP headers presentes
- [ ] 5 pantallas funcionales contra backend
- [ ] Polling 3s funcionando en P3
- [ ] Sin credenciales en console/network del browser
- [ ] Lighthouse score basico >=80
```

La verificacion de Gate 6 requiere U4 desplegado y accesible. Durante el desarrollo
de MD0 (en paralelo con U4), las verificaciones se hacen contra los mocks del Step 3.
