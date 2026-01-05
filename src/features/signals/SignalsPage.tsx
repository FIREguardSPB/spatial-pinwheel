import { SignalsTable } from './SignalsTable';

export default function SignalsPage() {
    return (
        <div className="p-6 h-full flex flex-col bg-gray-950">
            <div className="flex items-center justify-between mb-6">
                <h1 className="text-2xl font-bold text-gray-100">Signals Queue</h1>
                <div className="flex space-x-2">
                    {/* Optional filters can go here */}
                </div>
            </div>

            <div className="flex-1 min-h-0">
                <SignalsTable />
            </div>
        </div>
    );
}
