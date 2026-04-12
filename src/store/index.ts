import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";

type ConnectionStatus = "connected" | "disconnected" | "reconnecting";
type Theme = "dark" | "light";

type BackendHealthStatus = "unknown" | "ok" | "degraded" | "error";

type RuntimeAlert = {
    message: string;
    requestId?: string | null;
    statusCode?: number | null;
    path?: string | null;
    ts: number;
};

type BackendSourcePayload = {
    sourceLabel: string;
    brokerProvider: string;
    brokerSandbox: boolean;
    isMockMode?: boolean;
};

interface AppState {
    authToken: string | null;
    setAuthToken: (token: string | null) => void;

    theme: Theme;
    toggleTheme: () => void;

    isUiDemoMode: boolean;
    isMockMode: boolean;
    setMockMode: (isMock: boolean) => void;

    connectionStatus: ConnectionStatus;
    setConnectionStatus: (status: ConnectionStatus) => void;

    backendHealth: BackendHealthStatus;
    backendMessage: string | null;
    lastApiError: RuntimeAlert | null;
    setBackendHealth: (status: BackendHealthStatus, message?: string | null) => void;
    reportApiError: (payload: Omit<RuntimeAlert, "ts">) => void;
    clearApiError: () => void;

    sourceLabel: string;
    brokerProvider: string;
    brokerSandbox: boolean;
    setBackendSource: (payload: BackendSourcePayload) => void;

    selectedInstrument: string;
    setSelectedInstrument: (symbol: string) => void;

    selectedTimeframe: string;
    setSelectedTimeframe: (tf: string) => void;

    candles: Record<string, any[]>;
    addCandle: (symbol: string, tf: string, candle: any) => void;
    replaceCandles: (symbol: string, tf: string, next: any[]) => void;
    mergeCandles: (symbol: string, tf: string, next: any[]) => void;
    clearCandles: () => void;
}

export const useAppStore = create<AppState>()(
    devtools(
        persist(
            (set) => ({
                authToken: import.meta.env.VITE_API_TOKEN || null,
                setAuthToken: (token) => set({ authToken: token }),

                theme: "dark",
                toggleTheme: () => set((state) => ({
                    theme: state.theme === "dark" ? "light" : "dark",
                })),

                isUiDemoMode: import.meta.env.VITE_UI_DEMO_MODE === "true",
                isMockMode: import.meta.env.VITE_UI_DEMO_MODE === "true",
                setMockMode: (isMock) => set((state) => ({ isMockMode: state.isUiDemoMode ? isMock : false })),

                connectionStatus: "disconnected",
                setConnectionStatus: (status) => set({ connectionStatus: status }),

                backendHealth: "unknown",
                backendMessage: null,
                lastApiError: null,
                setBackendHealth: (status, message = null) => set({ backendHealth: status, backendMessage: message }),
                reportApiError: (payload) => set({
                    backendHealth: "error",
                    backendMessage: payload.message,
                    lastApiError: { ...payload, ts: Date.now() },
                }),
                clearApiError: () => set({ lastApiError: null, backendMessage: null }),

                sourceLabel: import.meta.env.VITE_UI_DEMO_MODE === "true" ? "UI DEMO" : "API",
                brokerProvider: import.meta.env.VITE_UI_DEMO_MODE === "true" ? "mock" : "unknown",
                brokerSandbox: false,
                setBackendSource: ({ sourceLabel, brokerProvider, brokerSandbox, isMockMode }) => {
                    set((state) => ({
                        sourceLabel,
                        brokerProvider,
                        brokerSandbox,
                        isMockMode: state.isUiDemoMode ? Boolean(isMockMode) : false,
                    }));
                },

                selectedInstrument: "TQBR:SBER",
                setSelectedInstrument: (symbol) => set({ selectedInstrument: symbol }),

                selectedTimeframe: "1m",
                setSelectedTimeframe: (tf) => set({ selectedTimeframe: tf }),

                candles: {},
                addCandle: (symbol, tf, candle) => set((state) => {
                    const key = `${symbol}-${tf}`;
                    const current = state.candles[key] || [];
                    const index = current.findIndex((c) => c.time === candle.time);

                    if (index !== -1) {
                        const next = [...current];
                        next[index] = candle;
                        return { candles: { ...state.candles, [key]: next } };
                    }

                    const last = current[current.length - 1];
                    if (!last || candle.time > last.time) {
                        return { candles: { ...state.candles, [key]: [...current, candle] } };
                    }

                    const next = [...current, candle];
                    next.sort((a, b) => a.time - b.time);
                    return { candles: { ...state.candles, [key]: next } };
                }),
                replaceCandles: (symbol, tf, next) => set((state) => ({
                    candles: {
                        ...state.candles,
                        [`${symbol}-${tf}`]: [...next].sort((a, b) => a.time - b.time),
                    },
                })),
                mergeCandles: (symbol, tf, next) => set((state) => {
                    const key = `${symbol}-${tf}`;
                    const merged = new Map<number, any>();
                    for (const candle of state.candles[key] || []) {
                        if (candle && Number.isFinite(Number(candle.time))) {
                            merged.set(Number(candle.time), candle);
                        }
                    }
                    for (const candle of next || []) {
                        if (candle && Number.isFinite(Number(candle.time))) {
                            merged.set(Number(candle.time), candle);
                        }
                    }
                    return {
                        candles: {
                            ...state.candles,
                            [key]: Array.from(merged.values()).sort((a, b) => a.time - b.time),
                        },
                    };
                }),
                clearCandles: () => set({ candles: {} }),
            }),
            {
                name: "app-storage-v4",
                version: 4,
                migrate: (persistedState: any) => ({
                    ...(persistedState || {}),
                    isMockMode: false,
                    candles: {},
                }),
                partialize: (state) => ({
                    authToken: state.authToken,
                    theme: state.theme,
                    sourceLabel: state.sourceLabel,
                    brokerProvider: state.brokerProvider,
                    brokerSandbox: state.brokerSandbox,
                    selectedInstrument: state.selectedInstrument,
                    selectedTimeframe: state.selectedTimeframe,
                }),
            },
        ),
    ),
);
