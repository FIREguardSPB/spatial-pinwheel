import { SignalsTable } from './SignalsTable';
import { SignalCard }   from './SignalCard';
import { useSignals, useSignalAction } from './hooks';
import { useState } from 'react';
import { toast } from 'sonner';

export default function SignalsPage() {
    const { data: signals } = useSignals();
    const { mutate: performAction, isPending } = useSignalAction();
    const [processingId, setProcessingId] = useState<string | null>(null);

    const handleAction = (id: string, action: 'approve' | 'reject') => {
        setProcessingId(id);
        performAction({ id, action }, {
            onSuccess: () => toast.success(action === 'approve' ? '✅ Сигнал одобрен' : '❌ Сигнал отклонён'),
            onError:   () => toast.error('Ошибка выполнения действия'),
            onSettled: () => setProcessingId(null),
        });
    };

    return (
        <div className="p-4 md:p-6 h-full flex flex-col bg-gray-950">
            <div className="flex items-center justify-between mb-4">
                <h1 className="text-xl md:text-2xl font-bold text-gray-100">Сигналы</h1>
            </div>

            {/* Mobile: card list */}
            <div className="md:hidden flex-1 overflow-y-auto space-y-3">
                {signals?.length === 0 && (
                    <div className="text-center text-gray-600 py-12 text-sm">
                        Сигналов нет. Убедитесь, что бот запущен.
                    </div>
                )}
                {signals?.map(signal => (
                    <SignalCard key={signal.id} signal={signal}
                        onAction={handleAction} isPending={isPending} processingId={processingId} />
                ))}
            </div>

            {/* Desktop: table */}
            <div className="hidden md:flex flex-1 min-h-0">
                <SignalsTable />
            </div>
        </div>
    );
}
