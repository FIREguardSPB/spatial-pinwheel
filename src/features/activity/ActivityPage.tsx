import { useDecisionLog } from './hooks';
import { format } from 'date-fns';
import { Terminal, ArrowRight, Copy } from 'lucide-react';

export default function ActivityPage() {
    const { data: logs, isLoading } = useDecisionLog();

    return (
        <div className="p-6 h-full flex flex-col bg-gray-950">
            <h1 className="text-2xl font-bold mb-6 text-gray-100 flex items-center">
                <Terminal className="mr-3 text-purple-500" />
                Decision Log
            </h1>

            <div className="flex-1 bg-gray-900 border border-gray-800 rounded-lg overflow-y-auto p-4 font-mono text-sm shadow-inner">
                {isLoading && <div className="text-gray-500">Loading logs...</div>}

                <div className="space-y-4">
                    {logs?.map((log) => (
                        <div key={log.id} className="flex flex-col md:flex-row border-b border-gray-800 pb-3 last:border-0 group">
                            <div className="min-w-[150px] text-gray-500 text-xs md:text-sm mb-1 md:mb-0">
                                {format(log.ts, 'yyyy-MM-dd HH:mm:ss')}
                            </div>
                            <div className="flex-1 relative pr-8">
                                <div className="flex items-center text-blue-400 font-bold mb-1">
                                    <ArrowRight className="w-3 h-3 mr-2" />
                                    {log.type}
                                </div>
                                <div className="text-gray-300 pl-5 font-mono text-xs break-all">
                                    {JSON.stringify(log.message).replace(/^"|"$/g, '')}
                                </div>
                                <button
                                    onClick={() => navigator.clipboard.writeText(JSON.stringify(log))}
                                    className="absolute top-0 right-0 p-1 opacity-0 group-hover:opacity-100 text-gray-500 hover:text-white transition-opacity"
                                    title="Copy JSON"
                                >
                                    <Copy className="w-3 h-3" />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
