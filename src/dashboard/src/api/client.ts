import type {
  EnvironmentConfig,
  SyntheticUserConfig,
  RunStatus,
  ExecutionReport,
  RunListResponse,
  RunFilters,
  ApiErrorPayload,
} from '@/types/api';
import { ENDPOINTS } from './endpoints';

const SESSION_KEY = 'testpilot_api_key';

export class ApiError extends Error {
  constructor(
    public readonly error_code: string,
    message: string,
    public readonly details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'ApiError';
  }

  toPayload(): ApiErrorPayload {
    return {
      error_code: this.error_code,
      message: this.message,
      ...(this.details ? { details: this.details } : {}),
    };
  }
}

export class ApiClient {
  private apiKey: string | null;

  constructor() {
    this.apiKey = sessionStorage.getItem(SESSION_KEY);
  }

  setApiKey(key: string): void {
    this.apiKey = key;
    sessionStorage.setItem(SESSION_KEY, key);
  }

  clearApiKey(): void {
    this.apiKey = null;
    sessionStorage.removeItem(SESSION_KEY);
  }

  hasApiKey(): boolean {
    return this.apiKey !== null && this.apiKey.length > 0;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    if (!this.apiKey) {
      throw new ApiError('no_api_key', 'API key no configurada');
    }

    let response: Response;
    try {
      response = await fetch(`/v1${path}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': this.apiKey,
          ...options.headers,
        },
      });
    } catch (err) {
      // Network-level error (DNS, CORS, offline)
      throw new ApiError('network_error', 'Error de red al conectar con el servidor');
    }

    if (response.status === 401) {
      // BR-MD0-12: discard key on 401
      this.clearApiKey();
      throw new ApiError('unauthorized', 'API key inválida o expirada');
    }

    if (!response.ok) {
      // SECURITY-15, NFR-MD0-S4: extract only error_code + message, never raw body
      let errorCode = 'unknown';
      let errorMessage = `HTTP ${response.status}`;
      try {
        const body = (await response.json()) as Partial<ApiErrorPayload>;
        if (body.error_code) errorCode = body.error_code;
        if (body.message) errorMessage = body.message;
      } catch {
        // Ignore parse errors — keep defaults
      }
      console.error({ endpoint: path, status: response.status, error_code: errorCode });
      throw new ApiError(errorCode, errorMessage);
    }

    if (response.status === 204) {
      return undefined as unknown as T;
    }

    return response.json() as Promise<T>;
  }

  // --- Environments ---

  async getEnvironments(): Promise<EnvironmentConfig[]> {
    return this.request<EnvironmentConfig[]>(ENDPOINTS.ENVIRONMENTS);
  }

  async getEnvironment(id: string): Promise<EnvironmentConfig> {
    return this.request<EnvironmentConfig>(ENDPOINTS.ENVIRONMENT(id));
  }

  async createEnvironment(
    data: Omit<EnvironmentConfig, 'created_at' | 'updated_at'>
  ): Promise<EnvironmentConfig> {
    return this.request<EnvironmentConfig>(ENDPOINTS.ENVIRONMENTS, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateEnvironment(id: string, data: Partial<EnvironmentConfig>): Promise<EnvironmentConfig> {
    return this.request<EnvironmentConfig>(ENDPOINTS.ENVIRONMENT(id), {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async deactivateEnvironment(id: string): Promise<void> {
    return this.request<void>(ENDPOINTS.ENVIRONMENT(id), {
      method: 'DELETE',
    });
  }

  // --- Runs ---

  async launchRun(config: SyntheticUserConfig): Promise<{ run_id: string }> {
    return this.request<{ run_id: string }>(ENDPOINTS.RUN_LAUNCH, {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  async getRunStatus(runId: string): Promise<RunStatus> {
    return this.request<RunStatus>(ENDPOINTS.RUN_STATUS(runId));
  }

  async getRunDetail(runId: string): Promise<ExecutionReport> {
    return this.request<ExecutionReport>(ENDPOINTS.RUN_DETAIL(runId));
  }

  async listRuns(filters: RunFilters = {}): Promise<RunListResponse> {
    const params = new URLSearchParams();
    if (filters.from) params.set('from', filters.from);
    if (filters.to) params.set('to', filters.to);
    if (filters.environment_id) params.set('environment_id', filters.environment_id);
    if (filters.traffic_light) params.set('traffic_light', filters.traffic_light);
    if (filters.flow) params.set('flow', filters.flow);
    if (filters.mode) params.set('mode', filters.mode);
    if (filters.page !== undefined) params.set('page', String(filters.page));
    if (filters.page_size !== undefined) params.set('page_size', String(filters.page_size));

    const qs = params.toString();
    return this.request<RunListResponse>(`${ENDPOINTS.RUNS_LIST}${qs ? `?${qs}` : ''}`);
  }

  // Screenshots: returns relative URL (same origin, proxied through /v1/screenshots/...)
  getScreenshotUrl(_runId: string, path: string): string {
    return `/v1/screenshots/${path}`;
  }
}

// Singleton instance — components import this
export const apiClient = new ApiClient();
