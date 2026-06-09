import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { LiveRunPage } from '@/pages/LiveRunPage';
import {
  MOCK_RUN_STATUS_RUNNING,
  MOCK_RUN_STATUS_COMPLETED,
} from '@/api/mock-server';
import type { RunStatus } from '@/types/api';

// Mock the apiClient
const mockGetRunStatus = vi.fn();

vi.mock('@/api/client', () => ({
  apiClient: {
    getRunStatus: (...args: unknown[]) => mockGetRunStatus(...args),
  },
  ApiError: class ApiError extends Error {
    error_code: string;
    constructor(code: string, msg: string) {
      super(msg);
      this.error_code = code;
    }
  },
}));

// Mock navigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const Wrapper = ({ runId = 'mock-uuid-1234' }) => (
  <MemoryRouter initialEntries={[`/runs/${runId}/live`]}>
    <Routes>
      <Route path="/runs/:runId/live" element={<LiveRunPage />} />
    </Routes>
  </MemoryRouter>
);

describe('LiveRunPage (P3)', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockGetRunStatus.mockResolvedValue(MOCK_RUN_STATUS_RUNNING);
    mockNavigate.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('renders profile and flow names from RunStatus without hardcoding', async () => {
    render(<Wrapper />);

    await waitFor(() => {
      expect(screen.getByText('mobile_co')).toBeInTheDocument();
    });

    // Check that flows from the status are displayed
    expect(screen.getByText(/checkout_full/i)).toBeInTheDocument();
  });

  it('shows running badge for profiles in running state', async () => {
    render(<Wrapper />);

    await waitFor(() => {
      expect(screen.getAllByText(/ejecutando/i).length).toBeGreaterThan(0);
    });
  });

  it('shows bootstrap banner when bootstrap_mode=true', async () => {
    const statusWithBootstrap: RunStatus = {
      ...MOCK_RUN_STATUS_RUNNING,
      bootstrap_mode: true,
    };
    mockGetRunStatus.mockResolvedValue(statusWithBootstrap);

    render(<Wrapper />);

    await waitFor(() => {
      expect(screen.getByText(/aprendizaje/i)).toBeInTheDocument();
    });
  });

  it('shows INCIDENT banner when orders_created != 0 (invariant violation)', async () => {
    const statusWithOrders = {
      ...MOCK_RUN_STATUS_RUNNING,
      orders_created: 1,
    } as unknown as RunStatus;
    mockGetRunStatus.mockResolvedValue(statusWithOrders);

    render(<Wrapper />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/incidente/i)).toBeInTheDocument();
    });
  });

  it('polling stops and navigates when state = completed (BR-MD0-11)', async () => {
    // First call returns running, second returns completed
    mockGetRunStatus
      .mockResolvedValueOnce(MOCK_RUN_STATUS_RUNNING)
      .mockResolvedValue(MOCK_RUN_STATUS_COMPLETED);

    render(<Wrapper />);

    // Wait for completed state to be detected
    await waitFor(
      () => {
        expect(screen.getByText(/completado/i)).toBeInTheDocument();
      },
      { timeout: 10000 }
    );

    // Advance timer to trigger navigate (1s delay)
    await vi.advanceTimersByTimeAsync(1500);

    expect(mockNavigate).toHaveBeenCalledWith('/runs/mock-uuid-1234');
  });

  it('matrix is generic — no hardcoded number of profiles or flows', async () => {
    // Use a status with only 1 profile
    const singleProfile: RunStatus = {
      ...MOCK_RUN_STATUS_RUNNING,
      profile_statuses: [MOCK_RUN_STATUS_RUNNING.profile_statuses[0]],
    };
    mockGetRunStatus.mockResolvedValue(singleProfile);

    render(<Wrapper />);

    await waitFor(() => {
      expect(screen.getByText('mobile_co')).toBeInTheDocument();
    });
    // Should only show mobile_co, not desktop_co or desktop_ec
    expect(screen.queryByText('desktop_co')).not.toBeInTheDocument();
  });
});
