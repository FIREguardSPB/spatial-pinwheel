const configuredApiBase = import.meta.env.VITE_API_URL || '/api/v1';
const directApiBase = (import.meta.env.VITE_DIRECT_API_BASE_URL || '').trim();

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, '');
}

function trimLeadingSlash(value: string): string {
  return value.replace(/^\/+/, '');
}

export function isAbsoluteUrl(value: string): boolean {
  return /^https?:\/\//i.test(value);
}

export function getApiBaseUrl(): string {
  if (directApiBase) {
    return trimTrailingSlash(directApiBase);
  }
  if (isAbsoluteUrl(configuredApiBase)) {
    return trimTrailingSlash(configuredApiBase);
  }
  return configuredApiBase;
}

export function joinApiPath(path: string): string {
  const base = getApiBaseUrl();
  const normalizedPath = trimLeadingSlash(path);

  if (isAbsoluteUrl(base)) {
    return new URL(normalizedPath, `${base}/`).toString();
  }

  return `${trimTrailingSlash(base)}/${normalizedPath}`;
}

export function buildBrowserUrl(path: string): string {
  const joined = joinApiPath(path);
  if (isAbsoluteUrl(joined)) {
    return joined;
  }
  return new URL(joined, window.location.origin).toString();
}

export function getStreamUrl(token?: string | null): string {
  const url = new URL(buildBrowserUrl('stream'));
  if (token) {
    url.searchParams.set('token', token);
  }
  return url.toString();
}

export function getApiBaseDebugLabel(): string {
  const base = getApiBaseUrl();
  if (isAbsoluteUrl(base)) {
    return `${base} (direct)`;
  }
  return `${base} (via same-origin/proxy)`;
}
