import React, { useState } from 'react';
import { BookOpen, HelpCircle, X } from 'lucide-react';
import clsx from 'clsx';
import { HELP_CONTENT, type HelpEntry } from '../../constants/helpContent';

interface HelpModalProps {
  entry: HelpEntry;
  onClose: () => void;
}

export const HelpModal: React.FC<HelpModalProps> = ({ entry, onClose }) => {
  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl max-w-lg w-full p-6 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-2 min-w-0">
            <BookOpen className="w-5 h-5 text-blue-400 shrink-0" />
            <div>
              <h2 className="text-lg font-bold text-gray-100">{entry.title}</h2>
              <p className="text-xs text-gray-500 mt-1">{entry.tooltip}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-gray-500 hover:text-gray-200 hover:bg-gray-800 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="rounded-xl border border-blue-500/20 bg-blue-500/10 p-4">
          <div className="text-xs uppercase tracking-wider text-blue-300/80 font-semibold mb-2">Понятно для новичка</div>
          <p className="text-sm text-gray-200 leading-relaxed">{entry.simple}</p>
        </div>

        <div>
          <div className="text-xs uppercase tracking-wider text-gray-500 font-semibold mb-2">Пример</div>
          <p className="text-sm text-gray-300 leading-relaxed">{entry.example}</p>
        </div>

        {entry.advice && (
          <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/10 p-4">
            <div className="text-xs uppercase tracking-wider text-yellow-300/80 font-semibold mb-2">Практический совет</div>
            <p className="text-sm text-yellow-100/90 leading-relaxed">{entry.advice}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export const InfoTooltip: React.FC<{ id: string; className?: string }> = ({ id, className }) => {
  const [open, setOpen] = useState(false);
  const entry = HELP_CONTENT[id];
  if (!entry) return null;

  return (
    <>
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen(true);
        }}
        className={clsx('group relative inline-flex items-center justify-center text-gray-500 hover:text-blue-400 transition-colors', className)}
        aria-label={`Подсказка: ${entry.title}`}
      >
        <HelpCircle className="w-4 h-4" />
        <span className="pointer-events-none absolute left-1/2 top-full z-40 mt-2 hidden w-56 -translate-x-1/2 rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-left text-[11px] normal-case leading-relaxed text-gray-200 shadow-xl group-hover:block">
          {entry.tooltip}
          <span className="mt-1 block text-[10px] text-blue-300">Кликните для подробного объяснения</span>
        </span>
      </button>
      {open && <HelpModal entry={entry} onClose={() => setOpen(false)} />}
    </>
  );
};

export const HelpLabel: React.FC<{ label: string; helpId?: string; className?: string }> = ({ label, helpId, className }) => (
  <span className={clsx('inline-flex items-center gap-1.5', className)}>
    <span>{label}</span>
    {helpId ? <InfoTooltip id={helpId} /> : null}
  </span>
);

export const GlossaryModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const [selected, setSelected] = useState<string>(Object.keys(HELP_CONTENT)[0]);
  const entries = Object.entries(HELP_CONTENT);

  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const entry = HELP_CONTENT[selected];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-5xl max-h-[85vh] flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-bold text-gray-100">Глоссарий и подсказки</h2>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-gray-500 hover:text-gray-200 hover:bg-gray-800 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex flex-1 min-h-0">
          <div className="w-56 border-r border-gray-800 overflow-y-auto shrink-0 bg-gray-950/50">
            {entries.map(([key, item]) => (
              <button
                key={key}
                onClick={() => setSelected(key)}
                className={clsx(
                  'w-full text-left px-4 py-3 border-b border-gray-900 transition-colors',
                  selected === key ? 'bg-blue-600/15 text-blue-300' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200',
                )}
              >
                <div className="text-sm font-medium">{item.title}</div>
                <div className="text-[11px] mt-1 text-gray-500">{item.tooltip}</div>
              </button>
            ))}
          </div>
          <div className="flex-1 overflow-y-auto p-6">
            <div className="space-y-4">
              <h3 className="text-xl font-bold text-gray-100">{entry.title}</h3>
              <p className="text-xs text-gray-500">{entry.tooltip}</p>
              <div className="rounded-xl border border-blue-500/20 bg-blue-500/10 p-4">
                <p className="text-sm text-gray-200 leading-relaxed">{entry.simple}</p>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-gray-500 font-semibold mb-2">Пример</div>
                <p className="text-sm text-gray-300 leading-relaxed">{entry.example}</p>
              </div>
              {entry.advice && (
                <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/10 p-4">
                  <div className="text-xs uppercase tracking-wider text-yellow-300/80 font-semibold mb-2">Практический совет</div>
                  <p className="text-sm text-yellow-100/90 leading-relaxed">{entry.advice}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
