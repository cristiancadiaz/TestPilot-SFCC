# Domain Entities — MD0 Dashboard Web Interno

Modelos de datos que el frontend consume del backend. **El dashboard no define modelos propios** — son vistas TypeScript/JSDoc de los modelos Pydantic del backend (definidos en U0 `src/models.py`).

---

## EnvironmentConfig (P1)

```typescript
interface EnvironmentConfig {
  environment_id: string;          // ^[a-z][a-z0-9_-]{2,31}$ — read-only post-create
  display_name: string;            // libre, max 128 chars
  store_url: string;               // https URL
  env_access_secret_path: string;  // testpilot/{env}/env-access
  shopper_secret_path: string;     // testpilot/{env}/shopper
  anti_bot_whitelisted: boolean;
  active: boolean;
  created_at: string;              // ISO 8601
  updated_at: string;              // ISO 8601
}
```

**Operaciones del dashboard sobre esta entidad:** crear, editar (todos los campos excepto `environment_id` y `created_at`), desactivar (`active=false`). **Nunca elimina.**

---

## SyntheticUserConfig (P2 — request body de POST /v1/run)

```typescript
interface SyntheticUserConfig {
  environment_id: string;          // referencia a EnvironmentConfig
  products: Array<{
    search_term: string;
    validate_variant: boolean;
  }>;
  flows: Array<"checkout-full" | "checkout-card-declined">;
  profiles: Array<"mobile-co" | "desktop-co" | "desktop-ec">;
  screenshot_on_success: boolean;
  screenshot_on_error: boolean;    // siempre true (invariante BR-MD0-07)
}
```

**Nota crítica:** el dashboard NUNCA agrega campos de credenciales al payload. La resolución de URL + credenciales ocurre en el backend a partir de `environment_id`.

---

## RunStatus (P3 — response de GET /v1/runs/{id}/status)

```typescript
interface RunStatus {
  run_id: string;
  state: "queued" | "running" | "completed" | "failed";
  started_at: string;              // ISO 8601
  environment_id: string;
  profiles: Array<{
    profile_id: "mobile-co" | "desktop-co" | "desktop-ec";
    state: "pending" | "running" | "success" | "failed";
    current_step: string | null;   // nombre del paso en curso
    steps_completed: number;
    steps_total: number;
    duration_ms: number;           // acumulado parcial
  }>;
}
```

**Vista del dashboard:** grilla 3×N (perfiles × pasos), con celdas coloreadas según `state`. Auto-refresh cada 3 s mientras `state ∈ {queued, running}`.

---

## ExecutionReport (P4 — response de GET /v1/runs/{id})

Modelo completo del reporte terminado. Definido por `specs/execution_report.json` y modelado en `src/models.py` (U0). El dashboard lo consume tal cual y lo renderiza.

**Campos clave para visualización:**

```typescript
interface ExecutionReport {
  run_id: string;
  environment_id: string;
  started_at: string;
  finished_at: string;
  duration_ms: number;
  traffic_light: "green" | "yellow" | "red";
  bootstrap_mode: boolean;
  orders_created: 0;               // invariante — siempre 0
  profile_results: Array<ProfileResult>;
  baseline_comparison: BaselineComparison | null;
}

interface ProfileResult {
  profile_id: string;
  flow_name: string;
  traffic_light: "green" | "yellow" | "red";
  duration_ms: number;
  steps: Array<StepResult>;
}

interface StepResult {
  name: string;
  status: "success" | "failed" | "skipped";
  duration_ms: number;
  error: string | null;
  screenshot_url: string | null;  // path relativo, ej. "abc123/mobile-co/checkout-full/payment-fail.png"
}

interface BaselineComparison {
  p95_baseline_ms: number;
  current_vs_p95_pct: number;     // ej. 1.18 = 18% sobre baseline
  per_step_comparison: Array<{
    step_name: string;
    p95_ms: number;
    current_ms: number;
    pct_diff: number;
  }>;
}
```

---

## RunListItem (P5 — response de GET /v1/runs?filters)

Vista resumida para la tabla de historial. **No** incluye `profile_results.steps` ni screenshots para evitar payloads grandes.

```typescript
interface RunListItem {
  run_id: string;
  environment_id: string;
  display_name: string;            // join con EnvironmentConfig.display_name
  started_at: string;
  finished_at: string;
  duration_ms: number;
  traffic_light: "green" | "yellow" | "red";
  bootstrap_mode: boolean;
  profiles_executed: Array<string>;
  flows_executed: Array<string>;
  orders_created: 0;
}

interface RunListResponse {
  items: Array<RunListItem>;
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
}
```

---

## ApiError (todas las pantallas)

```typescript
interface ApiError {
  error_code: string;              // ej. "environment_not_found"
  message: string;                 // legible para usuario
  details?: Record<string, unknown>;
}
```

**Códigos esperados:**
- `environment_not_found` (404 al lanzar run)
- `environment_inactive` (409 — ambiente desactivado)
- `secret_not_found` (502 — path no resuelve en Secrets Manager)
- `validation_failed` (422 — Pydantic rechaza input)
- `unauthorized` (401 — API key inválida)
- `run_not_found` (404 — UUID inexistente)
- `internal_error` (500 — sin detalles al cliente por SECURITY-15)

---

## Relación con backend

```
Dashboard (frontend)            Backend (U4 API)            Storage
─────────────────────           ───────────────────         ───────
EnvironmentConfig vista   ←→    EnvironmentConfig         DynamoDB tabla environments
                                   model (Pydantic)
                                
SyntheticUserConfig form  →     SyntheticUserConfig       (efímero, sin persistir)
                                   model (Pydantic)
                                
RunStatus vista           ←     RunStatus model           DynamoDB tabla runs (estado en vivo)

ExecutionReport vista     ←     ExecutionReport model     DynamoDB tabla runs + S3 (screenshots)

RunListItem tabla         ←     RunListItem proyección    DynamoDB tabla runs (GSI por fecha)
```

**Principio:** el dashboard es un **cliente puro** sobre el contrato REST. Toda lógica de dominio vive en el backend. El frontend solo valida formato antes de enviar, renderiza al recibir, y maneja transiciones de UI.
