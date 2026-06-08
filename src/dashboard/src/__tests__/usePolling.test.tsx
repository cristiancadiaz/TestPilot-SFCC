import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { usePolling } from '@/hooks/usePolling';

// Note: Tests that need real timer behavior use vi.useRealTimers() locally.
// Tests with fake timers are careful to flush microtasks.

describe('usePolling', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('calls fetcher on mount (first tick fires immediately)', async () => {
    const fetcher = vi.fn(async () => 'data');
    const shouldContinue = vi.fn(() => false); // stop after first

    const { result } = renderHook(() => usePolling(fetcher, 100, shouldContinue));

    await waitFor(() => {
      expect(result.current.data).toBe('data');
    });
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(result.current.isPolling).toBe(false);
  });

  it('polls multiple times while shouldContinue returns true', async () => {
    let count = 0;
    const fetcher = vi.fn(async () => ++count);
    const shouldContinue = vi.fn((n: number) => n < 3);

    const { result } = renderHook(() => usePolling(fetcher, 20, shouldContinue));

    await waitFor(
      () => {
        expect(result.current.isPolling).toBe(false);
      },
      { timeout: 3000 }
    );
    expect(count).toBeGreaterThanOrEqual(3);
    expect(result.current.data).toBeGreaterThanOrEqual(3);
  });

  it('stops immediately when shouldContinue returns false on first call', async () => {
    const fetcher = vi.fn(async () => 'done');
    const shouldContinue = vi.fn(() => false);

    const { result } = renderHook(() => usePolling(fetcher, 100, shouldContinue));

    await waitFor(() => {
      expect(result.current.isPolling).toBe(false);
    });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('pauses after 3 consecutive failures (NFR-MD0-R1)', async () => {
    let attempts = 0;
    const fetcher = vi.fn(async () => {
      attempts++;
      throw new Error('network error');
    });
    const shouldContinue = vi.fn(() => true);

    const { result } = renderHook(() => usePolling(fetcher, 10, shouldContinue));

    await waitFor(
      () => {
        expect(result.current.isPolling).toBe(false);
      },
      { timeout: 3000 }
    );
    expect(result.current.error).not.toBeNull();
    expect(attempts).toBeGreaterThanOrEqual(3);
  });

  it('cleanup: does not update state after unmount (BR-MD0-11)', async () => {
    let count = 0;
    const fetcher = vi.fn(async () => {
      count++;
      return count;
    });
    const shouldContinue = vi.fn(() => true);

    const { result, unmount } = renderHook(() => usePolling(fetcher, 20, shouldContinue));

    // Wait for at least one call
    await waitFor(() => {
      expect(result.current.data).not.toBeNull();
    });

    const countAtUnmount = count;
    unmount();

    // Wait a bit; count should not increase significantly after unmount
    await act(async () => {
      await new Promise((r) => setTimeout(r, 100));
    });

    // Allow at most 1 in-flight call
    expect(count).toBeLessThanOrEqual(countAtUnmount + 1);
  });
});
