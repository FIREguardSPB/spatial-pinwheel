import React, { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import { useAppStore } from '../../store';
import { Search, Plus, X, ChevronDown, Star, BriefcaseBusiness, LibraryBig } from 'lucide-react';
import clsx from 'clsx';
import { toast } from 'sonner';

interface WatchlistItem { instrument_id: string; ticker: string; name: string; exchange: string; }
interface SearchResult  { instrument_id: string; ticker: string; name: string; exchange: string; type: string; }
interface PositionItem { instrument_id: string; side?: string; qty?: number; }

const TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d'];

const dedupeByInstrument = <T extends { instrument_id: string }>(items: T[]) => {
  const map = new Map<string, T>();
  items.forEach((item) => map.set(item.instrument_id, item));
  return Array.from(map.values());
};

const tickerFromInstrumentId = (instrumentId: string) => instrumentId.split(':').pop() ?? instrumentId;

function SectionTitle({ icon: Icon, children }: { icon: React.ComponentType<any>; children: React.ReactNode }) {
  return (
    <div className="px-3 py-1.5 text-[10px] text-gray-500 uppercase tracking-wider border-b border-gray-800 flex items-center gap-1.5">
      <Icon className="w-3 h-3" />
      <span>{children}</span>
    </div>
  );
}

export const InstrumentSelector: React.FC = () => {
  const { selectedInstrument, setSelectedInstrument, selectedTimeframe, setSelectedTimeframe } = useAppStore();
  const [open, setOpen]   = useState(false);
  const [query, setQuery] = useState('');
  const ref               = useRef<HTMLDivElement>(null);
  const qc                = useQueryClient();

  const { data: watchlist = [] } = useQuery({
    queryKey: ['watchlist'],
    queryFn: async () => { const { data } = await apiClient.get('/watchlist'); return (data.items ?? []) as WatchlistItem[]; },
    staleTime: 60_000,
    retry: false,
  });

  const { data: searchResults = [] } = useQuery({
    queryKey: ['inst-search', query],
    queryFn: async () => {
      try {
        const { data } = await apiClient.get(`/instruments/search?q=${encodeURIComponent(query)}&limit=50`);
        return (data.items ?? []) as SearchResult[];
      } catch {
        return [];
      }
    },
    enabled: query.length >= 1,
    staleTime: 30_000,
  });

  const { data: catalogResults = [] } = useQuery({
    queryKey: ['inst-catalog'],
    queryFn: async () => {
      try {
        const { data } = await apiClient.get('/instruments/search?limit=50');
        return (data.items ?? []) as SearchResult[];
      } catch {
        return [];
      }
    },
    enabled: open && query.length === 0,
    staleTime: 5 * 60_000,
  });

  const { data: openPositions = [] } = useQuery({
    queryKey: ['selector-open-positions'],
    queryFn: async () => {
      try {
        const { data } = await apiClient.get('/state/positions');
        return (data.items ?? []) as PositionItem[];
      } catch {
        return [];
      }
    },
    enabled: open,
    staleTime: 15_000,
    refetchInterval: open ? 15_000 : false,
  });

  const { data: selectedRuntime } = useQuery({
    queryKey: ['selector-runtime-overview', selectedInstrument],
    queryFn: async () => {
      try {
        const { data } = await apiClient.get(`/settings/runtime-overview?instrument_id=${encodeURIComponent(selectedInstrument)}`);
        return data as { effective_plan?: Record<string, any> | null; event_regime?: Record<string, any> | null };
      } catch {
        return { effective_plan: null, event_regime: null };
      }
    },
    enabled: open && Boolean(selectedInstrument),
    staleTime: 15_000,
    retry: false,
    placeholderData: (prev) => prev,
  });

  const addMut = useMutation({
    mutationFn: (i: SearchResult | WatchlistItem) => apiClient.post('/watchlist', { instrument_id: i.instrument_id, ticker: i.ticker, name: i.name, exchange: i.exchange }),
    onSuccess: (_,i) => { qc.invalidateQueries({ queryKey: ['watchlist'] }); toast.success(`${i.ticker} добавлен`); },
    onError: () => toast.error('Ошибка добавления'),
  });
  const delMut = useMutation({
    mutationFn: (id: string) => apiClient.delete(`/watchlist/${encodeURIComponent(id)}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watchlist'] }),
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Ошибка удаления'),
  });

  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) { setOpen(false); setQuery(''); } };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  const selected = watchlist.find(w => w.instrument_id === selectedInstrument)
    ?? catalogResults.find(w => w.instrument_id === selectedInstrument)
;
  const selectedTooltip = selectedRuntime?.effective_plan
    ? [
        `${selected?.ticker ?? tickerFromInstrumentId(selectedInstrument)} · ${selectedInstrument}`,
        `Стратегия: ${selectedRuntime.effective_plan.strategy_name ?? '—'}`,
        `Режим: ${selectedRuntime.effective_plan.regime ?? '—'}`,
        `Threshold: ${selectedRuntime.effective_plan.decision_threshold ?? '—'}`,
        `TF: ${selectedRuntime.effective_plan.analysis_timeframe ?? '1m'} → ${selectedRuntime.effective_plan.execution_timeframe ?? selectedRuntime.effective_plan.analysis_timeframe ?? '1m'}`,
        `Hold bars: ${selectedRuntime.effective_plan.hold_bars ?? '—'}`,
        `Re-entry: ${selectedRuntime.effective_plan.reentry_cooldown_sec ?? '—'}s`,
        `Risk x: ${selectedRuntime.effective_plan.risk_multiplier ?? '—'}`,
        selectedRuntime.event_regime ? `Event: ${selectedRuntime.event_regime.regime} / ${selectedRuntime.event_regime.action}` : 'Event: нет',
      ].join('\n')
    : `${selected?.ticker ?? tickerFromInstrumentId(selectedInstrument)} · ${selectedInstrument}\nAdaptive plan ещё не рассчитан`;
  const isSearching = query.length >= 1;
  const catalogItems = dedupeByInstrument(
    catalogResults.filter(item => !watchlist.some(w => w.instrument_id === item.instrument_id)),
  );
  const positionOptions: WatchlistItem[] = dedupeByInstrument(
    openPositions.map((item) => {
      const fromWatchlist = watchlist.find(w => w.instrument_id === item.instrument_id);
      const fromCatalog = catalogResults.find(w => w.instrument_id === item.instrument_id);
      return fromWatchlist ?? fromCatalog ?? {
        instrument_id: item.instrument_id,
        ticker: tickerFromInstrumentId(item.instrument_id),
        name: item.instrument_id,
        exchange: item.instrument_id.split(':')[0] ?? 'MOEX',
      };
    }),
  );

  const renderItem = (item: SearchResult | WatchlistItem, opts?: { selected?: boolean; removable?: boolean; addable?: boolean; badge?: React.ReactNode }) => {
    const removable = opts?.removable ?? false;
    const addable = opts?.addable ?? false;
    const isSelected = opts?.selected ?? item.instrument_id === selectedInstrument;

    return (
      <div
        key={item.instrument_id}
        onClick={() => { setSelectedInstrument(item.instrument_id); setOpen(false); setQuery(''); }}
        className={clsx('flex items-center px-3 py-2.5 hover:bg-gray-800 cursor-pointer transition-colors', isSelected && 'bg-blue-600/10')}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={clsx('font-bold text-sm', isSelected ? 'text-blue-400' : 'text-gray-200')}>{item.ticker}</span>
            <span className="text-[10px] text-gray-600 bg-gray-800 px-1.5 rounded">{item.exchange}</span>
            {opts?.badge}
          </div>
          <div className="text-xs text-gray-500 truncate">{item.name}</div>
        </div>
        {addable ? (
          <button onClick={e => { e.stopPropagation(); addMut.mutate(item); }} className="ml-2 p-1.5 rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/40">
            <Plus className="w-3.5 h-3.5" />
          </button>
        ) : removable ? (
          <button onClick={e => { e.stopPropagation(); delMut.mutate(item.instrument_id); }} className="ml-2 p-1 text-gray-700 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors">
            <X className="w-3.5 h-3.5" />
          </button>
        ) : (
          <Star className="w-3.5 h-3.5 text-yellow-500/70 ml-2 shrink-0" />
        )}
      </div>
    );
  };

  return (
    <div className="flex items-center gap-3 relative z-50" ref={ref}>
      <div className="relative">
        <button
          onClick={() => setOpen(o => !o)}
          title={selectedTooltip}
          className="flex items-center gap-2 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 hover:border-gray-500 transition-colors min-w-[160px]"
        >
          <Star className="w-3.5 h-3.5 text-yellow-500/70 shrink-0" />
          <span className="font-bold text-gray-200 text-sm">{selected?.ticker ?? tickerFromInstrumentId(selectedInstrument)}</span>
          <ChevronDown className={clsx('w-3.5 h-3.5 text-gray-500 ml-auto transition-transform', open && 'rotate-180')} />
        </button>

        {open && (
          <div className="absolute top-full left-0 mt-1 w-80 bg-gray-900 border border-gray-700 rounded-xl shadow-2xl overflow-hidden">
            <div className="p-2 border-b border-gray-800">
              <div className="flex items-center gap-2 bg-gray-800 rounded-lg px-3 py-2">
                <Search className="w-3.5 h-3.5 text-gray-500 shrink-0" />
                <input autoFocus value={query} onChange={e => setQuery(e.target.value)}
                  placeholder="Тикер или название..." className="bg-transparent text-sm text-gray-200 placeholder-gray-600 outline-none flex-1" />
                {query && <button onClick={() => setQuery('')}><X className="w-3.5 h-3.5 text-gray-500" /></button>}
              </div>
            </div>

            <div className="max-h-[28rem] overflow-y-auto">
              {isSearching ? (
                <>
                  <SectionTitle icon={Search}>Найдено: {searchResults.length}</SectionTitle>
                  {searchResults.length === 0 && <div className="py-6 text-center text-gray-600 text-sm">Ничего не найдено</div>}
                  {searchResults.map(item => {
                    const inList = watchlist.some(w => w.instrument_id === item.instrument_id);
                    return renderItem(item, { addable: !inList, badge: inList ? <span className="text-[10px] text-yellow-500">в списке</span> : undefined });
                  })}
                </>
              ) : (
                <>
                  {positionOptions.length > 0 && (
                    <>
                      <SectionTitle icon={BriefcaseBusiness}>Открытые позиции</SectionTitle>
                      {positionOptions.map(item => renderItem(item, { badge: <span className="text-[10px] text-emerald-400">позиция</span> }))}
                    </>
                  )}

                  <SectionTitle icon={Star}>Мой список · {watchlist.length}</SectionTitle>
                  {watchlist.length === 0 && <div className="py-4 text-center text-gray-600 text-sm">Список пуст</div>}
                  {watchlist.map(item => renderItem(item, { removable: watchlist.length > 1 && item.instrument_id !== selectedInstrument }))}

                  <SectionTitle icon={LibraryBig}>Доступные инструменты</SectionTitle>
                  {catalogItems.length === 0 && <div className="py-4 text-center text-gray-600 text-sm">Словарь инструментов пуст</div>}
                  {catalogItems.map(item => renderItem(item, { addable: true }))}
                </>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center bg-gray-900 border border-gray-700 rounded-lg p-1">
        {TIMEFRAMES.map(tf => (
          <button key={tf} onClick={() => setSelectedTimeframe(tf)}
            className={clsx('px-2.5 py-1 text-xs font-medium rounded transition-all',
              selectedTimeframe === tf ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800')}>
            {tf}
          </button>
        ))}
      </div>
    </div>
  );
};
