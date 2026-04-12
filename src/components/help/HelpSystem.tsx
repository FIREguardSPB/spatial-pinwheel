import React, { useEffect, useId, useRef, useState } from 'react';
import { BookOpen, HelpCircle, X } from 'lucide-react';
import clsx from 'clsx';
import { HELP_CONTENT, type HelpEntry } from '../../constants/helpContent';

function getFocusableElements(container: HTMLElement | null) {
  if (!container) return [] as HTMLElement[];
  return Array.from(
    container.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'),
  ).filter((el) => !el.hasAttribute('disabled'));
}

function useDialogFocus(onClose: () => void) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    restoreFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focusables = getFocusableElements(dialogRef.current);
    window.setTimeout(() => (focusables[0] ?? dialogRef.current)?.focus(), 0);

    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;
      const items = getFocusableElements(dialogRef.current);
      if (items.length === 0) {
        event.preventDefault();
        dialogRef.current?.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener('keydown', handler);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', handler);
      document.body.style.overflow = '';
      restoreFocusRef.current?.focus?.();
    };
  }, [onClose]);

  return dialogRef;
}

interface HelpModalProps {
  entry: HelpEntry;
  onClose: () => void;
}

export const HelpModal: React.FC<HelpModalProps> = ({ entry, onClose }) => {
  const dialogRef = useDialogFocus(onClose);
  const titleId = useId();
  const tooltipId = useId();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={tooltipId} tabIndex={-1} className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl max-w-lg w-full p-6 space-y-4 outline-none">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-2 min-w-0">
            <BookOpen className="w-5 h-5 text-blue-400 shrink-0" />
            <div>
              <h2 id={titleId} className="text-lg font-bold text-gray-100">{entry.title}</h2>
              <p id={tooltipId} className="text-xs text-gray-500 mt-1">{entry.tooltip}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-gray-500 hover:text-gray-200 hover:bg-gray-800 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400" aria-label="Закрыть справку"><X className="w-4 h-4" /></button>
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
  const tooltipId = useId();
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
        className={clsx('group relative inline-flex items-center justify-center text-gray-500 hover:text-blue-400 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400 rounded', className)}
        aria-label={`Подсказка: ${entry.title}`}
        aria-describedby={tooltipId}
        title={entry.tooltip}
      >
        <HelpCircle className="w-4 h-4" />
        <span id={tooltipId} role="tooltip" className="pointer-events-none absolute left-1/2 top-full z-40 mt-2 hidden w-56 -translate-x-1/2 rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-left text-[11px] normal-case leading-relaxed text-gray-200 shadow-xl group-hover:block group-focus-visible:block">
          {entry.tooltip}
          <span className="mt-1 block text-[10px] text-blue-300">Нажмите Enter или кликните для подробного объяснения</span>
        </span>
      </button>
      {open && <HelpModal entry={entry} onClose={() => setOpen(false)} />}
    </>
  );
};

export const HelpLabel: React.FC<{ label: string; helpId?: string; className?: string }> = ({ label, helpId, className }) => {
  const [open, setOpen] = useState(false);
  const tooltipId = useId();
  const entry = helpId ? HELP_CONTENT[helpId] : null;
  if (!helpId || !entry) return <span className={clsx('inline-flex items-center gap-1.5', className)}>{label}</span>;
  return (
    <>
      <span className={clsx('inline-flex items-center gap-1.5', className)}>
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setOpen(true);
          }}
          className="group relative inline-flex items-center gap-1.5 text-left text-inherit hover:text-blue-300 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400 rounded"
          aria-label={`Открыть справку по параметру ${entry.title}`}
          aria-describedby={tooltipId}
          title={entry.tooltip}
        >
          <span className="border-b border-dashed border-gray-600 group-hover:border-blue-400">{label}</span>
          <HelpCircle className="w-4 h-4 text-gray-500 group-hover:text-blue-400 shrink-0" />
          <span id={tooltipId} role="tooltip" className="pointer-events-none absolute left-0 top-full z-40 mt-2 hidden w-56 rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-left text-[11px] normal-case leading-relaxed text-gray-200 shadow-xl group-hover:block group-focus-visible:block">
            {entry.tooltip}
            <span className="mt-1 block text-[10px] text-blue-300">Нажмите Enter или кликните для подробного объяснения</span>
          </span>
        </button>
      </span>
      {open && <HelpModal entry={entry} onClose={() => setOpen(false)} />}
    </>
  );
};

export const GlossaryModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const [selected, setSelected] = useState<string>(Object.keys(HELP_CONTENT)[0]);
  const entries = Object.entries(HELP_CONTENT);
  const dialogRef = useDialogFocus(onClose);
  const titleId = useId();
  const entry = HELP_CONTENT[selected];
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-5xl max-h-[85vh] flex flex-col overflow-hidden outline-none">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <div className="flex items-center gap-2"><BookOpen className="w-5 h-5 text-blue-400" /><h2 id={titleId} className="text-lg font-bold text-gray-100">Глоссарий и подсказки</h2></div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-gray-500 hover:text-gray-200 hover:bg-gray-800 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400" aria-label="Закрыть глоссарий"><X className="w-4 h-4" /></button>
        </div>
        <div className="flex flex-1 min-h-0 flex-col md:flex-row">
          <div className="md:w-64 border-b md:border-b-0 md:border-r border-gray-800 overflow-y-auto shrink-0 bg-gray-950/50">
            <div className="flex md:flex-col gap-2 overflow-x-auto p-3">
              {entries.map(([key, item]) => (
                <button key={key} onClick={() => setSelected(key)} className={clsx('min-w-48 md:min-w-0 md:w-full text-left px-4 py-3 rounded-xl md:rounded-none md:border-b md:border-gray-900 transition-colors', selected === key ? 'bg-blue-600/15 text-blue-300' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200')}>
                  <div className="text-sm font-medium">{item.title}</div>
                  <div className="text-[11px] mt-1 text-gray-500">{item.tooltip}</div>
                </button>
              ))}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-6">
            <div className="space-y-4">
              <h3 className="text-xl font-bold text-gray-100">{entry.title}</h3>
              <p className="text-xs text-gray-500">{entry.tooltip}</p>
              <div className="rounded-xl border border-blue-500/20 bg-blue-500/10 p-4"><p className="text-sm text-gray-200 leading-relaxed">{entry.simple}</p></div>
              <div><div className="text-xs uppercase tracking-wider text-gray-500 font-semibold mb-2">Пример</div><p className="text-sm text-gray-300 leading-relaxed">{entry.example}</p></div>
              {entry.advice && <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/10 p-4"><div className="text-xs uppercase tracking-wider text-yellow-300/80 font-semibold mb-2">Практический совет</div><p className="text-sm text-yellow-100/90 leading-relaxed">{entry.advice}</p></div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
