import React from 'react';
import { useAppStore } from '../../store';
import { Wifi, WifiOff, AlertTriangle } from 'lucide-react';
import { useWorkerStatus } from '../system/useWorkerStatus';

export const ConnectionStatus: React.FC = () => {
    const { isUiDemoMode, connectionStatus, backendHealth } = useAppStore();
    const { data: workerStatus } = useWorkerStatus();

    if (isUiDemoMode) {
        return (
            <div className="flex items-center px-3 py-1 bg-orange-500/10 text-orange-500 text-xs rounded border border-orange-500/20 animate-pulse">
                <AlertTriangle className="w-3 h-3 mr-2" />
                <span className="font-bold">MOCK MODE ACTIVE - DATA IS FAKE</span>
            </div>
        );
    }

    if (connectionStatus === 'reconnecting') {
        return (
            <div className="flex items-center px-3 py-1 bg-yellow-500/10 text-yellow-400 text-xs rounded border border-yellow-500/20">
                <AlertTriangle className="w-3 h-3 mr-2" />
                <span className="font-bold">STREAM RECONNECTING</span>
            </div>
        );
    }

    if (workerStatus && ['offline', 'stopped', 'error'].includes(workerStatus.phase)) {
        return (
            <div className="flex items-center px-3 py-1 bg-red-500/10 text-red-400 text-xs rounded border border-red-500/20">
                <AlertTriangle className="w-3 h-3 mr-2" />
                <span className="font-bold">WORKER {String(workerStatus.phase).toUpperCase()}</span>
            </div>
        );
    }

    if (workerStatus && workerStatus.phase === 'analysis') {
        return (
            <div className="flex items-center px-3 py-1 bg-blue-500/10 text-blue-300 text-xs rounded border border-blue-500/20">
                <Wifi className="w-3 h-3 mr-2" />
                <span className="font-bold">WORKER ANALYZING</span>
            </div>
        );
    }

    if (backendHealth === 'degraded') {
        return (
            <div className="flex items-center px-3 py-1 bg-yellow-500/10 text-yellow-300 text-xs rounded border border-yellow-500/20">
                <AlertTriangle className="w-3 h-3 mr-2" />
                <span className="font-bold">BACKEND DEGRADED</span>
            </div>
        );
    }

    if (backendHealth === 'error') {
        return (
            <div className="flex items-center px-3 py-1 bg-red-500/10 text-red-500 text-xs rounded border border-red-500/20">
                <WifiOff className="w-3 h-3 mr-2" />
                <span className="font-bold">API DISCONNECTED</span>
            </div>
        );
    }

    if (connectionStatus === 'disconnected') {
        return (
            <div className="flex items-center px-3 py-1 bg-yellow-500/10 text-yellow-300 text-xs rounded border border-yellow-500/20">
                <AlertTriangle className="w-3 h-3 mr-2" />
                <span className="font-bold">LIVE UPDATES PAUSED</span>
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
