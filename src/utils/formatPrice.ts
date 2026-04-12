export function priceDecimals(value?: number | null): number {
  if (value == null || !Number.isFinite(value)) return 2;
  const abs = Math.abs(value);
  if (abs < 10) return 4;
  if (abs < 100) return 3;
  return 2;
}

export function formatPrice(value?: number | null): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return Number(value).toFixed(priceDecimals(value));
}

export function formatPercent(value?: number | null, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${Number(value).toFixed(digits)}%`;
}
