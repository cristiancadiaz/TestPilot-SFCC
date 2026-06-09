// Basic accessibility tests (NFR-MD0-U1, BR-MD0-17)
// Uses @testing-library/jest-dom assertions for accessible attributes

import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TrafficLight } from '@/components/TrafficLight';

describe('Accessibility: TrafficLight', () => {
  it('has role="status" on green', () => {
    render(<TrafficLight color="green" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('has role="status" on yellow', () => {
    render(<TrafficLight color="yellow" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('has role="status" on red', () => {
    render(<TrafficLight color="red" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('aria-label is human-readable for each color', () => {
    const { rerender } = render(<TrafficLight color="green" />);
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Aprobado');

    rerender(<TrafficLight color="yellow" />);
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Alerta');

    rerender(<TrafficLight color="red" />);
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Fallo');
  });

  it('icon is aria-hidden (decorative) — text provides the meaning', () => {
    render(<TrafficLight color="green" />);
    const icon = screen.getByText('✓');
    expect(icon).toHaveAttribute('aria-hidden', 'true');
  });

  it('text label is always visible (triple encoding BR-MD0-17)', () => {
    const colors = ['green', 'yellow', 'red'] as const;
    const labels = ['OK', 'Alerta', 'Fallo'];

    colors.forEach((color, i) => {
      const { unmount } = render(<TrafficLight color={color} />);
      expect(screen.getByText(labels[i])).toBeInTheDocument();
      unmount();
    });
  });
});
