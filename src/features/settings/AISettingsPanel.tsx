import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import { Brain, CheckCircle, XCircle, Loader, Eye, EyeOff } from 'lucide-react';
import clsx from 'clsx';
import { toast } from 'sonner';

interface AIStats { total: number; providers: { provider: string; win_rate: number; avg_conf: number; closed_positions: number }[] }

const AI_MODES = [
  { value: 'off',      label: 'OFF',      desc: 'AI не используется, решает только DE' },
  { value: 'advisory', label: 'Advisory', desc: 'AI вызывается, результат в мета, DE решает' },
  { value: 'override', label: 'Override', desc: 'AI может изменить решение DE при уверенности ≥ threshold' },
  { value: 'required', label: 'Required', desc: 'Без AI сигнал пропускается (SKIP)' },
];

const PROVIDERS = ['claude', 'openai', 'ollama', 'skip'];

export const AISettingsPanel: React.FC<{ settings: any; onUpdate: (patch: any) => void }> = ({ settings, onUpdate }) => {
  const [showKeys, setShowKeys]     = useState<Record<string, boolean>>({});
  const [testResult, setTestResult] = useState<'ok' | 'fail' | null>(null);
  const [testing, setTesting]       = useState(false);

  const { data: aiStats } = useQuery({
    queryKey: ['ai-stats'],
    queryFn: async () => { const { data } = await apiClient.get('/ai/stats'); return data as AIStats; },
    refetchInterval: 60_000,
  });

  const handleTest = async () => {
    setTesting(true); setTestResult(null);
    try {
      await apiClient.get('/ai/stats');
      setTestResult('ok');
    } catch {
      setTestResult('fail');
    }
    setTesting(false);
  };

  const toggleKey = (field: string) => setShowKeys(s => ({ ...s, [field]: !s[field] }));

  return (
    <div className="space-y-6">
      {/* AI Mode */}
      <div>
        <h3 className="font-semibold text-gray-200 mb-3 flex items-center gap-2">
          <Brain className="w-4 h-4 text-blue-400" /> Режим AI
        </h3>
        <div className="grid grid-cols-2 gap-3">
          {AI_MODES.map(m => (
            <label key={m.value} className={clsx(
              'flex flex-col gap-1 p-3 rounded-xl border cursor-pointer transition-all',
              settings?.ai_mode === m.value
                ? 'bg-blue-600/10 border-blue-500/50 text-blue-300'
                : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500')}>
              <div className="flex items-center gap-2">
                <input type="radio" name="ai_mode" value={m.value}
                  checked={settings?.ai_mode === m.value}
                  onChange={() => onUpdate({ ai_mode: m.value })}
                  className="accent-blue-500" />
                <span className="font-bold text-sm">{m.label}</span>
              </div>
              <span className="text-xs opacity-70 pl-5">{m.desc}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Min Confidence */}
      <div>
        <label className="text-sm text-gray-400 block mb-1">
          Минимальная уверенность AI для override: <span className="font-bold text-white">{settings?.ai_min_confidence ?? 70}%</span>
        </label>
        <input type="range" min={50} max={95} step={5}
          value={settings?.ai_min_confidence ?? 70}
          onChange={e => onUpdate({ ai_min_confidence: parseInt(e.target.value) })}
          className="w-full accent-blue-500" />
        <div className="flex justify-between text-xs text-gray-600 mt-1">
          <span>50% (мягко)</span><span>95% (строго)</span>
        </div>
      </div>

      {/* Provider */}
      <div>
        <label className="text-sm text-gray-400 block mb-2">Основной провайдер</label>
        <div className="flex gap-2">
          {PROVIDERS.map(p => (
            <button key={p} onClick={() => onUpdate({ ai_primary_provider: p })}
              className={clsx('px-3 py-1.5 rounded-lg text-sm font-medium transition-all border',
                settings?.ai_primary_provider === p
                  ? 'bg-blue-600 border-blue-500 text-white'
                  : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-gray-200')}>
              {p === 'claude' ? '🤖 Claude' : p === 'openai' ? '🟢 GPT-4o' : p === 'ollama' ? '🦙 Ollama' : '⛔ Skip'}
            </button>
          ))}
        </div>
      </div>

      {/* API Keys */}
      <div className="space-y-3">
        <h3 className="font-semibold text-gray-200 text-sm">API ключи</h3>
        {[
          { key: 'claude_api_key',  label: 'Claude API Key',  placeholder: 'sk-ant-api03-...' },
          { key: 'openai_api_key',  label: 'OpenAI API Key',  placeholder: 'sk-...' },
        ].map(({ key, label, placeholder }) => (
          <div key={key}>
            <label className="text-xs text-gray-500 block mb-1">{label}</label>
            <div className="flex items-center gap-2">
              <input
                type={showKeys[key] ? 'text' : 'password'}
                value={settings?.[key] ?? ''}
                onChange={e => onUpdate({ [key]: e.target.value })}
                placeholder={placeholder}
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 font-mono outline-none focus:border-blue-500"
              />
              <button onClick={() => toggleKey(key)} className="p-2 text-gray-600 hover:text-gray-300 transition-colors">
                {showKeys[key] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
        ))}
        <div>
          <label className="text-xs text-gray-500 block mb-1">Ollama URL</label>
          <input value={settings?.ollama_url ?? 'http://localhost:11434'}
            onChange={e => onUpdate({ ollama_url: e.target.value })}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 font-mono outline-none focus:border-blue-500" />
        </div>
      </div>

      {/* Test connection */}
      <div className="flex items-center gap-4">
        <button onClick={handleTest} disabled={testing}
          className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-600 text-gray-200 rounded-lg text-sm font-medium transition-colors disabled:opacity-50">
          {testing ? <Loader className="w-4 h-4 animate-spin" /> : <Brain className="w-4 h-4" />}
          Тест подключения AI
        </button>
        {testResult === 'ok'   && <span className="flex items-center gap-1 text-emerald-400 text-sm"><CheckCircle className="w-4 h-4" /> AI API доступен</span>}
        {testResult === 'fail' && <span className="flex items-center gap-1 text-red-400 text-sm"><XCircle className="w-4 h-4" /> Недоступен</span>}
      </div>

      {/* AI Stats */}
      {aiStats && aiStats.total > 0 && (
        <div className="bg-gray-800/50 rounded-xl p-4">
          <h3 className="font-semibold text-gray-300 text-sm mb-3">Статистика AI решений</h3>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div><div className="text-xs text-gray-500">Решений всего</div><div className="text-xl font-bold text-gray-100">{aiStats.total}</div></div>
          </div>
          {aiStats.providers.map(p => (
            <div key={p.provider} className="flex items-center justify-between py-2 border-t border-gray-700/50 text-sm">
              <span className="text-gray-400 font-medium capitalize">{p.provider}</span>
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span>WR <span className={clsx('font-bold', p.win_rate >= 50 ? 'text-emerald-400' : 'text-red-400')}>{p.win_rate?.toFixed(1)}%</span></span>
                <span>Avg conf <span className="text-gray-300">{p.avg_conf?.toFixed(0)}%</span></span>
                <span>{p.closed_positions} поз.</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
