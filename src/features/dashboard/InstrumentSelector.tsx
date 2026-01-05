import React from 'react';
import { useAppStore } from '../../store';
import { Search } from 'lucide-react';

const MOCK_INSTRUMENTS = ['TQBR:SBER', 'TQBR:VTBR', 'TQBR:GAZP', 'BTCUSDT', 'ETHUSDT'];
const TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d', '1w'];

export const InstrumentSelector: React.FC = () => {
    const { selectedInstrument, setSelectedInstrument, selectedTimeframe, setSelectedTimeframe } = useAppStore();
    const [isOpen, setIsOpen] = React.useState(false);

    return (
        <div className="flex items-center space-x-4 relative z-50">
            {/* Instrument Dropdown */}
            <div className="relative">
                <div
                    className="flex items-center bg-gray-900 border border-gray-700 rounded-md px-3 py-2 cursor-pointer hover:border-gray-500 transition-colors bg-opacity-50 backdrop-blur-sm shadow-sm"
                    onClick={() => setIsOpen(!isOpen)}
                >
                    <Search className="w-4 h-4 text-gray-400 mr-2" />
                    <span className="font-bold text-gray-200">{selectedInstrument}</span>
                </div>

                {isOpen && (
                    <div className="absolute top-full left-0 mt-1 w-48 bg-gray-800 border border-gray-700 rounded-md shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-100">
                        {MOCK_INSTRUMENTS.map((inst) => (
                            <div
                                key={inst}
                                className={`px-4 py-2 text-sm cursor-pointer hover:bg-gray-700 ${inst === selectedInstrument ? 'text-blue-400 font-medium' : 'text-gray-300'}`}
                                onClick={() => {
                                    setSelectedInstrument(inst);
                                    setIsOpen(false);
                                }}
                            >
                                {inst}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Timeframe Selector */}
            <div className="flex items-center bg-gray-900 border border-gray-700 rounded-md p-1 bg-opacity-50 backdrop-blur-sm shadow-sm">
                {TIMEFRAMES.map((tf) => (
                    <button
                        key={tf}
                        className={`px-3 py-1 text-xs font-medium rounded transition-all duration-200 ${selectedTimeframe === tf
                                ? 'bg-gray-700 text-blue-400 shadow-sm'
                                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
                            }`}
                        onClick={() => setSelectedTimeframe(tf)}
                    >
                        {tf}
                    </button>
                ))}
            </div>
        </div>
    );
};
