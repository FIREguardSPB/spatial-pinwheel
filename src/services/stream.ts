import { QueryClient } from '@tanstack/react-query';
import { useAppStore } from '../store';
import { MockStreamService } from './mock';
import { EVENTS, QUERY_KEYS } from '../constants';

type EventHandler = (data: any) => void;

class StreamService {
    private eventSource: EventSource | null = null;
    private mockService: MockStreamService | null = null;
    private listeners: Map<string, Set<EventHandler>> = new Map();
    private queryClient: QueryClient | null = null;
    private reconnectTimer: any = null;

    constructor() {
        // Singleton init if needed
    }

    setQueryClient(client: QueryClient) {
        this.queryClient = client;
    }

    connect() {
        // Use strict UI Demo Mode flag for autonomous behavior
        const { isUiDemoMode, authToken, setConnectionStatus } = useAppStore.getState();

        this.disconnect();
        setConnectionStatus('reconnecting');

        // STRICT AUTONOMOUS CLIENT DEMO (No local server req)
        if (isUiDemoMode) {
            console.log('[Stream] Starting UI Demo Mode (Autonomous)');
            this.mockService = new MockStreamService(this.dispatch.bind(this));
            this.mockService.start();
            setConnectionStatus('connected');
            return;
        }

        // Real SSE (or Server-Side Mock)
        const baseUrl = import.meta.env.VITE_API_URL || '/api';
        const url = new URL(`${baseUrl}/stream`, window.location.origin);
        if (authToken) {
            url.searchParams.append('token', authToken);
        }

        this.eventSource = new EventSource(url.toString());

        this.eventSource.onopen = () => {
            console.log('[Stream] Connected');
            setConnectionStatus('connected');
        };

        this.eventSource.onerror = () => {
            console.error('[Stream] Error');
            setConnectionStatus('disconnected');
            this.eventSource?.close();
            // Auto reconnect
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = setTimeout(() => this.connect(), 5000);
        };

        // Listen for named events
        const events = Object.values(EVENTS);
        events.forEach(eventType => {
            this.eventSource?.addEventListener(eventType, (e: MessageEvent) => {
                try {
                    const payload = JSON.parse(e.data);
                    console.log('[Stream] Rx:', eventType, payload);
                    this.dispatch(eventType, payload);
                } catch (err) {
                    console.error('Parse error', err);
                }
            });
        });
    }

    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        if (this.mockService) {
            this.mockService.stop();
            this.mockService = null;
        }
        clearTimeout(this.reconnectTimer);
        useAppStore.getState().setConnectionStatus('disconnected');
    }

    // Dispatch to listeners and Invalidate Queries
    private dispatch(type: string, payload: any) {
        // 1. Notify listeners
        if (this.listeners.has(type)) {
            this.listeners.get(type)?.forEach(handler => handler(payload));
        }

        // 2. Invalidate Queries
        if (this.queryClient) {
            switch (type) {
                case EVENTS.SIGNAL_CREATED:
                case EVENTS.SIGNAL_UPDATED:
                    this.queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.SIGNALS] });
                    break;
                case EVENTS.POSITIONS_UPDATED:
                    this.queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.POSITIONS] });
                    break;
                case EVENTS.ORDERS_UPDATED:
                    this.queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ORDERS] });
                    break;
                case EVENTS.TRADE_FILLED:
                    this.queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.TRADES] });
                    this.queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.POSITIONS] });
                    break;
            }
        }
    }

    // Subscriptions
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
