import { QueryClient } from '@tanstack/react-query';
import { useAppStore } from '../store';
import { MockStreamService } from './mock';
import { EVENTS, QUERY_KEYS } from '../constants';
import { getStreamUrl } from './runtimeApi';

type EventHandler = (data: any) => void;

const HEARTBEAT_STALE_MS = 20_000;
const HARD_DISCONNECT_AFTER_MS = 60_000;
const WATCHDOG_INTERVAL_MS = 5_000;
const FORCED_RECONNECT_DELAY_MS = 3_000;

class StreamService {
    private eventSource: EventSource | null = null;
    private mockService: MockStreamService | null = null;
    private listeners: Map<string, Set<EventHandler>> = new Map();
    private queryClient: QueryClient | null = null;
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    private watchdogTimer: ReturnType<typeof setInterval> | null = null;
    private intentionalClose = false;
    private lastActivityAt = 0;
    private reconnectScheduled = false;
    private lastInvalidationAt: Partial<Record<string, number>> = {};

    setQueryClient(client: QueryClient) {
        this.queryClient = client;
    }

    connect(force = false) {
        const { isUiDemoMode, authToken, setConnectionStatus } = useAppStore.getState();

        this.intentionalClose = false;

        if (isUiDemoMode) {
            this.disconnect(true);
            this.mockService = new MockStreamService(this.dispatch.bind(this));
            this.mockService.start();
            setConnectionStatus('connected');
            return;
        }

        if (!force && this.eventSource && this.eventSource.readyState !== EventSource.CLOSED) {
            return;
        }

        this.cleanupEventSource();
        this.clearReconnectTimer();
        this.startWatchdog();
        this.reconnectScheduled = false;
        this.lastActivityAt = Date.now();

        this.eventSource = new EventSource(getStreamUrl(authToken));

        this.eventSource.onopen = () => {
            const store = useAppStore.getState();
            this.lastActivityAt = Date.now();
            this.reconnectScheduled = false;
            setConnectionStatus('connected');
            store.setBackendHealth('ok', null);
            store.clearApiError();
        };

        this.eventSource.onerror = () => {
            if (this.intentionalClose) {
                return;
            }

            const store = useAppStore.getState();
            const idleMs = Date.now() - this.lastActivityAt;
            if (idleMs > HEARTBEAT_STALE_MS && store.connectionStatus === 'connected') {
                setConnectionStatus('reconnecting');
            }

            if (this.eventSource?.readyState === EventSource.CLOSED && idleMs > HARD_DISCONNECT_AFTER_MS) {
                this.scheduleReconnect();
            }
        };

        const eventTypes = Object.values(EVENTS);
        eventTypes.forEach((eventType) => {
            this.eventSource?.addEventListener(eventType, (e: MessageEvent) => {
                this.lastActivityAt = Date.now();

                if (eventType === EVENTS.HEARTBEAT) {
                    if (useAppStore.getState().connectionStatus !== 'connected') {
                        useAppStore.getState().setConnectionStatus('connected');
                    }
                    return;
                }

                try {
                    const payload = JSON.parse(e.data);
                    if (useAppStore.getState().connectionStatus !== 'connected') {
                        useAppStore.getState().setConnectionStatus('connected');
                    }
                    this.dispatch(eventType, payload);
                } catch (err) {
                    if (import.meta.env.DEV) {
                        console.error('[Stream] Parse error', err);
                    }
                }
            });
        });
    }

    disconnect(preserveIntentionalClose = false) {
        if (!preserveIntentionalClose) {
            this.intentionalClose = true;
        }
        this.clearReconnectTimer();
        this.stopWatchdog();
        this.cleanupEventSource();
        if (this.mockService) {
            this.mockService.stop();
            this.mockService = null;
        }
        useAppStore.getState().setConnectionStatus('disconnected');
    }

