// API endpoint path constants
// All paths are relative to /v1 (prefixed by ApiClient.fetch)

export const ENDPOINTS = {
  // Environments
  ENVIRONMENTS: '/environments',
  ENVIRONMENT: (id: string) => `/environments/${id}`,

  // Runs
  RUN_LAUNCH: '/run',
  RUN_STATUS: (runId: string) => `/runs/${runId}/status`,
  RUN_DETAIL: (runId: string) => `/runs/${runId}`,
  RUNS_LIST: '/runs',

  // Screenshots (path only — URL is constructed in client)
  SCREENSHOT: (runId: string, path: string) => `/screenshots/${runId}/${path}`,
} as const;
