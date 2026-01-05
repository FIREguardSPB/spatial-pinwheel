import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

interface AppState {
    // Auth
    authToken: string | null;
    setAuthToken: (token: string | null) => void;

    // Settings
    isUiDemoMode: boolean;
    isMockMode: boolean; // Server-side mock
    setMockMode: (isMock: boolean) => void;

    // Connection
    connectionStatus: 'connected' | 'disconnected' | 'reconnecting';
    setConnectionStatus: (status: 'connected' | 'disconnected' | 'reconnecting') => void;

    // Dashboard State
    selectedInstrument: string;
    setSelectedInstrument: (symbol: string) => void;

    selectedTimeframe: string;
    setSelectedTimeframe: (tf: string) => void;

    // Data Persistence (Client-side cache)
    candles: Record<string, any[]>; // storing raw objects
    addCandle: (symbol: string, tf: string, candle: any) => void;
}

export const useAppStore = create<AppState>()(
    devtools(
        persist(
            (set) => ({
                authToken: import.meta.env.VITE_API_TOKEN || null, // default from env
                setAuthToken: (token) => set({ authToken: token }),

                // Client-Side Demo Mode (Strict)
                isUiDemoMode: import.meta.env.VITE_UI_DEMO_MODE === 'true',
                // Backend Mock Mode (Legacy/Server-side) - mostly informational now if UI Demo is off
                isMockMode: import.meta.env.VITE_USE_MOCK === 'true',

                setMockMode: (isMock) => set({ isMockMode: isMock }), // Keep for now, but UI Demo is static env usually

                connectionStatus: 'disconnected',
                setConnectionStatus: (status) => set({ connectionStatus: status }),

                selectedInstrument: 'TQBR:SBER', // default
                setSelectedInstrument: (symbol) => set({ selectedInstrument: symbol }),

                selectedTimeframe: '1m', // default
                setSelectedTimeframe: (tf) => set({ selectedTimeframe: tf }),

                candles: {},
                addCandle: (symbol, tf, candle) => set((state) => {
                    const key = `${symbol}-${tf}`;
                    const current = state.candles[key] || [];

                    // 1. Check if exists
                    const index = current.findIndex(c => c.time === candle.time);
                    if (index !== -1) {
                        // Update existing
                        const next = [...current];
                        next[index] = candle;
                        return { candles: { ...state.candles, [key]: next } };
                    }

                    // 2. Append and Sort
                    // Optimization: check if new is newer than last (most common case)
                    const last = current[current.length - 1];
                    if (!last || candle.time > last.time) {
                        return { candles: { ...state.candles, [key]: [...current, candle] } };
                    }

                    // Middle insertion / Unsorted arrival
                    const next = [...current, candle];
                    next.sort((a, b) => a.time - b.time);
                    return { candles: { ...state.candles, [key]: next } };
                }),
            }),
            {
                name: 'app-storage-v2',
                partialize: (state) => ({
                    authToken: state.authToken,
                    isMockMode: state.isMockMode,
                    selectedInstrument: state.selectedInstrument,
                    selectedTimeframe: state.selectedTimeframe,
                    candles: state.candles, // Persist candles
                }),
            }
        )
    )
);
