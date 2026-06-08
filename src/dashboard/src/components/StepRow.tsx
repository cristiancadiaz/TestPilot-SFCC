// Step row for P4 Run Detail table
// React auto-escapes all text (error strings) — NEVER dangerouslySetInnerHTML (NFR-MD0-S7)

import type { StepResult } from '@/types/api';
import { ScreenshotThumbnail } from './ScreenshotThumbnail';

interface StepRowProps {
  step: StepResult;
  p95Ms?: number; // from BaselineComparison, if available
}

const STATUS_STYLES: Record<string, string> = {
  success: 'bg-green-50 border-green-200',
  failed: 'bg-red-50 border-red-200',
  skipped: 'bg-gray-50 border-gray-200',
};

const STATUS_ICONS: Record<string, string> = {
  success: '✓',
  failed: '✗',
  skipped: '–',
};

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function StepRow({ step, p95Ms }: StepRowProps) {
  const rowStyle = STATUS_STYLES[step.status] ?? 'bg-white';

  const p95Diff =
    p95Ms !== undefined ? step.duration_ms - p95Ms : null;
  const p95Label =
    p95Diff !== null
      ? p95Diff > 0
        ? `+${formatMs(p95Diff)}`
        : formatMs(p95Diff)
      : null;

  return (
    <tr className={['border-b', rowStyle].join(' ')}>
      <td className="px-3 py-2 font-mono text-sm">
        <span className="mr-2" aria-hidden="true">
          {STATUS_ICONS[step.status]}
        </span>
        {step.name}
        {step.phase === 'setup' && (
          <span className="ml-2 text-xs text-gray-400">(setup)</span>
        )}
      </td>

      <td className="px-3 py-2 text-sm text-right font-mono">
        {formatMs(step.duration_ms)}
        {p95Label && (
          <span
            className={['ml-2 text-xs', p95Diff && p95Diff > 0 ? 'text-red-500' : 'text-green-600'].join(' ')}
          >
            {p95Label} vs p95
          </span>
        )}
      </td>

      <td className="px-3 py-2 text-sm max-w-xs">
        {/* React auto-escapes error strings — safe by default (NFR-MD0-S7) */}
        {step.error && (
          <span className="text-red-700 font-mono text-xs break-all">{step.error}</span>
        )}
      </td>

      <td className="px-3 py-2">
        {step.screenshot_url && (
          <div className="w-32">
            <ScreenshotThumbnail
              url={step.screenshot_url}
              alt={`Captura: ${step.name} (${step.screenshot_state ?? 'unknown'})`}
            />
          </div>
        )}
      </td>
    </tr>
  );
}
