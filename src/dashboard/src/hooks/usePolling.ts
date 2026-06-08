import { useState, useEffect, useRef } from 'react';
import type { ApiError } from '@/api/client';

interface UsePollingResult<T> {
  data: T | null;
  error: ApiError | null;
  isPolling: boolean;
}

// Pattern 1 from nfr-design.md
// Polls fetcher() every intervalMs (+/- 500ms jitter) while shouldContinue returns true.
// Stops after 3 consecutive failures (NFR-MD0-R1).
// Cleans up on unmount via cancelled flag (BR-MD0-11).
export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  shouldContinue: (data: T) => boolean
): UsePollingResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [isPolling, setIsPolling] = useState(true);
  const failureCount = useRef(0);
  // Keep latest refs to avoid stale closures without retriggering effect
  const fetcherRef = useRef(fetcher);
  const shouldContinueRef = useRef(shouldContinue);
  fetcherRef.current = fetcher;
  shouldContinueRef.current = shouldContinue;

  useEffect(() => {
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout>;

    const tick = async () => {
      try {
        const result = await fetcherRef.current();
        if (cancelled) return;
        setData(result);
        setError(null);
        failureCount.current = 0;
        if (shouldContinueRef.current(result)) {
          const jitter = Math.random() * 1000 - 500; // ±500ms NFR-MD0-P2
          timeoutId = setTimeout(tick, intervalMs + jitter);
        } else {
          setIsPolling(false);
        }
      } catch (err) {
        if (cancelled) return;
        failureCount.current += 1;
        if (failureCount.current >= 3) {
          // Pause after 3 consecutive failures — NFR-MD0-R1
          setError(err as ApiError);
          setIsPolling(false);
        } else {
          timeoutId = setTimeout(tick, intervalMs);
        }
      }
    };

    tick();

    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [intervalMs]); // only re-run if intervalMs changes; fetcher/shouldContinue via refs

  return { data, error, isPolling };
}
