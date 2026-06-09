import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { NewRunPage } from '@/pages/NewRunPage';
import { MOCK_ENVIRONMENTS } from '@/api/mock-server';
import type { SyntheticUserConfig } from '@/types/api';

// Mock apiClient
const mockLaunchRun = vi.fn();
const mockGetEnvironments = vi.fn();

vi.mock('@/api/client', () => ({
  apiClient: {
    launchRun: (...args: unknown[]) => mockLaunchRun(...args),
    getEnvironments: (...args: unknown[]) => mockGetEnvironments(...args),
  },
  ApiError: class ApiError extends Error {
    error_code: string;
    constructor(code: string, msg: string) {
      super(msg);
      this.error_code = code;
    }
  },
}));

const activeEnvs = MOCK_ENVIRONMENTS.filter((e) => e.active);

const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter initialEntries={['/runs/new']}>{children}</MemoryRouter>
);

describe('NewRunPage (P2)', () => {
  beforeEach(() => {
    mockGetEnvironments.mockResolvedValue(MOCK_ENVIRONMENTS);
    mockLaunchRun.mockResolvedValue({ run_id: 'mock-uuid-1234' });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('submit button disabled when form is empty', async () => {
    render(<NewRunPage />, { wrapper: Wrapper });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /lanzar run/i })).toBeDisabled();
    });
  });

  it('flow checkboxes have all 7 v2 snake_case values — no hyphens (BR-MD0-07)', async () => {
    render(<NewRunPage />, { wrapper: Wrapper });

    // All 7 FlowName values must appear
    const expectedFlows = [
      'checkout_full',
      'checkout_card_declined',
      'search_and_filter',
      'browse_discounted_products',
      'pdp_validation',
      'cart_review',
      'full_journey',
    ];

    for (const flow of expectedFlows) {
      const checkbox = screen.getByDisplayValue(flow);
      expect(checkbox).toBeInTheDocument();
    }

    // Verify no hyphenated (legacy) names exist in the DOM
    const allCheckboxes = screen
      .getAllByRole('checkbox')
      .filter((cb) => (cb as HTMLInputElement).type === 'checkbox');
    const values = allCheckboxes.map((cb) => (cb as HTMLInputElement).value);
    const hyphenated = values.filter(
      (v) => v.includes('-') && (v.startsWith('checkout') || v.startsWith('search') || v.startsWith('browse') || v.startsWith('pdp') || v.startsWith('cart') || v.startsWith('full'))
    );
    expect(hyphenated).toHaveLength(0);
  });

  it('profile checkboxes use snake_case (mobile_co, desktop_co, desktop_ec)', async () => {
    render(<NewRunPage />, { wrapper: Wrapper });

    expect(screen.getByDisplayValue('mobile_co')).toBeInTheDocument();
    expect(screen.getByDisplayValue('desktop_co')).toBeInTheDocument();
    expect(screen.getByDisplayValue('desktop_ec')).toBeInTheDocument();
  });

  it('generated payload contains schema_version v2 and no legacy/credential fields', async () => {
    render(<NewRunPage />, { wrapper: Wrapper });

    // Select environment
    await waitFor(() => {
      expect(screen.getByRole('option', { name: /staging/i })).toBeInTheDocument();
    });
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /seleccionar ambiente/i }),
      'staging'
    );

    // Select a flow
    await userEvent.click(screen.getByDisplayValue('checkout_full'));

    // Select a profile
    await userEvent.click(screen.getByDisplayValue('mobile_co'));

    // Fill product search term
    const searchInput = screen.getByPlaceholderText(/término de búsqueda/i);
    await userEvent.type(searchInput, 'camisa roja');

    // Check JSON preview — uses <pre> tag (no ARIA role for pre)
    const preElements = document.querySelectorAll('pre');
    expect(preElements.length).toBeGreaterThan(0);
    const text = preElements[0].textContent ?? '';
    expect(text).toContain('"schema_version": "v2"');
    expect(text).not.toContain('screenshot_on_success');
    expect(text).not.toContain('screenshot_on_error');
    expect(text).not.toContain('store_url');
    expect(text).not.toContain('password');
  });

  it('successful submit calls launchRun exactly once (idempotence BR-MD0-01 + NFR-MD0-R2)', async () => {
    render(<NewRunPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole('option', { name: /staging/i })).toBeInTheDocument();
    });

    // Fill form
    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /seleccionar ambiente/i }),
      'staging'
    );
    await userEvent.click(screen.getByDisplayValue('checkout_full'));
    await userEvent.click(screen.getByDisplayValue('mobile_co'));
    const searchInput = screen.getByPlaceholderText(/término de búsqueda/i);
    await userEvent.type(searchInput, 'camisa roja');

    const submitBtn = screen.getByRole('button', { name: /lanzar run/i });

    // Double-click
    await userEvent.click(submitBtn);
    await userEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockLaunchRun).toHaveBeenCalledTimes(1);
    });
  });

  it('shows error and re-enables submit when launchRun fails', async () => {
    mockLaunchRun.mockRejectedValueOnce({ message: 'API error' });
    render(<NewRunPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole('option', { name: /staging/i })).toBeInTheDocument();
    });

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /seleccionar ambiente/i }),
      'staging'
    );
    await userEvent.click(screen.getByDisplayValue('checkout_full'));
    await userEvent.click(screen.getByDisplayValue('mobile_co'));
    const searchInput = screen.getByPlaceholderText(/término de búsqueda/i);
    await userEvent.type(searchInput, 'tenis');

    const submitBtn = screen.getByRole('button', { name: /lanzar run/i });
    await userEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/api error/i)).toBeInTheDocument();
    });
    // Button re-enabled for retry
    expect(screen.getByRole('button', { name: /lanzar run/i })).not.toBeDisabled();
  });

  it('payload does not contain store_url or credentials (BR-MD0-01)', async () => {
    let capturedPayload: SyntheticUserConfig | null = null;
    mockLaunchRun.mockImplementation(async (payload: SyntheticUserConfig) => {
      capturedPayload = payload;
      return { run_id: 'mock-uuid-1234' };
    });

    render(<NewRunPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole('option', { name: /staging/i })).toBeInTheDocument();
    });

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /seleccionar ambiente/i }),
      'staging'
    );
    await userEvent.click(screen.getByDisplayValue('checkout_full'));
    await userEvent.click(screen.getByDisplayValue('mobile_co'));
    const searchInput = screen.getByPlaceholderText(/término de búsqueda/i);
    await userEvent.type(searchInput, 'jeans azul');

    await userEvent.click(screen.getByRole('button', { name: /lanzar run/i }));

    await waitFor(() => {
      expect(capturedPayload).not.toBeNull();
    });

    expect(capturedPayload).not.toBeNull();
    const p = capturedPayload as unknown as SyntheticUserConfig;
    const json = JSON.stringify(p);
    expect(json).not.toContain('store_url');
    expect(json).not.toContain('password');
    expect(json).not.toContain('secret');
    expect(p.schema_version).toBe('v2');
    // capture_intermediate_screenshots must be absent or false
    if (p.options) {
      expect(p.options.capture_intermediate_screenshots).toBe(false);
    }
  });

  it('validate: error shown when no products', async () => {
    render(<NewRunPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole('option', { name: /staging/i })).toBeInTheDocument();
    });

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: /seleccionar ambiente/i }),
      'staging'
    );
    await userEvent.click(screen.getByDisplayValue('checkout_full'));
    await userEvent.click(screen.getByDisplayValue('mobile_co'));
    // Leave product search_term empty

    const submitBtn = screen.getByRole('button', { name: /lanzar run/i });
    expect(submitBtn).toBeDisabled();
  });

  it('inactive environment is not shown in dropdown', async () => {
    render(<NewRunPage />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole('option', { name: /staging/i })).toBeInTheDocument();
    });

    // sandbox is inactive — should not appear
    const options = screen.getAllByRole('option');
    const values = options.map((o) => (o as HTMLOptionElement).value);
    expect(values).not.toContain('sandbox');
    expect(activeEnvs.every((e) => values.includes(e.environment_id))).toBe(true);
  });

  it('capture_intermediate_screenshots is NOT shown in UI', () => {
    render(<NewRunPage />, { wrapper: Wrapper });
    // This field must not be visible/interactive in the UI (ADR-003 invariant)
    expect(screen.queryByLabelText(/capture_intermediate/i)).toBeNull();
    expect(screen.queryByText(/capture_intermediate/i)).toBeNull();
  });
});
