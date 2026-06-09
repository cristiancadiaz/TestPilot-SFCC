// P5 History run summary card
// NEVER dangerouslySetInnerHTML (NFR-MD0-S7)

import { useNavigate } from 'react-router-dom';
import type { RunListItem } from '@/types/api';
import { TrafficLight } from './TrafficLight';

interface RunCardProps {
  item: RunListItem;
}

function formatDuration(ms: number): string {
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}m ${remaining}s`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('es-CO', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
}

export function RunCard({ item }: RunCardProps) {
  const navigate = useNavigate();

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => navigate(`/runs/${item.run_id}`)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') navigate(`/runs/${item.run_id}`);
      }}
      className="flex items-center gap-4 p-4 bg-white rounded-lg shadow hover:shadow-md cursor-pointer transition-shadow"
      aria-label={`Ver detalles del run ${item.display_name}`}
    >
      <TrafficLight color={item.traffic_light} size="sm" bootstrapMode={item.bootstrap_mode} />

      <div className="flex-1 min-w-0">
        <p className="font-medium text-gray-900 truncate">{item.display_name}</p>
        <p className="text-sm text-gray-500">{formatDate(item.started_at)}</p>
      </div>

      <div className="flex items-center gap-2 shrink-0">
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

        {item.bootstrap_mode && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
            bootstrap
          </span>
        )}

        <span className="text-sm text-gray-500 font-mono">{formatDuration(item.duration_ms)}</span>
      </div>
    </div>
  );
}
