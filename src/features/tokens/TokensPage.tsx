/**
 * P8-01: Страница управления API-токенами.
 *
 * Позволяет добавлять, редактировать, удалять токены без правки конфигурационных файлов.
 * Значения хранятся в БД и показываются в замаскированном виде.
 */
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import { toast } from 'sonner';
import {
  Key, Plus, Pencil, Trash2, Eye, EyeOff, CheckCircle2,
  XCircle, Loader2, TestTube2, Shield, Bot, MessageCircle, TrendingUp
} from 'lucide-react';
import { ConfirmModal, Skeleton } from '../../components/ui/UIComponents';

// ── Types ──────────────────────────────────────────────────────────────────────
interface ApiToken {
  id:           string;
  key_name:     string;
  masked_value: string;
  label:        string;
  description:  string;
  category:     string;
  is_active:    boolean;
  has_value:    boolean;
  created_ts:   number;
  updated_ts:   number;
  last_used_ts: number | null;
}

const CATEGORY_META: Record<string, { label: string; icon: React.ElementType; color: string }> = {
  auth:     { label: 'Авторизация', icon: Shield,        color: 'text-violet-400' },
  ai:       { label: 'AI / LLM',    icon: Bot,           color: 'text-blue-400'   },
  telegram: { label: 'Telegram',    icon: MessageCircle, color: 'text-sky-400'    },
  broker:   { label: 'Брокер',      icon: TrendingUp,    color: 'text-emerald-400'},
  general:  { label: 'Прочее',      icon: Key,           color: 'text-gray-400'   },
};

// ── API helpers ───────────────────────────────────────────────────────────────
const tokensApi = {
  list:   ()                       => apiClient.get<ApiToken[]>('/tokens').then(r => r.data),
  upsert: (body: Record<string,string>) => apiClient.post('/tokens', body).then(r => r.data),
  update: (id: string, body: Record<string,unknown>) => apiClient.put(`/tokens/${id}`, body).then(r => r.data),
  delete: (id: string)             => apiClient.delete(`/tokens/${id}`).then(r => r.data),
  reveal: (id: string)             => apiClient.get(`/tokens/reveal/${id}?confirm=true`).then(r => r.data),
  test:   (id: string)             => apiClient.post(`/tokens/test/${id}`).then(r => r.data),
};

