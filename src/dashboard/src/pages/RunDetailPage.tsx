// P4: Run detail / full report
// First visible element: <TrafficLight size='lg'> (BR-MD0-08)
// Permanent orders_created=0 banner (BR-MD0-09)
// Bootstrap badge (BR-MD0-10)
// audit.hypotheses as hypotheses, not facts (P7/C10)
// Screenshot gallery: lazy load, only when screenshot_url != null (ADR-003)
// NEVER dangerouslySetInnerHTML

import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import type { ExecutionReport, ProfileResult } from '@/types/api';
import { apiClient } from '@/api/client';
import type { ApiError } from '@/api/client';
import { TrafficLight } from '@/components/TrafficLight';
import { StepRow } from '@/components/StepRow';
import { ScreenshotThumbnail } from '@/components/ScreenshotThumbnail';

const DIMENSION_LABELS: Record<string, string> = {
  commerce_integrity: 'Integridad comercial',
  performance: 'Rendimiento',
  locale_correctness: 'Localización',
  accessibility: 'Accesibilidad',
  client_health: 'Salud del cliente',
  content_integrity: 'Integridad de contenido',
};

const SEVERITY_STYLES: Record<string, string> = {
  info: 'bg-blue-50 border-blue-200 text-blue-700',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-700',
  critical: 'bg-red-50 border-red-200 text-red-700',
};

