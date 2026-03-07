import React, { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import { useAppStore } from '../../store';
import { Search, Plus, X, ChevronDown, Star } from 'lucide-react';
import clsx from 'clsx';
import { toast } from 'sonner';

interface WatchlistItem { instrument_id: string; ticker: string; name: string; exchange: string; }
interface SearchResult  { instrument_id: string; ticker: string; name: string; exchange: string; type: string; }

const FALLBACK: WatchlistItem[] = [
  { instrument_id: 'TQBR:SBER', ticker: 'SBER', name: 'Сбербанк', exchange: 'TQBR' },
  { instrument_id: 'TQBR:GAZP', ticker: 'GAZP', name: 'Газпром',  exchange: 'TQBR' },
  { instrument_id: 'TQBR:LKOH', ticker: 'LKOH', name: 'Лукойл',  exchange: 'TQBR' },
];

const TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d'];

export const InstrumentSelector: React.FC = () => {
  const { selectedInstrument, setSelectedInstrument, selectedTimeframe, setSelectedTimeframe } = useAppStore();
  const [open, setOpen]   = useState(false);
  const [query, setQuery] = useState('');
  const ref               = useRef<HTMLDivElement>(null);
  const qc                = useQueryClient();

  const { data: watchlist = FALLBACK } = useQuery({
    queryKey: ['watchlist'],
    queryFn: async () => { const { data } = await apiClient.get('/watchlist'); return (data.items ?? FALLBACK) as WatchlistItem[]; },
    staleTime: 60_000, placeholderData: FALLBACK,
  });

  const { data: searchResults = [] } = useQuery({
    queryKey: ['inst-search', query],
    queryFn: async () => { const { data } = await apiClient.get(`/instruments/search?q=${encodeURIComponent(query)}`); return (data.items ?? []) as SearchResult[]; },
    enabled: query.length >= 1, staleTime: 30_000,
  });

  const addMut = useMutation({
    mutationFn: (i: SearchResult) => apiClient.post('/watchlist', { instrument_id: i.instrument_id, ticker: i.ticker, name: i.name, exchange: i.exchange }),
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

  const selected    = watchlist.find(w => w.instrument_id === selectedInstrument);
  const isSearching = query.length >= 1;
  const items       = isSearching ? searchResults : watchlist;

  return (
    <div className="flex items-center gap-3 relative z-50" ref={ref}>
      {/* Instrument button */}
      <div className="relative">
        <button
          onClick={() => setOpen(o => !o)}
          className="flex items-center gap-2 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 hover:border-gray-500 transition-colors min-w-[130px]"
        >
          <Star className="w-3.5 h-3.5 text-yellow-500/70 shrink-0" />
          <span className="font-bold text-gray-200 text-sm">{selected?.ticker ?? selectedInstrument}</span>
          <ChevronDown className={clsx('w-3.5 h-3.5 text-gray-500 ml-auto transition-transform', open && 'rotate-180')} />
        </button>

        {open && (
          <div className="absolute top-full left-0 mt-1 w-72 bg-gray-900 border border-gray-700 rounded-xl shadow-2xl overflow-hidden">
            {/* Search */}
            <div className="p-2 border-b border-gray-800">
              <div className="flex items-center gap-2 bg-gray-800 rounded-lg px-3 py-2">
                <Search className="w-3.5 h-3.5 text-gray-500 shrink-0" />
                <input autoFocus value={query} onChange={e => setQuery(e.target.value)}
                  placeholder="Тикер или название..." className="bg-transparent text-sm text-gray-200 placeholder-gray-600 outline-none flex-1" />
                {query && <button onClick={() => setQuery('')}><X className="w-3.5 h-3.5 text-gray-500" /></button>}
              </div>
            </div>
            <div className="px-3 py-1.5 text-[10px] text-gray-600 uppercase tracking-wider border-b border-gray-800">
              {isSearching ? `Найдено: ${searchResults.length}` : `Мой список · ${watchlist.length}`}
            </div>
            <div className="max-h-64 overflow-y-auto">
              {items.length === 0 && <div className="py-6 text-center text-gray-600 text-sm">Ничего не найдено</div>}
              {isSearching
                ? (items as SearchResult[]).map(item => {
                    const inList = watchlist.some(w => w.instrument_id === item.instrument_id);
                    return (
                      <div key={item.instrument_id} onClick={() => { setSelectedInstrument(item.instrument_id); setOpen(false); setQuery(''); }}
                        className="flex items-center px-3 py-2.5 hover:bg-gray-800 cursor-pointer transition-colors">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-gray-200 text-sm">{item.ticker}</span>
                            <span className="text-[10px] text-gray-600 bg-gray-800 px-1.5 rounded">{item.exchange}</span>
                          </div>
                          <div className="text-xs text-gray-500 truncate">{item.name}</div>
                        </div>
                        {!inList
                          ? <button onClick={e => { e.stopPropagation(); addMut.mutate(item); }} className="ml-2 p-1.5 rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/40"><Plus className="w-3.5 h-3.5" /></button>
                          : <Star className="w-3.5 h-3.5 text-yellow-500 ml-2 shrink-0" />}
                      </div>
                    );
                  })
                : (items as WatchlistItem[]).map(item => (
                    <div key={item.instrument_id} onClick={() => { setSelectedInstrument(item.instrument_id); setOpen(false); }}
                      className={clsx('flex items-center px-3 py-2.5 hover:bg-gray-800 cursor-pointer transition-colors', item.instrument_id === selectedInstrument && 'bg-blue-600/10')}>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={clsx('font-bold text-sm', item.instrument_id === selectedInstrument ? 'text-blue-400' : 'text-gray-200')}>{item.ticker}</span>
                          <span className="text-[10px] text-gray-600 bg-gray-800 px-1.5 rounded">{item.exchange}</span>
                        </div>
                        <div className="text-xs text-gray-500 truncate">{item.name}</div>
                      </div>
                      {watchlist.length > 1 && item.instrument_id !== selectedInstrument && (
                        <button onClick={e => { e.stopPropagation(); delMut.mutate(item.instrument_id); }} className="ml-2 p-1 text-gray-700 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors"><X className="w-3.5 h-3.5" /></button>
                      )}
                    </div>
                  ))
              }
            </div>
          </div>
        )}
      </div>

      {/* Timeframes */}
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
