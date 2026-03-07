import React, { useState } from 'react';
import { HelpCircle, X, BookOpen } from 'lucide-react';
import { HELP_CONTENT, type HelpEntry } from '../../constants/helpContent';
import clsx from 'clsx';

// ─── HelpModal ────────────────────────────────────────────────────────────────
interface HelpModalProps { entry: HelpEntry; onClose: () => void; }

export const HelpModal: React.FC<HelpModalProps> = ({ entry, onClose }) => {
  // Close on backdrop click
  const handleBackdrop = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) onClose();
  };

  // Close on Escape
  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={handleBackdrop}>
      <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-4 animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-blue-400 shrink-0" />
            <h2 className="text-lg font-bold text-gray-100">{entry.title}</h2>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-gray-500 hover:text-gray-200 hover:bg-gray-800 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Simple explanation */}
        <p className="text-sm text-gray-300 leading-relaxed bg-blue-500/10 border border-blue-500/20 rounded-xl p-3">
          {entry.simple}
        </p>

        {/* Example */}
        <div className="space-y-1">
          <div className="text-xs text-gray-500 uppercase tracking-wider font-semibold">Пример</div>
          <p className="text-sm text-gray-300 leading-relaxed">{entry.example}</p>
        </div>

        {/* Advice */}
        {entry.advice && (
          <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-3">
            <div className="text-xs text-yellow-400/80 uppercase tracking-wider font-semibold mb-1">💡 Рекомендация</div>
            <p className="text-sm text-yellow-100/80 leading-relaxed">{entry.advice}</p>
          </div>
        )}
      </div>
    </div>
  );
};

// ─── InfoTooltip ─────────────────────────────────────────────────────────────
interface InfoTooltipProps {
  id: string;       // key in HELP_CONTENT
  className?: string;
}

export const InfoTooltip: React.FC<InfoTooltipProps> = ({ id, className }) => {
  const [open, setOpen] = useState(false);
  const entry = HELP_CONTENT[id];
  if (!entry) return null;

  return (
    <>
      <button
        onClick={e => { e.preventDefault(); e.stopPropagation(); setOpen(true); }}
        title={`Что такое ${entry.title}?`}
        className={clsx(
          'inline-flex items-center justify-center w-4 h-4 rounded-full',
          'text-gray-600 hover:text-blue-400 transition-colors',
          'focus:outline-none focus:ring-1 focus:ring-blue-500 focus:ring-offset-1 focus:ring-offset-gray-900',
          className
        )}
      >
        <HelpCircle className="w-3.5 h-3.5" />
      </button>
      {open && <HelpModal entry={entry} onClose={() => setOpen(false)} />}
    </>
  );
};

// ─── GlossaryModal — все термины сразу ───────────────────────────────────────
export const GlossaryModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const [selected, setSelected] = useState<string | null>(null);
  const entries = Object.entries(HELP_CONTENT);

  React.useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-bold text-gray-100">Глоссарий трейдера</h2>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-gray-500 hover:text-gray-200 hover:bg-gray-800 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex flex-1 min-h-0">
          {/* Terms list */}
          <div className="w-48 border-r border-gray-800 overflow-y-auto shrink-0">
            {entries.map(([key, entry]) => (
              <button key={key}
                onClick={() => setSelected(key)}
                className={clsx('w-full text-left px-4 py-2.5 text-sm transition-colors',
                  selected === key ? 'bg-blue-600/20 text-blue-300' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200')}>
                {entry.title}
              </button>
            ))}
          </div>

          {/* Detail panel */}
          <div className="flex-1 overflow-y-auto p-6">
            {selected ? (() => {
              const entry = HELP_CONTENT[selected];
              return (
                <div className="space-y-4">
                  <h3 className="text-xl font-bold text-gray-100">{entry.title}</h3>
                  <p className="text-sm text-gray-300 leading-relaxed bg-blue-500/10 border border-blue-500/20 rounded-xl p-3">{entry.simple}</p>
                  <div>
                    <div className="text-xs text-gray-500 uppercase tracking-wider font-semibold mb-1">Пример</div>
                    <p className="text-sm text-gray-300 leading-relaxed">{entry.example}</p>
                  </div>
                  {entry.advice && (
                    <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-3">
                      <div className="text-xs text-yellow-400/80 uppercase font-semibold mb-1">💡 Рекомендация</div>
                      <p className="text-sm text-yellow-100/80">{entry.advice}</p>
                    </div>
                  )}
                </div>
              );
            })() : (
              <div className="h-full flex items-center justify-center text-gray-600 text-sm">
                Выберите термин слева
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
