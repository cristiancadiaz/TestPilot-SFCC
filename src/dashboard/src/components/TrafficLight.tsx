// Pattern 3 from nfr-design.md
// Triple encoding: color + text + icon (BR-MD0-17, NFR-MD0-U2)
// role="status" + aria-label for screen readers (NFR-MD0-U1)
// NEVER dangerouslySetInnerHTML (NFR-MD0-S7)

import type { TrafficLightColor } from '@/types/api';

interface TrafficLightProps {
  color: TrafficLightColor;
  size?: 'sm' | 'lg';
  bootstrapMode?: boolean;
}

type Config = {
  bg: string;
  text: string;
  icon: string;
  aria: string;
};

const CONFIG: Record<TrafficLightColor, Config> = {
  green: { bg: 'bg-green-500', text: 'OK', icon: '✓', aria: 'Aprobado' },
  yellow: { bg: 'bg-yellow-500', text: 'Alerta', icon: '⚠', aria: 'Alerta' },
  red: { bg: 'bg-red-600', text: 'Fallo', icon: '✗', aria: 'Fallo' },
};

export function TrafficLight({ color, size = 'lg', bootstrapMode = false }: TrafficLightProps) {
  const config = CONFIG[color];
  // BR-MD0-10: in bootstrap mode, yellow renders as grey (no false alarm)
  const muted = bootstrapMode && color === 'yellow';

  const sizeClasses = size === 'lg' ? 'min-h-24 text-2xl px-6 py-4' : 'h-8 text-sm px-3 py-1';

  return (
    <div
      role="status"
      aria-label={config.aria}
      className={[
        'inline-flex items-center gap-2 rounded-full font-bold text-white',
        muted ? 'bg-gray-400' : config.bg,
        sizeClasses,
      ].join(' ')}
    >
      <span aria-hidden="true">{config.icon}</span>
      <span>{config.text}</span>
    </div>
  );
}
