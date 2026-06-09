import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { TrafficLight } from '@/components/TrafficLight';

describe('TrafficLight', () => {
  it('renders OK text and icon for green', () => {
    render(<TrafficLight color="green" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText('OK')).toBeInTheDocument();
    expect(screen.getByText('✓')).toBeInTheDocument();
  });

  it('renders Alerta text and icon for yellow', () => {
    render(<TrafficLight color="yellow" />);
    expect(screen.getByText('Alerta')).toBeInTheDocument();
    expect(screen.getByText('⚠')).toBeInTheDocument();
  });

  it('renders Fallo text and icon for red', () => {
    render(<TrafficLight color="red" />);
    expect(screen.getByText('Fallo')).toBeInTheDocument();
    expect(screen.getByText('✗')).toBeInTheDocument();
  });

  it('has role="status" and correct aria-label', () => {
    render(<TrafficLight color="green" />);
    const el = screen.getByRole('status');
    expect(el).toHaveAttribute('aria-label', 'Aprobado');
  });

  it('aria-label is Alerta for yellow', () => {
    render(<TrafficLight color="yellow" />);
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Alerta');
  });

  it('aria-label is Fallo for red', () => {
    render(<TrafficLight color="red" />);
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Fallo');
  });

  it('applies minimum height 96px for size=lg (BR-MD0-08)', () => {
    render(<TrafficLight color="green" size="lg" />);
    const el = screen.getByRole('status');
    // Tailwind min-h-24 = 6rem = 96px — class must be present
    expect(el.className).toMatch(/min-h-24/);
  });

  it('renders grey background in bootstrap mode with yellow (BR-MD0-10)', () => {
    render(<TrafficLight color="yellow" bootstrapMode={true} />);
    const el = screen.getByRole('status');
    expect(el.className).toMatch(/bg-gray-400/);
    expect(el.className).not.toMatch(/bg-yellow/);
  });

  it('does NOT apply grey in bootstrap mode with green', () => {
    render(<TrafficLight color="green" bootstrapMode={true} />);
    const el = screen.getByRole('status');
    expect(el.className).toMatch(/bg-green/);
    expect(el.className).not.toMatch(/bg-gray-400/);
  });

  it('does NOT apply grey in bootstrap mode with red', () => {
    render(<TrafficLight color="red" bootstrapMode={true} />);
    const el = screen.getByRole('status');
    expect(el.className).toMatch(/bg-red/);
    expect(el.className).not.toMatch(/bg-gray-400/);
  });
});