// ── Token row ─────────────────────────────────────────────────────────────────
function TokenRow({ tok, onEdit, onDelete }: { tok: ApiToken; onEdit: (t: ApiToken) => void; onDelete: (t: ApiToken) => void }) {
  const [revealed, setRevealed] = useState<string | null>(null);
  const [revealing, setRevealing] = useState(false);
  const [testing,   setTesting]   = useState(false);
  const [testResult, setTestResult] = useState<{ok: boolean; message: string} | null>(null);
  const meta = CATEGORY_META[tok.category] || CATEGORY_META.general;
  const Icon = meta.icon;

  const handleReveal = async () => {
    if (revealed) { setRevealed(null); return; }
    setRevealing(true);
    try {
      const data = await tokensApi.reveal(tok.id);
      setRevealed(data.value || '(пусто)');
    } catch { toast.error('Не удалось получить значение'); }
    finally  { setRevealing(false); }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await tokensApi.test(tok.id);
      setTestResult(res);
      toast[res.ok ? 'success' : 'error'](res.message);
    } catch { toast.error('Ошибка теста'); }
    finally  { setTesting(false); }
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`p-2 rounded-lg bg-gray-800 ${meta.color} shrink-0`}>
            <Icon className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="font-semibold text-sm text-gray-100 truncate">{tok.label}</div>
            <div className="text-xs text-gray-500 font-mono truncate">{tok.key_name}</div>
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {tok.has_value
            ? <span className="text-xs text-emerald-400 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> Задан
              </span>
            : <span className="text-xs text-gray-500 flex items-center gap-1">
                <XCircle className="w-3 h-3" /> Не задан
              </span>
          }
        </div>
      </div>

      {/* Description */}
      {tok.description && (
        <p className="text-xs text-gray-500 leading-relaxed">{tok.description}</p>
      )}

      {/* Value display */}
      <div className="flex items-center gap-2 bg-gray-950 rounded-lg px-3 py-2 font-mono text-xs">
        <span className="flex-1 text-gray-400 truncate">
          {revealed ?? (tok.has_value ? tok.masked_value : '— не задан —')}
        </span>
        {tok.has_value && (
          <button onClick={handleReveal} disabled={revealing}
            className="text-gray-500 hover:text-gray-300 shrink-0">
            {revealing ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
              : revealed ? <EyeOff className="w-3.5 h-3.5" />
              : <Eye className="w-3.5 h-3.5" />}
          </button>
        )}
      </div>

      {/* Test result */}
      {testResult && (
        <div className={`text-xs px-3 py-2 rounded-lg ${testResult.ok ? 'bg-emerald-950 text-emerald-300' : 'bg-red-950 text-red-300'}`}>
          {testResult.ok ? '✓ ' : '✗ '}{testResult.message}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <button onClick={() => onEdit(tok)}
          className="flex-1 flex items-center justify-center gap-1.5 text-xs px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors">
          <Pencil className="w-3.5 h-3.5" />
          {tok.has_value ? 'Изменить' : 'Задать'}
        </button>
        <button onClick={handleTest} disabled={!tok.has_value || testing}
          className="flex items-center justify-center gap-1.5 text-xs px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 transition-colors disabled:opacity-40">
          {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <TestTube2 className="w-3.5 h-3.5" />}
          Тест
        </button>
        <button onClick={() => onDelete(tok)}
          className="flex items-center justify-center gap-1.5 text-xs px-3 py-2 rounded-lg bg-gray-800 hover:bg-red-900 text-gray-400 hover:text-red-300 transition-colors">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

// ── Edit modal ────────────────────────────────────────────────────────────────
function EditModal({
  tok, onClose, onSave,
}: {
  tok: ApiToken | null;   // null = new custom token
  onClose: () => void;
  onSave: (keyName: string, value: string, label: string, category: string) => void;
}) {
  const [keyName,  setKeyName]  = useState(tok?.key_name  || '');
  const [value,    setValue]    = useState('');
  const [label,    setLabel]    = useState(tok?.label     || '');
  const [category, setCategory] = useState(tok?.category  || 'general');
  const [showVal,  setShowVal]  = useState(false);

  const isNew = !tok;
  const isKnown = !!tok;

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-md space-y-4">
        <h2 className="text-lg font-bold text-gray-100">
          {isNew ? 'Добавить токен' : `Изменить: ${tok.label}`}
        </h2>

        {isNew && (
          <>
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Ключ (KEY_NAME) *</label>
              <input value={keyName} onChange={e => setKeyName(e.target.value.toUpperCase())}
                placeholder="MY_API_KEY"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 font-mono focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Название</label>
              <input value={label} onChange={e => setLabel(e.target.value)}
                placeholder="Мой API ключ"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Категория</label>
              <select value={category} onChange={e => setCategory(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500">
                {Object.entries(CATEGORY_META).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            </div>
          </>
        )}

        <div>
          <label className="text-xs text-gray-400 mb-1 block">
            {isKnown ? 'Новое значение (оставьте пустым, чтобы не менять)' : 'Значение *'}
          </label>
          <div className="relative">
            <input
              type={showVal ? 'text' : 'password'}
              value={value}
              onChange={e => setValue(e.target.value)}
              placeholder={isKnown ? '••••••••' : 'Введите значение'}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 pr-10 text-sm text-gray-100 font-mono focus:outline-none focus:border-blue-500"
            />
            <button onClick={() => setShowVal(v => !v)}
              className="absolute right-2.5 top-2 text-gray-500 hover:text-gray-300">
              {showVal ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <div className="flex gap-3 pt-2">
          <button onClick={onClose}
            className="flex-1 px-4 py-2.5 rounded-xl bg-gray-800 text-gray-300 text-sm hover:bg-gray-700 transition-colors">
            Отмена
          </button>
          <button
            onClick={() => {
              if (isNew && !keyName.trim()) { toast.error('Укажите KEY_NAME'); return; }
              if (!isKnown && !value.trim()) { toast.error('Значение не может быть пустым'); return; }
              onSave(isNew ? keyName : tok.key_name, value, label || keyName, category);
            }}
            className="flex-1 px-4 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-500 transition-colors">
            Сохранить
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function TokensPage() {
  const qc = useQueryClient();
  const [editTok,    setEditTok]    = useState<ApiToken | null | undefined>(undefined); // undefined=closed, null=new
  const [deleteTok,  setDeleteTok]  = useState<ApiToken | null>(null);
  const [activeCategory, setActiveCategory] = useState<string>('all');

  const { data: tokens = [], isLoading, isError } = useQuery({
    queryKey: ['tokens'],
    queryFn: tokensApi.list,
    refetchInterval: 30_000,
  });

  const saveMutation = useMutation({
    mutationFn: (body: Record<string, string>) => tokensApi.upsert(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tokens'] });
      setEditTok(undefined);
      toast.success('Токен сохранён');
    },
    onError: () => toast.error('Не удалось сохранить токен'),
  });

  const deleteMutation = useMutation({
    mutationFn: (tok: ApiToken) => tokensApi.delete(tok.id),
    onSuccess: (_, tok) => {
      qc.invalidateQueries({ queryKey: ['tokens'] });
      setDeleteTok(null);
      toast.success(tok.key_name in {'AUTH_TOKEN':1,'CLAUDE_API_KEY':1,'TELEGRAM_BOT_TOKEN':1}
        ? 'Значение токена очищено' : 'Токен удалён');
    },
    onError: () => toast.error('Не удалось удалить токен'),
  });

  const categories = ['all', ...Array.from(new Set(tokens.map(t => t.category)))];

  const filtered = activeCategory === 'all'
    ? tokens
    : tokens.filter(t => t.category === activeCategory);

  const grouped: Record<string, ApiToken[]> = {};
  filtered.forEach(t => {
    const c = t.category;
    if (!grouped[c]) grouped[c] = [];
    grouped[c].push(t);
  });

  return (
    <div className="max-w-4xl mx-auto p-4 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
            <Key className="w-6 h-6 text-yellow-400" />
            Управление токенами
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Все API-ключи и токены хранятся в БД — редактировать конфиги не нужно
          </p>
        </div>
        <button
          onClick={() => setEditTok(null)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-semibold transition-colors">
          <Plus className="w-4 h-4" /> Добавить
        </button>
      </div>

      {/* Category filter */}
      <div className="flex gap-2 flex-wrap">
        {categories.map(cat => {
          const meta = cat === 'all' ? null : CATEGORY_META[cat];
          return (
            <button key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                activeCategory === cat
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:text-gray-200 hover:bg-gray-700'
              }`}>
              {cat === 'all' ? `Все (${tokens.length})` : `${meta?.label || cat} (${tokens.filter(t=>t.category===cat).length})`}
            </button>
          );
        })}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="grid sm:grid-cols-2 gap-4">
          {[1,2,3,4,5,6].map(i => <Skeleton key={i} className="h-44 rounded-xl" />)}
        </div>
      ) : isError ? (
        <div className="text-center py-16 text-red-400">
          <XCircle className="w-10 h-10 mx-auto mb-3 opacity-50" />
          <p>Не удалось загрузить токены</p>
        </div>
      ) : (
        Object.entries(grouped).map(([cat, toks]) => {
          const meta = CATEGORY_META[cat] || CATEGORY_META.general;
          const CatIcon = meta.icon;
          return (
            <div key={cat} className="space-y-3">
              {activeCategory === 'all' && (
                <h2 className={`text-sm font-semibold flex items-center gap-2 ${meta.color}`}>
                  <CatIcon className="w-4 h-4" />
                  {meta.label}
                </h2>
              )}
              <div className="grid sm:grid-cols-2 gap-3">
                {toks.map(tok => (
                  <TokenRow
                    key={tok.id}
                    tok={tok}
                    onEdit={t => setEditTok(t)}
                    onDelete={t => setDeleteTok(t)}
                  />
                ))}
              </div>
            </div>
          );
        })
      )}

      {/* Summary bar */}
      {!isLoading && tokens.length > 0 && (
        <div className="flex gap-4 pt-2 border-t border-gray-800 text-xs text-gray-500">
          <span className="text-emerald-400 font-medium">
            {tokens.filter(t => t.has_value).length} задано
          </span>
          <span>
            {tokens.filter(t => !t.has_value).length} не задано
          </span>
          <span className="ml-auto">
            Всего: {tokens.length}
          </span>
        </div>
      )}

      {/* Edit modal */}
      {editTok !== undefined && (
        <EditModal
          tok={editTok}
          onClose={() => setEditTok(undefined)}
          onSave={(keyName, value, label, category) => {
            if (!value && editTok) return setEditTok(undefined); // no-op if empty for existing
            saveMutation.mutate({ key_name: keyName, value, label, category });
          }}
        />
      )}

      {/* Delete confirm */}
      {deleteTok && (
        <ConfirmModal
          title={`Удалить токен "${deleteTok.label}"?`}
          description={
            deleteTok.key_name in { AUTH_TOKEN: 1, CLAUDE_API_KEY: 1, TELEGRAM_BOT_TOKEN: 1 }
              ? 'Системный токен нельзя полностью удалить — значение будет очищено.'
              : `Токен ${deleteTok.key_name} будет удалён безвозвратно.`
          }
          confirmLabel="Удалить"
          onConfirm={() => deleteMutation.mutate(deleteTok)}
          onCancel={() => setDeleteTok(null)}
        />
      )}
    </div>
  );
}
