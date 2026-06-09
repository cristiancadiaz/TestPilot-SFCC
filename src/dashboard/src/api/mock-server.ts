// In-memory fixtures for Vitest + development
// Used when real API (U4) is not available.
// No real credentials — env_access_secret_path and shopper_secret_path are paths to
// AWS Secrets Manager, never the actual secrets.

import type {
  EnvironmentConfig,
  RunStatus,
  ExecutionReport,
  RunListResponse,
  RunListItem,
} from '@/types/api';

// --- Fixtures ---

export const MOCK_ENVIRONMENTS: EnvironmentConfig[] = [
  {
    environment_id: 'staging',
    display_name: 'Staging',
    store_url: 'https://staging.example.shop',
    env_access_secret_path: 'testpilot/staging/env-access',
    shopper_secret_path: 'testpilot/staging/shopper',
    anti_bot_whitelisted: true,
    active: true,
    created_at: '2026-05-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
  },
  {
    environment_id: 'development',
    display_name: 'Desarrollo',
    store_url: 'https://dev.example.shop',
    env_access_secret_path: 'testpilot/development/env-access',
    shopper_secret_path: 'testpilot/development/shopper',
    anti_bot_whitelisted: true,
    active: true,
    created_at: '2026-05-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
  },
  {
    environment_id: 'sandbox',
    display_name: 'Sandbox (inactivo)',
    store_url: 'https://sandbox.example.shop',
    env_access_secret_path: 'testpilot/sandbox/env-access',
    shopper_secret_path: 'testpilot/sandbox/shopper',
    anti_bot_whitelisted: false,
    active: false,
    created_at: '2026-04-01T00:00:00Z',
    updated_at: '2026-05-01T00:00:00Z',
  },
];

export const MOCK_RUN_STATUS_RUNNING: RunStatus = {
  run_id: 'mock-uuid-1234',
  state: 'running',
  mode: 'gate',
  started_at: '2026-06-06T10:00:00Z',
  environment_id: 'staging',
  bootstrap_mode: false,
  orders_created: 0,
  profile_statuses: [
    {
      profile_id: 'mobile_co',
      flow_name: 'checkout_full',
      state: 'running',
      current_step: 'checkout_shipping',
      steps_completed: 5,
      steps_total: 10,
      duration_ms: 45000,
    },
    {
      profile_id: 'desktop_co',
      flow_name: 'checkout_full',
      state: 'pending',
      current_step: null,
      steps_completed: 0,
      steps_total: 10,
      duration_ms: 0,
    },
    {
      profile_id: 'desktop_ec',
      flow_name: 'checkout_full',
      state: 'pending',
      current_step: null,
      steps_completed: 0,
      steps_total: 10,
      duration_ms: 0,
    },
  ],
};

export const MOCK_RUN_STATUS_COMPLETED: RunStatus = {
  run_id: 'mock-uuid-1234',
  state: 'completed',
  mode: 'gate',
  started_at: '2026-06-06T10:00:00Z',
  environment_id: 'staging',
  bootstrap_mode: false,
  orders_created: 0,
  profile_statuses: [
    {
      profile_id: 'mobile_co',
      flow_name: 'checkout_full',
      state: 'success',
      current_step: null,
      steps_completed: 10,
      steps_total: 10,
      duration_ms: 165000,
    },
    {
      profile_id: 'desktop_co',
      flow_name: 'checkout_full',
      state: 'success',
      current_step: null,
      steps_completed: 10,
      steps_total: 10,
      duration_ms: 142000,
    },
    {
      profile_id: 'desktop_ec',
      flow_name: 'checkout_full',
      state: 'success',
      current_step: null,
      steps_completed: 10,
      steps_total: 10,
      duration_ms: 158000,
    },
  ],
};

