export function fmtMoney(value: number | null | undefined, currency = '₽') {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ${currency}`;
}

export function fmtNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return Number(value).toLocaleString('ru-RU', { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}

export function fmtPercent(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${Number(value).toLocaleString('ru-RU', { maximumFractionDigits: digits })}%`;
}

export function fmtDateTime(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === '') return '—';
  const date = typeof value === 'number'
    ? new Date(value < 10_000_000_000 ? value * 1000 : value)
    : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString('ru-RU');
}

export function fmtMode(value: string | null | undefined) {
  const normalized = (value ?? '').toLowerCase();
  if (normalized === 'auto_paper' || normalized === 'paper') return 'Paper';
  if (normalized === 'auto_live' || normalized === 'live') return 'Live';
  if (normalized === 'review') return 'Ручное ревью';
  return value || '—';
}

export function fmtBool(value: boolean | null | undefined, yes = 'Да', no = 'Нет') {
  if (value === null || value === undefined) return '—';
  return value ? yes : no;
}
