import { useState, useEffect, useCallback } from 'react';
import type { EnvironmentConfig } from '@/types/api';
import { apiClient } from '@/api/client';
import type { ApiError } from '@/api/client';

interface UseEnvironmentsResult {
  environments: EnvironmentConfig[];
  activeEnvironments: EnvironmentConfig[]; // only active=true (for P2 selector)
  loading: boolean;
  error: ApiError | null;
  refetch: () => void;
}

export function useEnvironments(): UseEnvironmentsResult {
  const [environments, setEnvironments] = useState<EnvironmentConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    apiClient
      .getEnvironments()
      .then((data) => {
        if (!cancelled) {
          setEnvironments(data);
          setLoading(false);
        }
      })
      .catch((err: ApiError) => {
        if (!cancelled) {
          setError(err);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [tick]);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  return {
    environments,
    activeEnvironments: environments.filter((e) => e.active),
    loading,
    error,
    refetch,
  };
}
