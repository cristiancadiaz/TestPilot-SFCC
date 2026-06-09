// P5: Run history with pagination and URL-synced filters
// Pattern 7 from nfr-design.md: filters synced to URL (BR-MD0-16)
// Server-side pagination 25 items (NFR-MD0-P3)
// Filters: date range, environment_id, traffic_light, flow, mode
// Reset to page 1 when filters change

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { RunListItem, TrafficLightColor, FlowName, RunMode } from '@/types/api';
import { FLOW_NAMES } from '@/types/api';
import { apiClient } from '@/api/client';
import type { ApiError } from '@/api/client';
import { TrafficLight } from '@/components/TrafficLight';
import { useEnvironments } from '@/hooks/useEnvironments';

const PAGE_SIZE = 25;

function defaultFrom(): string {
  const d = new Date();
  d.setDate(d.getDate() - 7);
  return d.toISOString().slice(0, 10);
}

function defaultTo(): string {
  return new Date().toISOString().slice(0, 10);
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' });
}

function formatDuration(ms: number): string {
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

export function HistoryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { environments } = useEnvironments();

  // Read filters from URL (BR-MD0-16)
  const from = searchParams.get('from') ?? defaultFrom();
  const to = searchParams.get('to') ?? defaultTo();
  const envFilter = searchParams.get('env') ?? '';
  const tlFilter = (searchParams.get('tl') as TrafficLightColor | '') ?? '';
  const flowFilter = (searchParams.get('flow') as FlowName | '') ?? '';
  const modeFilter = (searchParams.get('mode') as RunMode | '') ?? '';
  const page = Number(searchParams.get('page') ?? 1);

  const updateParam = useCallback(
    (key: string, value: string | undefined) => {
      const next = new URLSearchParams(searchParams);
      if (value) next.set(key, value);
      else next.delete(key);
      next.set('page', '1'); // reset to page 1 on filter change
      setSearchParams(next);
    },
    [searchParams, setSearchParams]
  );

  const setPage = (p: number) => {
    const next = new URLSearchParams(searchParams);
    next.set('page', String(p));
    setSearchParams(next);
  };

  const [items, setItems] = useState<RunListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    apiClient
      .listRuns({
        from,
        to,
        environment_id: envFilter || undefined,
        traffic_light: (tlFilter as TrafficLightColor) || undefined,
        flow: (flowFilter as FlowName) || undefined,
        mode: (modeFilter as RunMode) || undefined,
        page,
        page_size: PAGE_SIZE,
      })
      .then((resp) => {
        if (!cancelled) {
          setItems(resp.items);
          setTotal(resp.total);
          setHasMore(resp.has_more);
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
  }, [from, to, envFilter, tlFilter, flowFilter, modeFilter, page]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Historial de runs</h1>

      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Desde</label>
          <input
            type="date"
            value={from}
            onChange={(e) => updateParam('from', e.target.value)}
            className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Hasta</label>
          <input
            type="date"
            value={to}
            onChange={(e) => updateParam('to', e.target.value)}
            className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Ambiente</label>
          <select
            value={envFilter}
            onChange={(e) => updateParam('env', e.target.value || undefined)}
            className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todos</option>
            {environments.map((env) => (
              <option key={env.environment_id} value={env.environment_id}>
                {env.display_name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Semáforo</label>
          <select
            value={tlFilter}
            onChange={(e) => updateParam('tl', e.target.value || undefined)}
            className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todos</option>
            <option value="green">Verde</option>
            <option value="yellow">Amarillo</option>
            <option value="red">Rojo</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Flow</label>
          <select
            value={flowFilter}
            onChange={(e) => updateParam('flow', e.target.value || undefined)}
            className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todos</option>
            {FLOW_NAMES.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Modo</label>
          <select
            value={modeFilter}
            onChange={(e) => updateParam('mode', e.target.value || undefined)}
            className="w-full border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todos</option>
            <option value="gate">gate</option>
            <option value="exploratory">exploratory</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4 text-red-700 text-sm">
          Error al cargar historial: {error.message}
        </div>
      )}

      {loading && <p className="text-gray-500 text-sm">Cargando...</p>}

      {!loading && !error && (
        <>
          <div className="text-sm text-gray-500">
            {total} runs encontrados
          </div>

          {/* Table */}
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b text-xs font-medium text-gray-700">
                  <th className="px-4 py-3 text-left">Fecha/hora</th>
                  <th className="px-4 py-3 text-left">Ambiente</th>
                  <th className="px-4 py-3 text-center">Semáforo</th>
                  <th className="px-4 py-3 text-right">Duración</th>
                  <th className="px-4 py-3 text-center">Modo</th>
                  <th className="px-4 py-3 text-left">Perfiles</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.run_id} className="border-b hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-700">{formatDate(item.started_at)}</td>
                    <td className="px-4 py-3 font-mono text-sm text-gray-600">{item.environment_id}</td>
                    <td className="px-4 py-3 text-center">
                      <TrafficLight
                        color={item.traffic_light}
                        size="sm"
                        bootstrapMode={item.bootstrap_mode}
                      />
                      {item.bootstrap_mode && (
                        <span className="block text-xs text-gray-400 mt-1">bootstrap</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm text-gray-600">
                      {formatDuration(item.duration_ms)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className={[
                          'text-xs px-2 py-0.5 rounded-full font-medium',
                          item.mode === 'gate'
                            ? 'bg-blue-100 text-blue-700'
                            : 'bg-orange-100 text-orange-700',
                        ].join(' ')}
                      >
                        {item.mode}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {item.profiles_executed.map((p) => (
                          <span
                            key={p}
                            className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded font-mono"
                          >
                            {p}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <a
                        href={`/runs/${item.run_id}`}
                        className="text-blue-600 hover:underline text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-1"
                      >
                        Ver detalle
                      </a>
                    </td>
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                      No hay runs para los filtros seleccionados.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              Página {page} de {totalPages}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(page - 1)}
                disabled={page <= 1}
                className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                Anterior
              </button>
              <button
                onClick={() => setPage(page + 1)}
                disabled={!hasMore || page >= totalPages}
                className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                Siguiente
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
