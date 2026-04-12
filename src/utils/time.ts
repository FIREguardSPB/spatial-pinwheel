const DEFAULT_TZ = 'Europe/Moscow';

export function formatInTimeZone(
  value: string | number | Date | null | undefined,
  options: Intl.DateTimeFormatOptions = {},
  timeZone = DEFAULT_TZ,
): string {
  if (value == null || value === '') return '—';
  let date: Date;
  if (value instanceof Date) {
    date = value;
  } else if (typeof value === 'string') {
    date = new Date(value);
  } else {
    const numeric = Number(value);
    const ts = numeric > 10_000_000_000 ? numeric : numeric * 1000;
    date = new Date(ts);
  }
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString('ru-RU', { timeZone, ...options });
}

export function formatDateTimeMsk(value: string | number | Date | null | undefined, options: Intl.DateTimeFormatOptions = {}) {
  return formatInTimeZone(value, {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    ...options,
  });
}

export function formatTimeMsk(value: string | number | Date | null | undefined, options: Intl.DateTimeFormatOptions = {}) {
  return formatInTimeZone(value, {
    hour: '2-digit',
    minute: '2-digit',
    ...options,
  });
}