    private cleanupEventSource() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }

    private clearReconnectTimer() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        this.reconnectScheduled = false;
    }

    private startWatchdog() {
        this.stopWatchdog();
        this.watchdogTimer = setInterval(() => {
            if (this.intentionalClose || !this.eventSource) {
                return;
            }

            const idleMs = Date.now() - this.lastActivityAt;
            const store = useAppStore.getState();

            if (idleMs > HARD_DISCONNECT_AFTER_MS) {
                if (store.connectionStatus !== 'disconnected') {
                    store.setConnectionStatus('disconnected');
                }
                this.scheduleReconnect();
                return;
            }

            if (idleMs > HEARTBEAT_STALE_MS) {
                if (store.connectionStatus === 'connected') {
                    store.setConnectionStatus('reconnecting');
                }
                return;
            }

            if (store.connectionStatus !== 'connected') {
                store.setConnectionStatus('connected');
            }
        }, WATCHDOG_INTERVAL_MS);
    }

    private stopWatchdog() {
        if (this.watchdogTimer) {
            clearInterval(this.watchdogTimer);
            this.watchdogTimer = null;
        }
    }

    private scheduleReconnect() {
        if (this.reconnectScheduled || this.intentionalClose) {
            return;
        }
        this.reconnectScheduled = true;
        this.clearReconnectTimer();
        this.reconnectScheduled = true;
        this.reconnectTimer = setTimeout(() => {
            this.cleanupEventSource();
            this.connect(true);
        }, FORCED_RECONNECT_DELAY_MS);
    }


    private invalidateQueryThrottled(queryKey: readonly unknown[], minIntervalMs: number) {
        if (!this.queryClient) {
            return;
        }

        const cacheKey = JSON.stringify(queryKey);
        const now = Date.now();
        const lastRun = this.lastInvalidationAt[cacheKey] ?? 0;
        if (now - lastRun < minIntervalMs) {
            return;
        }

        this.lastInvalidationAt[cacheKey] = now;
        this.queryClient.invalidateQueries({ queryKey });
    }

    private dispatch(type: string, payload: any) {
        if (this.listeners.has(type)) {
            this.listeners.get(type)?.forEach((handler) => handler(payload));
        }

        if (!this.queryClient) {
            return;
        }

        const invalidateUi = (key: readonly unknown[], minIntervalMs = 2_000) => {
            this.invalidateQueryThrottled(key, minIntervalMs);
        };

        switch (type) {
            case EVENTS.SIGNAL_CREATED:
            case EVENTS.SIGNAL_UPDATED:
                this.invalidateQueryThrottled([QUERY_KEYS.SIGNALS], 7_500);
                invalidateUi(['ui', 'signals'], 5_000);
                invalidateUi(['ui', 'dashboard'], 7_500);
                break;
            case EVENTS.POSITIONS_UPDATED:
                this.invalidateQueryThrottled([QUERY_KEYS.POSITIONS], 5_000);
                invalidateUi(['ui', 'dashboard'], 5_000);
                invalidateUi(['ui', 'account'], 5_000);
                break;
            case EVENTS.ORDERS_UPDATED:
                this.invalidateQueryThrottled([QUERY_KEYS.ORDERS], 5_000);
                invalidateUi(['ui', 'dashboard'], 5_000);
                break;
            case EVENTS.TRADE_FILLED:
                this.queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.TRADES] });
                this.invalidateQueryThrottled([QUERY_KEYS.POSITIONS], 5_000);
                invalidateUi(['ui', 'trades'], 5_000);
                invalidateUi(['ui', 'dashboard'], 7_500);
                invalidateUi(['ui', 'account'], 5_000);
                break;
            case EVENTS.KLINE:
                invalidateUi(['ui', 'dashboard'], 10_000);
                break;
            default:
                break;
        }
    }

    on(type: string, handler: EventHandler) {
        if (!this.listeners.has(type)) {
            this.listeners.set(type, new Set());
        }
        this.listeners.get(type)?.add(handler);
        return () => this.off(type, handler);
    }

    off(type: string, handler: EventHandler) {
        this.listeners.get(type)?.delete(handler);
    }
}

export const streamService = new StreamService();