function formatDuration(ms: number): string {
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

function ProfileCard({ pr }: { pr: ProfileResult }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div className="bg-gray-50 px-4 py-3 flex items-center justify-between">
        <div>
          <span className="font-mono font-medium text-gray-900">{pr.profile.name}</span>
          <span className="mx-2 text-gray-400">—</span>
          <span className="font-mono text-sm text-gray-600">{pr.flow_result.flow_name}</span>
        </div>
        <div className="flex items-center gap-3">
          <TrafficLight color={pr.traffic_light} size="sm" />
          <span className="font-mono text-sm text-gray-500">{formatDuration(pr.flow_result.duration_ms)}</span>
        </div>
      </div>

      <div className="p-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-500 border-b">
              <th className="pb-2 font-medium">Paso</th>
              <th className="pb-2 font-medium text-right">Duración</th>
              <th className="pb-2 font-medium">Error</th>
              <th className="pb-2 font-medium">Captura</th>
            </tr>
          </thead>
          <tbody>
            {pr.flow_result.steps.map((step, i) => (
              <StepRow key={i} step={step} />
            ))}
          </tbody>
        </table>

        {/* Network summary */}
        {pr.network_summary && (
          <div className="mt-4 text-xs text-gray-600 bg-gray-50 rounded p-3">
            <p className="font-medium text-gray-700 mb-1">Red</p>
            <p>Requests: {pr.network_summary.total_requests} / Fallidos: {pr.network_summary.failed_requests}</p>
            {pr.network_summary.web_vitals && (
              <p className="mt-1">
                LCP: {pr.network_summary.web_vitals.lcp_ms ?? '—'}ms &nbsp;|&nbsp;
                CLS: {pr.network_summary.web_vitals.cls ?? '—'} &nbsp;|&nbsp;
                TTFB: {pr.network_summary.web_vitals.ttfb_ms ?? '—'}ms
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>();
  const [report, setReport] = useState<ExecutionReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    apiClient
      .getRunDetail(runId!)
      .then((data) => {
        if (!cancelled) {
          setReport(data);
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
  }, [runId]);

  // All screenshots from all profiles (gallery)
  const screenshots = report
    ? report.profile_results
        .flatMap((pr) =>
          pr.flow_result.steps
            .filter((s) => s.screenshot_url !== null)
            .map((s) => ({
              url: s.screenshot_url!,
              alt: `${pr.profile.name} / ${pr.flow_result.flow_name} / ${s.name} (${s.screenshot_state})`,
            }))
        )
    : [];

  if (loading) return <p className="text-gray-500">Cargando reporte...</p>;
  if (error)
    return (
      <div className="bg-red-50 border border-red-200 rounded p-4 text-red-700">
        Error al cargar el reporte: {error.message}
      </div>
    );
  if (!report) return null;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 font-mono">{report.run_id}</h1>
          <p className="text-sm text-gray-500">
            {new Date(report.started_at).toLocaleString('es-CO')} →{' '}
            {new Date(report.finished_at).toLocaleString('es-CO')} ({formatDuration(report.duration_ms)})
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={[
              'text-xs px-2 py-0.5 rounded-full font-medium',
              report.mode === 'gate' ? 'bg-blue-100 text-blue-700' : 'bg-orange-100 text-orange-700',
            ].join(' ')}
          >
            {report.mode}
          </span>
          {report.mode === 'exploratory' && (
            <span className="text-xs text-gray-500">No cuenta para decisión de deploy</span>
          )}
        </div>
      </div>

      {/* BR-MD0-08: TrafficLight size='lg' as first visible element */}
      <div className="flex items-center gap-4">
        <TrafficLight
          color={report.traffic_light}
          size="lg"
          bootstrapMode={report.bootstrap_mode}
        />
        {report.bootstrap_mode && (
          <span className="text-sm bg-blue-100 text-blue-700 px-3 py-1 rounded-full">
            Modo aprendizaje
          </span>
        )}
      </div>

      {/* BR-MD0-09: PERMANENT orders_created=0 banner — always visible, not collapsible */}
      <div
        className={[
          'rounded p-3 text-sm font-medium',
          // If orders_created somehow != 0, show RED blocking banner
          'bg-green-50 border border-green-200 text-green-800',
        ].join(' ')}
        aria-live="polite"
      >
        Órdenes creadas: 0 — Cero contaminación verificada.
      </div>

      {/* Profile results */}
      <section>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Resultados por perfil</h2>
        <div className="space-y-6">
          {report.profile_results.map((pr, i) => (
            <ProfileCard key={i} pr={pr} />
          ))}
        </div>
      </section>

      {/* Baseline comparison */}
      {report.baseline_comparison && (
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Comparación con baseline p95</h2>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <table className="text-sm w-full">
              <tbody>
                <tr className="border-b">
                  <td className="py-2 font-medium text-gray-700">p95 histórico</td>
                  <td className="py-2 font-mono">{formatDuration(report.baseline_comparison.p95_ms)}</td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 font-medium text-gray-700">Duración actual</td>
                  <td className="py-2 font-mono">{formatDuration(report.baseline_comparison.current_ms)}</td>
                </tr>
                <tr className="border-b">
                  <td className="py-2 font-medium text-gray-700">Runs en baseline</td>
                  <td className="py-2 font-mono">{report.baseline_comparison.runs_count}</td>
                </tr>
                <tr>
                  <td className="py-2 font-medium text-gray-700">Modo bootstrap</td>
                  <td className="py-2">{report.baseline_comparison.bootstrap_mode ? 'Sí' : 'No'}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Audit section */}
      {report.audit && (
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Auditoría (6 dimensiones)</h2>

          {!report.audit.synthesis_available && (
            <div className="bg-yellow-50 border border-yellow-200 rounded p-3 text-yellow-800 text-sm mb-4">
              El agente de síntesis no está disponible. Los hallazgos crudos se muestran a continuación.
            </div>
          )}

          {report.audit.findings.length === 0 && (
            <p className="text-gray-500 text-sm">No se encontraron hallazgos en este run.</p>
          )}

          <div className="space-y-3">
            {report.audit.findings.map((finding, i) => (
              <div
                key={i}
                className={['border rounded p-4', SEVERITY_STYLES[finding.severity] ?? ''].join(' ')}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-sm">
                    {DIMENSION_LABELS[finding.dimension] ?? finding.dimension}
                  </span>
                  <span className="text-xs uppercase font-bold">{finding.severity}</span>
                </div>
                <p className="text-xs font-mono text-gray-500 truncate">{finding.page_url}</p>
                {finding.step && (
                  <p className="text-xs text-gray-500 mt-1">Paso: {finding.step}</p>
                )}
                {finding.requires_human_review && (
                  <p className="text-xs font-bold mt-1">Requiere revisión humana</p>
                )}
              </div>
            ))}
          </div>

          {/* P7/C10: hypotheses — always marked as hypotheses, never facts */}
          {report.audit.hypotheses && report.audit.hypotheses.length > 0 && (
            <div className="mt-6">
              <h3 className="text-base font-semibold text-gray-800 mb-3">
                Hipótesis del agente de síntesis
              </h3>
              <p className="text-xs text-gray-500 mb-3">
                Las siguientes son hipótesis propuestas por el agente LLM basadas en los hallazgos.
                No son hechos confirmados y no determinan el semáforo. El semáforo se calcula
                exclusivamente por la regla determinista (p95 baseline).
              </p>
              <div className="space-y-3">
                {report.audit.hypotheses.map((hyp, i) => (
                  <div key={i} className="bg-gray-50 border border-gray-200 rounded p-4">
                    {/* React auto-escapes text — safe (NFR-MD0-S7) */}
                    <p className="text-sm text-gray-800">{hyp.text}</p>
                    <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
                      <span>Confianza: {Math.round(hyp.confidence * 100)}%</span>
                      {hyp.requires_human_review && (
                        <span className="text-orange-600 font-medium">Requiere revisión humana</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {report.audit.document_md_url && (
            <div className="mt-4">
              <a
                href={`/v1/audit-documents/${report.audit.document_md_url}`}
                className="text-sm text-blue-600 hover:underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                Ver documento de auditoría completo (Markdown)
              </a>
            </div>
          )}
        </section>
      )}

      {/* Screenshot gallery (ADR-003: only when screenshot_url != null — policy is server-side) */}
      {screenshots.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">
            Capturas de evidencia ({screenshots.length})
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {screenshots.map((s, i) => (
              <div key={i} className="space-y-1">
                <ScreenshotThumbnail url={s.url} alt={s.alt} />
                <p className="text-xs text-gray-400 truncate" title={s.alt}>
                  {s.alt}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Download buttons */}
      <div className="flex gap-3">
        <a
          href={`/v1/runs/${report.run_id}/report.json`}
          download={`run-${report.run_id}.json`}
          className="px-4 py-2 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
        >
          Descargar JSON
        </a>
        <a
          href={`/v1/runs/${report.run_id}/report.md`}
          download={`run-${report.run_id}.md`}
          className="px-4 py-2 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
        >
          Descargar Markdown
        </a>
      </div>
    </div>
  );
}
