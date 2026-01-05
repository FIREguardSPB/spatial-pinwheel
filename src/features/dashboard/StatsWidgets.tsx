import React from 'react';
import { usePositions, useOrders, useDailyStats } from './hooks';
import clsx from 'clsx';
import { TrendingUp, TrendingDown, Activity, DollarSign } from 'lucide-react';

export const StatsWidgets: React.FC = () => {
    const { data: positions } = usePositions();
    const { data: orders } = useOrders();
    const { data: stats } = useDailyStats();

    return (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            {/* PnL Card */}
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col justify-between">
                <span className="text-gray-500 text-xs uppercase font-bold tracking-wider">Day PnL</span>
                <div className="flex items-center mt-2">
                    <DollarSign className="w-5 h-5 text-gray-400 mr-1" />
                    <span className={clsx("text-2xl font-bold font-mono", (stats?.pnl || 0) >= 0 ? "text-green-500" : "text-red-500")}>
                        {stats?.pnl?.toFixed(2)} ₽
                    </span>
                </div>
            </div>

            {/* Positions Card */}
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col justify-between">
                <span className="text-gray-500 text-xs uppercase font-bold tracking-wider">Open Pos</span>
                <div className="flex items-center mt-2">
                    <Activity className="w-5 h-5 text-blue-500 mr-2" />
                    <span className="text-2xl font-bold font-mono">{positions?.length}</span>
                </div>
            </div>

            {/* Orders Card */}
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col justify-between">
                <span className="text-gray-500 text-xs uppercase font-bold tracking-wider">Active Orders</span>
                <div className="flex items-center mt-2">
                    <span className="text-2xl font-bold font-mono">{orders?.length}</span>
                    <span className="text-xs text-gray-500 ml-2">Pending</span>
                </div>
            </div>

            {/* Risk / Trades Card */}
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col justify-between">
                <span className="text-gray-500 text-xs uppercase font-bold tracking-wider">Trades Today</span>
                <div className="flex items-center mt-2">
                    {(stats?.tradesCount || 0) > 0 ? <TrendingUp className="w-5 h-5 text-green-500 mr-2" /> : <TrendingDown className="w-5 h-5 text-gray-600 mr-2" />}
                    <span className="text-2xl font-bold font-mono">{stats?.tradesCount}</span>
                </div>
            </div>
        </div>
    );
};
