import React from 'react';
import { useAppStore } from '../../store';
import { useSignals } from '../signals/hooks';
import { Wifi, WifiOff, AlertTriangle } from 'lucide-react';

export const ConnectionStatus: React.FC = () => {
    const { isMockMode } = useAppStore();
    const { isError } = useSignals(); // Use signals query as a proxy for API health

    if (isMockMode) {
        return (
            <div className="flex items-center px-3 py-1 bg-orange-500/10 text-orange-500 text-xs rounded border border-orange-500/20 animate-pulse">
                <AlertTriangle className="w-3 h-3 mr-2" />
                <span className="font-bold">MOCK MODE ACTIVE - DATA IS FAKE</span>
            </div>
        );
    }

    if (isError) {
        return (
            <div className="flex items-center px-3 py-1 bg-red-500/10 text-red-500 text-xs rounded border border-red-500/20">
                <WifiOff className="w-3 h-3 mr-2" />
                <span className="font-bold">API DISCONNECTED</span>
            </div>
        );
    }

    return (
        <div className="flex items-center px-3 py-1 bg-green-500/10 text-green-500 text-xs rounded border border-green-500/20">
            <Wifi className="w-3 h-3 mr-2" />
            <span>SYSTEM ONLINE</span>
        </div>
    );
};
