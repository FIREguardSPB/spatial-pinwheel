import React from 'react';
import { Brain, ExternalLink } from 'lucide-react';
import clsx from 'clsx';
import { Link } from 'react-router-dom';
import { HelpLabel } from '../../components/help/HelpSystem';
import type { RiskSettings } from '../../types';

const AI_MODES = [
  { value: 'off', label: 'Off', desc: 'ИИ не участвует в решении.' },
  { value: 'advisory', label: 'Advisory', desc: 'ИИ даёт мнение, но не меняет решение автоматически.' },
  { value: 'override', label: 'Override', desc: 'ИИ может изменить решение, если уверен достаточно сильно.' },
  { value: 'required', label: 'Required', desc: 'Без ответа ИИ сигнал не считается готовым.' },
] as const;

const PROVIDERS = [
  { value: 'claude', label: 'Claude' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'deepseek', label: 'DeepSeek Reasoner' },
  { value: 'ollama', label: 'Ollama' },
  { value: 'skip', label: 'Skip' },
] as const;

export const AISettingsPanel: React.FC<{ settings: RiskSettings; onUpdate: (patch: Partial<RiskSettings>) => void }> = ({ settings, onUpdate }) => {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-semibold text-gray-200 mb-3 flex items-center gap-2">
          <Brain className="w-4 h-4 text-blue-400" />
          <HelpLabel label="Режим AI" helpId="ai_mode" className="text-base" />
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {AI_MODES.map((mode) => (
            <button
              key={mode.value}
              type="button"
              onClick={() => onUpdate({ ai_mode: mode.value })}
              className={clsx(
                'rounded-xl border p-4 text-left transition-colors',
                settings.ai_mode === mode.value ? 'border-blue-500/60 bg-blue-500/10 text-blue-200' : 'border-gray-800 bg-gray-950 text-gray-300 hover:border-gray-600',
              )}
            >
              <div className="font-semibold">{mode.label}</div>
              <div className="mt-1 text-sm text-gray-400">{mode.desc}</div>
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-2">
          <HelpLabel label={`Минимальная уверенность AI: ${settings.ai_min_confidence ?? 70}%`} helpId="ai_confidence" />
        </label>
        <input
          type="range"
          min={50}
          max={95}
          step={5}
          value={settings.ai_min_confidence ?? 70}
          onChange={(e) => onUpdate({ ai_min_confidence: Number(e.target.value) })}
          className="w-full accent-blue-500"
        />
        <div className="mt-1 flex justify-between text-xs text-gray-600">
          <span>50% мягко</span>
          <span>95% строго</span>
        </div>
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-2">
          <HelpLabel label="Основной AI провайдер" helpId="ai_provider" />
        </label>
        <div className="flex flex-wrap gap-2">
          {PROVIDERS.map((provider) => (
            <button
              key={provider.value}
              type="button"
              onClick={() => onUpdate({ ai_primary_provider: provider.value })}
              className={clsx(
                'px-3 py-2 rounded-lg border text-sm transition-colors',
                settings.ai_primary_provider === provider.value ? 'border-blue-500 bg-blue-600 text-white' : 'border-gray-700 bg-gray-950 text-gray-300 hover:border-gray-500',
              )}
            >
              {provider.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-2">Fallback providers</label>
        <input
          value={settings.ai_fallback_providers ?? 'deepseek,ollama,skip'}
          onChange={(e) => onUpdate({ ai_fallback_providers: e.target.value })}
          className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
          placeholder="deepseek,ollama,skip"
        />
        <p className="mt-1 text-xs text-gray-600">Указывайте через запятую: например <code>deepseek,ollama,skip</code>.</p>
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-2">
          <HelpLabel label="Ollama URL" helpId="ollama_url" />
        </label>
        <input
          value={settings.ollama_url ?? 'http://localhost:11434'}
          onChange={(e) => onUpdate({ ollama_url: e.target.value })}
          className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-blue-500"
        />
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-950 p-4 text-sm text-gray-300">
        <div className="font-semibold text-gray-100 mb-2">Ключи API хранятся отдельно</div>
        <p className="text-gray-400 leading-relaxed">
          Секреты не сохраняются в обычных настройках, чтобы не смешивать конфигурацию и чувствительные данные.
          Управляйте ключами на странице токенов.
        </p>
        <Link to="/tokens" className="mt-3 inline-flex items-center gap-1.5 text-blue-400 hover:text-blue-300">
          Открыть токены <ExternalLink className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
};
