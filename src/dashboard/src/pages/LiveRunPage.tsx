// P3: Live run view with polling
// usePolling with intervalMs=3000 (NFR-MD0-P2)
// Generic profile x flow matrix — no hardcoded names or counts (H5.5 AC1)
// BR-MD0-09: orders_created banner (red blocking)
// BR-MD0-10: bootstrap badge
// BR-MD0-11: stop polling on terminal state, navigate after 1s delay
// BR-MD0-14: 30 min timeout warning
// NFR-MD0-R1: 3 failures -> banner

import { useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import type { RunStatus, ProfileRunStatus } from '@/types/api';
import { apiClient } from '@/api/client';
import { usePolling } from '@/hooks/usePolling';

const TERMINAL_STATES: RunStatus['state'][] = ['completed', 'failed'];
const PROFILE_CELL_STATES = ['pending', 'running', 'success', 'failed', 'error'] as const;

const CELL_STYLES: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-600',
  running: 'bg-blue-100 text-blue-700 animate-pulse',
  success: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  error: 'bg-orange-100 text-orange-700',
};
const CELL_LABELS: Record<string, string> = {
  pending: 'Pendiente',
  running: 'Ejecutando',
  success: 'OK',
  failed: 'Fallo',
  error: 'Error',
};

function formatDuration(ms: number): string {
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

function ProfileCell({ prs }: { prs: ProfileRunStatus }) {
  return (
    <td className="px-3 py-2 text-center">
      <span
        className={[
          'inline-block px-2 py-0.5 rounded text-xs font-medium',
          CELL_STYLES[prs.state] ?? 'bg-gray-100',
        ].join(' ')}
        aria-label={`${prs.profile_id} / ${prs.flow_name}: ${prs.state}`}
      >
        {CELL_LABELS[prs.state] ?? prs.state}
      </span>
      {prs.current_step && (
        <p className="text-xs text-gray-500 mt-0.5 font-mono">{prs.current_step}</p>
      )}
      <p className="text-xs text-gray-400">{formatDuration(prs.duration_ms)}</p>
    </td>
  );
}

export function LiveRunPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const navigatedRef = useRef(false);
  const startTimeRef = useRef(Date.now());

  const { data: status, error, isPolling } = usePolling<RunStatus>(
    () => apiClient.getRunStatus(runId!),
    3000,
    (data) => !TERMINAL_STATES.includes(data.state)
  );

  // BR-MD0-11: navigate to detail after 1s delay when terminal
  useEffect(() => {
    if (!status) return;
    if (TERMINAL_STATES.includes(status.state) && !navigatedRef.current) {
      navigatedRef.current = true;
      const timer = setTimeout(() => {
        navigate(`/runs/${runId}`);
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [status, navigate, runId]);

  // BR-MD0-14: 30 min timeout warning
  const elapsedMs = status ? Date.now() - startTimeRef.current : 0;
  const showTimeoutWarning = elapsedMs > 30 * 60 * 1000 && isPolling;

  // Derive unique flows from profile_statuses (generic matrix — no hardcoded flows)
  const flowsInRun = status
    ? Array.from(new Set(status.profile_statuses.map((ps) => ps.flow_name)))
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">
          Run en curso: <span className="font-mono text-lg">{runId}</span>
        </h1>
        {isPolling && (
          <span className="flex items-center gap-2 text-sm text-blue-600">
            <span className="inline-block w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
            Actualizando...
          </span>
        )}
      </div>

      {/* Run metadata */}
      {status && (
        <div className="flex flex-wrap gap-4 text-sm text-gray-600">
          <span>Ambiente: <strong>{status.environment_id}</strong></span>
          <span>
            Inicio: <strong>{new Date(status.started_at).toLocaleString('es-CO')}</strong>
          </span>
          <span
            className={[
              'px-2 py-0.5 rounded-full text-xs font-medium',
              status.mode === 'gate' ? 'bg-blue-100 text-blue-700' : 'bg-orange-100 text-orange-700',
            ].join(' ')}
          >
            {status.mode}
          </span>
        </div>
      )}

      {/* BR-MD0-10: bootstrap badge */}
      {status?.bootstrap_mode && (
        <div className="bg-blue-50 border border-blue-200 rounded p-3 text-blue-800 text-sm">
          Modo aprendizaje (Aprendizaje) — los primeros 14 runs exitosos establecen el baseline.
        </div>
      )}

      {/* BR-MD0-09: CRITICAL banner if orders_created != 0 (invariant guarantees 0) */}
      {status && status.orders_created !== 0 && (
        <div
          role="alert"
          className="bg-red-600 text-white rounded p-4 font-bold text-center"
          aria-live="assertive"
        >
          INCIDENTE: orders_created = {status.orders_created}. Esto NO debería ocurrir. Escalar
          inmediatamente al equipo de plataforma.
        </div>
      )}

      {/* NFR-MD0-R1: connection failure banner after 3 consecutive failures */}
      {error && !isPolling && (
        <div
          role="alert"
          className="bg-yellow-50 border border-yellow-300 rounded p-4 text-yellow-800 text-sm"
        >
          Conexión interrumpida — reintentando en 30 s. ({error.message})
        </div>
      )}

      {/* BR-MD0-14: 30 min timeout warning */}
      {showTimeoutWarning && (
        <div className="bg-orange-50 border border-orange-200 rounded p-3 text-orange-800 text-sm">
          Advertencia: El run lleva más de 30 minutos. Puede haber un problema de timeout.
        </div>
      )}

      {/* Generic matrix profile x flow (H5.5 AC1 — no hardcoded names/counts) */}
      {status && status.profile_statuses.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse bg-white rounded-lg shadow">
            <thead>
              <tr className="bg-gray-50 border-b">
                <th className="px-3 py-2 text-left font-medium text-gray-700">Perfil</th>
                {flowsInRun.map((flow) => (
                  <th key={flow} className="px-3 py-2 text-center font-medium text-gray-700 font-mono text-xs">
                    {flow}
                  </th>
                ))}
                <th className="px-3 py-2 text-right font-medium text-gray-700">Duración</th>
              </tr>
            </thead>
            <tbody>
              {Array.from(new Set(status.profile_statuses.map((ps) => ps.profile_id))).map(
                (profileId) => {
                  const profileStatuses = status.profile_statuses.filter(
                    (ps) => ps.profile_id === profileId
                  );
                  const totalDuration = profileStatuses.reduce(
                    (sum, ps) => sum + ps.duration_ms,
                    0
                  );

                  return (
                    <tr key={profileId} className="border-b">
                      <td className="px-3 py-2 font-mono text-sm font-medium">{profileId}</td>
                      {flowsInRun.map((flow) => {
                        const ps = profileStatuses.find((p) => p.flow_name === flow);
                        if (!ps) {
                          return (
                            <td key={flow} className="px-3 py-2 text-center text-gray-300">
                              —
                            </td>
                          );
                        }
                        return <ProfileCell key={flow} prs={ps} />;
                      })}
                      <td className="px-3 py-2 text-right font-mono text-sm text-gray-600">
                        {formatDuration(totalDuration)}
                      </td>
                    </tr>
                  );
                }
              )}
            </tbody>
          </table>
        </div>
      )}

      {!status && !error && (
        <p className="text-gray-500">Cargando estado del run...</p>
      )}

      {/* Terminal state: show transition message */}
      {status && TERMINAL_STATES.includes(status.state) && (
        <div className="text-center text-gray-600 text-sm">
          Run {status.state === 'completed' ? 'completado' : 'fallido'}. Redirigiendo al detalle...
        </div>
      )}

      {/* Accessibility note: list valid states for SR */}
      <div className="sr-only" aria-live="polite">
        {status
          ? `Estado del run: ${status.state}. ${status.profile_statuses.length} perfiles.`
          : 'Cargando...'}
      </div>

      {/* Suppress unused import warning */}
      {PROFILE_CELL_STATES.length > 0 && null}
    </div>
  );
}
