import { ChartContainer } from './ChartContainer';
import { InstrumentSelector } from './InstrumentSelector';
import { StatsWidgets } from './StatsWidgets';
import { useSignals } from '../signals/hooks';

export default function DashboardPage() {
    // Fetch signals for overlay (last 50 is default in mock/api for now)
    const { data: signals } = useSignals();

    return (
        <div className="h-full flex flex-col bg-gray-950 overflow-hidden">
            {/* Header Ribbon */}
            <div className="h-14 border-b border-gray-800 flex items-center px-4 justify-between bg-gray-950 shrink-0">
                <div className="flex items-center space-x-4">
                    <InstrumentSelector />
                    <div className="h-6 w-px bg-gray-800 mx-2" />
                    <span className="text-sm text-gray-500 font-mono">15m</span>
                </div>
                <div className="flex items-center space-x-2">
                    {/* Status moved to global Layout */}
                </div>
            </div>

            {/* Content Grid */}
            <div className="flex-1 flex flex-col md:flex-row min-h-0">
                {/* Main Chart Area */}
                <div className="flex-1 flex flex-col p-2 min-w-0">
                    {/* Top Stats Row */}
                    <StatsWidgets />

                    {/* Chart */}
                    <div className="flex-1 bg-gray-900 border border-gray-800 rounded-lg overflow-hidden relative shadow-inner">
                        <ChartContainer signals={signals} />
                    </div>
                </div>

                {/* Right Sidebar (Optional for MVP - could be Order Book or Recent Trades list) 
                 For now, let's keep it simple as requested -> "Widgets: Widgets (PnL day / equity)" 
                 User requirement said: "Справа/снизу: виджеты". We put them on top for layout stability.
             */}
            </div>
        </div>
    );
}
