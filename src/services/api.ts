import axios from 'axios';
import { useAppStore } from '../store';
import { toast } from 'sonner';
import { getApiBaseUrl } from './runtimeApi';

function extractRequestId(error: any): string | null {
    const data = error?.response?.data;
    return typeof data === 'object' && data?.request_id ? String(data.request_id) : null;
}

function buildErrorMessage(error: any): string {
    if (!error.response) {
        return 'Backend недоступен или не отвечает';
    }

    const data = error.response?.data;
    const requestId = typeof data === 'object' && data?.request_id ? ` [req:${data.request_id}]` : '';
    const payloadMessage = typeof data === 'object'
        ? data?.message || data?.detail || data?.error?.message || data?.error
        : undefined;

    const status = error.response?.status;
    const msg = payloadMessage || error.message || 'API Error';
    return `${status ? `${status}: ` : ''}${String(msg)}${requestId}`;
}

const BASE_URL = getApiBaseUrl();

function isCanceledOrAborted(error: any): boolean {
    const code = String(error?.code ?? '');
    const name = String(error?.name ?? '');
    return code === 'ERR_CANCELED' || code === 'ECONNABORTED' || name === 'CanceledError' || String(error?.message ?? '').toLowerCase().includes('canceled');
}

let lastToastKey = '';
let lastToastTs = 0;

function isBackgroundRuntimePath(path: string | null): boolean {
    if (!path) return false;
    return path.includes('/worker/status') || path.endsWith('/health') || path.includes('/health?');
}

function isReadOnlyRequest(error: any): boolean {
    return String(error?.config?.method ?? 'get').toUpperCase() === 'GET';
}

function isSoftReadPath(path: string | null): boolean {
    if (!path) return false;
    return [
        '/settings',
        '/settings/trading-schedule',
        '/settings/runtime-overview',
        '/state',
        '/state/orders',
        '/state/positions',
        '/state/trades',
        '/watchlist',
        '/signals',
        '/decision-log',
        '/account/summary',
        '/account/history',
        '/account/daily-stats',
        '/worker/status',
        '/bot/status',
        '/candles/',
        '/validation/',
        '/ml/',
        '/forensics/',
        '/metrics',
        '/tbank/stats',
        '/account/tbank/accounts',
        '/instruments/search',
        '/ui/',
    ].some((item) => path.includes(item));
}

export const apiClient = axios.create({
    baseURL: BASE_URL,
    timeout: 12000,
    headers: {
        'Content-Type': 'application/json',
    },
});

apiClient.interceptors.request.use(
    (config) => {
        const token = useAppStore.getState().authToken;
        if (token) {
            config.headers = config.headers ?? {};
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
    (response) => {
        if (response.config?.url?.includes('/health')) {
            useAppStore.getState().setBackendHealth(response.status >= 500 ? 'degraded' : 'ok', null);
        }
        return response;
    },
    (error) => {
        if (isCanceledOrAborted(error)) {
            return Promise.reject(error);
        }

        const message = buildErrorMessage(error);
        const requestId = extractRequestId(error);
        const path = error?.config?.url ? String(error.config.url) : null;
        const statusCode = error?.response?.status ?? null;
        const method = String(error?.config?.method ?? 'get').toUpperCase();

        const store = useAppStore.getState();
        if (isReadOnlyRequest(error) && isSoftReadPath(path)) {
            store.setBackendHealth('degraded', message);
            return Promise.reject(error);
        }

        if (method === 'GET' && isBackgroundRuntimePath(path)) {
            store.setBackendHealth('degraded', message);
            return Promise.reject(error);
        }

        if (!isBackgroundRuntimePath(path)) {
            store.reportApiError({
                message,
                requestId,
                path,
                statusCode,
            });

            const toastKey = `${statusCode ?? 'x'}:${path ?? 'unknown'}:${message}`;
            const now = Date.now();
            const shouldToast = toastKey !== lastToastKey || now - lastToastTs > 10000;
            if (shouldToast) {
                lastToastKey = toastKey;
                lastToastTs = now;
                if (statusCode === 401) {
                    toast.error('Unauthorized: проверь токен API');
                } else if (method !== 'GET') {
                    toast.error(message);
                }
            }
        }
        return Promise.reject(error);
    }
);


export async function listSettingsPresets() { const { data } = await apiClient.get('/settings/presets'); return data; }
export async function createSettingsPreset(payload: { name: string; description?: string }) { const { data } = await apiClient.post('/settings/presets', payload); return data; }
export async function getSettingsPreset(id: string) { const { data } = await apiClient.get(`/settings/presets/${encodeURIComponent(id)}`); return data; }
export async function updateSettingsPreset(id: string, payload: { name?: string; description?: string; settings_json?: Record<string, any> }) { const { data } = await apiClient.put(`/settings/presets/${encodeURIComponent(id)}`, payload); return data; }
export async function deleteSettingsPreset(id: string) { const { data } = await apiClient.delete(`/settings/presets/${encodeURIComponent(id)}`); return data; }
export async function applySettingsPreset(id: string) { const { data } = await apiClient.post(`/settings/presets/${encodeURIComponent(id)}/apply`); return data; }
