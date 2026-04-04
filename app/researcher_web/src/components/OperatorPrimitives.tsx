import React from 'react';

export function StatusBadge({ label, tone = 'neutral' }: { label: string; tone?: 'neutral' | 'good' | 'warn' | 'bad' | 'info' }) {
  return <span className={`status-badge status-badge--${tone}`}>{label}</span>;
}

export function SummaryCard({ label, value, tone = 'neutral' }: { label: string; value: string; tone?: 'neutral' | 'good' | 'warn' | 'bad' | 'info' }) {
  return (
    <div className="summary-card">
      <p className="summary-card__label">{label}</p>
      <p className={`summary-card__value summary-card__value--${tone}`}>{value}</p>
    </div>
  );
}

export function KbdMono({ children }: { children: React.ReactNode }) {
  return <span className="mono-pill">{children}</span>;
}