export const MOCK_REPORT_GREEN: ExecutionReport = {
  run_id: 'mock-uuid-1234',
  environment_id: 'staging',
  mode: 'gate',
  started_at: '2026-06-06T10:00:00Z',
  finished_at: '2026-06-06T10:08:30Z',
  duration_ms: 510000,
  traffic_light: 'green',
  bootstrap_mode: false,
  profile_results: [
    {
      profile: {
        name: 'mobile_co',
        viewport_width: 390,
        viewport_height: 844,
        locale: 'es-CO',
        user_agent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',
        is_mobile: true,
      },
      flow_result: {
        flow_name: 'checkout_full',
        status: 'success',
        duration_ms: 165000,
        steps: [
          {
            name: 'env_access_auth',
            status: 'success',
            phase: 'setup',
            duration_ms: 1200,
            error: null,
            screenshot_url: null,
            screenshot_state: null,
            finding_dimension: null,
          },
          {
            name: 'shopper_login',
            status: 'success',
            phase: 'setup',
            duration_ms: 4500,
            error: null,
            screenshot_url: null,
            screenshot_state: null,
            finding_dimension: null,
          },
          {
            name: 'payment_failure_validation',
            status: 'success',
            phase: 'flow',
            duration_ms: 3200,
            error: null,
            screenshot_url:
              'mock-uuid-1234/mobile_co/checkout_full/payment_failure_validation-final.png',
            screenshot_state: 'final',
            finding_dimension: null,
          },
        ],
      },
      traffic_light: 'green',
      network_summary: {
        total_requests: 120,
        failed_requests: 0,
        web_vitals: { lcp_ms: 1800, cls: 0.05, ttfb_ms: 210 },
        har_url: 'mock-uuid-1234/mobile_co/checkout_full/network.har.json',
      },
    },
  ],
  baseline_comparison: {
    p95_ms: 185000,
    current_ms: 165000,
    bootstrap_mode: false,
    runs_count: 18,
  },
  audit: null,
};

export const MOCK_REPORT_RED: ExecutionReport = {
  run_id: 'mock-uuid-5678',
  environment_id: 'staging',
  mode: 'gate',
  started_at: '2026-06-05T09:00:00Z',
  finished_at: '2026-06-05T09:04:00Z',
  duration_ms: 240000,
  traffic_light: 'red',
  bootstrap_mode: false,
  profile_results: [
    {
      profile: {
        name: 'desktop_co',
        viewport_width: 1280,
        viewport_height: 800,
        locale: 'es-CO',
        user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        is_mobile: false,
      },
      flow_result: {
        flow_name: 'checkout_full',
        status: 'failed',
        duration_ms: 240000,
        steps: [
          {
            name: 'checkout_payment',
            status: 'failed',
            phase: 'flow',
            duration_ms: 12000,
            error: 'Elemento no encontrado: #payment-form',
            screenshot_url: 'mock-uuid-5678/desktop_co/checkout_full/checkout_payment-fail.png',
            screenshot_state: 'fail',
            finding_dimension: null,
          },
        ],
      },
      traffic_light: 'red',
      network_summary: null,
    },
  ],
  baseline_comparison: null,
  audit: null,
};

export const MOCK_RUN_LIST: RunListResponse = {
  items: [
    {
      run_id: 'mock-uuid-1234',
      environment_id: 'staging',
      display_name: 'checkout_full @ staging',
      started_at: '2026-06-06T10:00:00Z',
      finished_at: '2026-06-06T10:08:30Z',
      duration_ms: 510000,
      traffic_light: 'green',
      bootstrap_mode: false,
      mode: 'gate',
      profiles_executed: ['mobile_co', 'desktop_co', 'desktop_ec'],
      flows_executed: ['checkout_full'],
      orders_created: 0,
    } as RunListItem,
    {
      run_id: 'mock-uuid-5678',
      environment_id: 'staging',
      display_name: 'checkout_full @ staging',
      started_at: '2026-06-05T09:00:00Z',
      finished_at: '2026-06-05T09:04:00Z',
      duration_ms: 240000,
      traffic_light: 'red',
      bootstrap_mode: false,
      mode: 'gate',
      profiles_executed: ['desktop_co'],
      flows_executed: ['checkout_full'],
      orders_created: 0,
    } as RunListItem,
  ],
  page: 1,
  page_size: 25,
  total: 2,
  has_more: false,
};

// --- Mock ApiClient for tests ---
// Import this in test files to get a pre-wired mock client.

export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export const mockHandlers = {
  getEnvironments: () => Promise.resolve(MOCK_ENVIRONMENTS),
  getEnvironment: (id: string) => {
    const env = MOCK_ENVIRONMENTS.find((e) => e.environment_id === id);
    if (!env) return Promise.reject(new Error('not_found'));
    return Promise.resolve(env);
  },
  launchRun: async (_config: unknown) => {
    await delay(200); // simulate network
    return { run_id: 'mock-uuid-1234' };
  },
  getRunStatus: (_runId: string) => Promise.resolve(MOCK_RUN_STATUS_RUNNING),
  getRunDetail: (runId: string) => {
    if (runId === 'mock-uuid-5678') return Promise.resolve(MOCK_REPORT_RED);
    return Promise.resolve(MOCK_REPORT_GREEN);
  },
  listRuns: () => Promise.resolve(MOCK_RUN_LIST),
};
