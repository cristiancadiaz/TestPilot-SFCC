// Types projected from specs v2 contracts and src/models.py
// snake_case throughout — mirrors the backend Pydantic models exactly.
// NO legacy hyphenated names (e.g. mobile-co, checkout-full) exist here.

// --- Enums and literals ---

export type FlowName =
  | 'checkout_full'
  | 'checkout_card_declined'
  | 'search_and_filter'
  | 'browse_discounted_products'
  | 'pdp_validation'
  | 'cart_review'
  | 'full_journey';

export const FLOW_NAMES: FlowName[] = [
  'checkout_full',
  'checkout_card_declined',
  'search_and_filter',
  'browse_discounted_products',
  'pdp_validation',
  'cart_review',
  'full_journey',
];

export type ProfileName = 'mobile_co' | 'desktop_co' | 'desktop_ec';

export const PROFILE_NAMES: ProfileName[] = ['mobile_co', 'desktop_co', 'desktop_ec'];

export type RunMode = 'gate' | 'exploratory';
export type TrafficLightColor = 'green' | 'yellow' | 'red';
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

// --- Environment config ---

export interface EnvironmentConfig {
  environment_id: string; // ^[a-z][a-z0-9_-]{2,31}$, read-only post-create
  display_name: string;
  store_url: string; // https URL — NEVER sent to frontend users directly
  env_access_secret_path: string; // ^testpilot/[a-z][a-z0-9_-]+/[a-z][a-z0-9_-]+$
  shopper_secret_path: string; // ^testpilot/[a-z][a-z0-9_-]+/[a-z][a-z0-9_-]+$
  anti_bot_whitelisted: boolean;
  active: boolean;
  created_at: string; // ISO 8601
  updated_at: string;
}

// --- Run request (POST /v1/run) ---
// INVARIANT: capture_intermediate_screenshots is always false (ADR-003)
// INVARIANT: store_url and credentials are NEVER included in this payload

export interface ProductItem {
  search_term: string; // minLength:2, maxLength:128
  validate_variant?: boolean; // default true
}

export interface RunOptions {
  timeout_seconds?: number; // min:30, max:600, default:180
  capture_intermediate_screenshots: false; // INVARIANT — always false
}

export interface SyntheticUserConfig {
  schema_version: 'v2';
  environment_id: string;
  flows: FlowName[];
  mode?: RunMode; // default 'gate' if omitted
  profiles: ProfileName[];
  products: ProductItem[];
  options?: RunOptions;
}

// --- Live run status (GET /v1/runs/{id}/status) ---

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
  bootstrap_mode?: boolean;
  orders_created: 0; // INVARIANT — always 0
  profile_statuses: ProfileRunStatus[];
}

// --- Full report (GET /v1/runs/{id}) ---

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
  traffic_light: TrafficLightColor;
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

// INVARIANT (P7/C10): hypotheses are ALWAYS presented as hypotheses, never facts.
// The traffic_light is computed exclusively by deterministic rule — never by the audit agent.
export interface AuditHypothesis {
  text: string;
  confidence: number; // 0..1
  requires_human_review: boolean;
}

export interface AuditReport {
  findings: AuditFinding[];
  hypotheses?: AuditHypothesis[];
  synthesis_available: boolean;
  document_md_url: string | null;
}

export interface ControllerTiming {
  pattern: string;
  count: number;
  p95_ms: number;
}

export interface WebVitals {
  lcp_ms: number | null;
  cls: number | null;
  ttfb_ms: number | null;
}

export interface NetworkSummary {
  total_requests: number;
  failed_requests: number;
  controllers?: ControllerTiming[];
  web_vitals?: WebVitals | null;
  har_url?: string | null;
}

export interface ExecutionReport {
  run_id: string;
  environment_id: string;
  mode: RunMode;
  started_at: string;
  finished_at: string;
  duration_ms: number;
  traffic_light: TrafficLightColor;
  bootstrap_mode: boolean;
  profile_results: ProfileResult[];
  baseline_comparison: BaselineComparison | null;
  audit: AuditReport | null;
}

// --- Run history (GET /v1/runs) ---

export interface RunListItem {
  run_id: string;
  environment_id: string;
  display_name: string;
  started_at: string;
  finished_at: string;
  duration_ms: number;
  traffic_light: TrafficLightColor;
  bootstrap_mode: boolean;
  mode: RunMode;
  profiles_executed: ProfileName[];
  flows_executed: FlowName[];
  orders_created: 0; // INVARIANT — always 0
}

export interface RunListResponse {
  items: RunListItem[];
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
}

// --- API error ---

export interface ApiErrorPayload {
  error_code: string;
  message: string;
  details?: Record<string, unknown>;
}

// --- Filters for GET /v1/runs ---

export interface RunFilters {
  from?: string; // ISO date
  to?: string;
  environment_id?: string;
  traffic_light?: TrafficLightColor;
  flow?: FlowName;
  mode?: RunMode;
  page?: number;
  page_size?: number;
}
