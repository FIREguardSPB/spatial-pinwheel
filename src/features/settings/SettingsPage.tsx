import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Bell, Brain, Play, Save, Shield, Square } from 'lucide-react';
import { toast } from 'sonner';
import clsx from 'clsx';

import { apiClient } from '../../services/api';
import { useAppStore } from '../../store';
import type { RiskSettings } from '../../types';
import { ConfirmModal, TradeModeChip } from '../../components/ui/UIComponents';
import { HelpLabel } from '../../components/help/HelpSystem';
import { AISettingsPanel } from './AISettingsPanel';
import { useBotControl, useBotStatus, useSettings, useUpdateSettings } from './hooks';

const presets: Record<RiskSettings['risk_profile'], Partial<RiskSettings>> = {
  conservative: {
    risk_per_trade_pct: 0.5,
    daily_loss_limit_pct: 1,
    max_concurrent_positions: 1,
    decision_threshold: 80,
    rr_min: 1.8,
  },
  balanced: {
    risk_per_trade_pct: 1,
    daily_loss_limit_pct: 2,
    max_concurrent_positions: 2,
    decision_threshold: 70,
    rr_min: 1.5,
  },
  aggressive: {
    risk_per_trade_pct: 2,
    daily_loss_limit_pct: 4,
    max_concurrent_positions: 4,
    decision_threshold: 60,
    rr_min: 1.3,
  },
};

const modes: Array<{ value: RiskSettings['trade_mode']; title: string; desc: string }> = [
  { value: 'review', title: 'Ручное ревью', desc: 'Сигнал создаётся, а вход подтверждаете вы.' },
  { value: 'auto_paper', title: 'Авто Paper', desc: 'Бот открывает сделки сам, но только на виртуальном счёте.' },
  { value: 'auto_live', title: 'Авто Live', desc: 'Бот открывает и закрывает реальные сделки на счёте T-Bank.' },
];

function SectionCard({ title, description, children }: { title: React.ReactNode; description?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="bg-gray-900 border border-gray-800 rounded-2xl p-6 space-y-5">
      <div>
        <h2 className="text-lg font-bold text-gray-100">{title}</h2>
        {description ? <p className="text-sm text-gray-500 mt-1">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}

function Field({ label, helpId, children }: { label: string; helpId?: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-2">
      <span className="text-sm text-gray-400">
        <HelpLabel label={label} helpId={helpId} />
      </span>
      {children}
    </label>
  );
}

function Input({ value, onChange, type = 'text', min, max, step, placeholder }: any) {
  return (
    <input
      type={type}
      value={value ?? ''}
      min={min}
      max={max}
      step={step}
      placeholder={placeholder}
      onChange={(e) => onChange(type === 'number' ? Number(e.target.value) : e.target.value)}
      className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
    />
  );
}

export default function SettingsPage() {
  const { data: status } = useBotStatus();
  const { mutate: controlBot, isPending: isControlPending } = useBotControl();
  const { data: settings } = useSettings();
  const { mutate: updateSettings, isPending: isUpdating } = useUpdateSettings();
  const { isMockMode, setMockMode, authToken, setAuthToken } = useAppStore();

  const [formState, setFormState] = useState<RiskSettings | null>(null);
  const [localToken, setLocalToken] = useState(authToken ?? '');
  const [confirmAction, setConfirmAction] = useState<null | 'start' | 'stop'>(null);
  const [tgToken, setTgToken] = useState('');
  const [tgChatId, setTgChatId] = useState('');
  const [tgTesting, setTgTesting] = useState(false);

  useEffect(() => {
    if (settings) setFormState(settings);
  }, [settings]);

  const selectedTgEvents = useMemo(() => (formState?.notification_events ?? '').split(',').filter(Boolean), [formState?.notification_events]);

  if (!formState) {
    return <div className="p-8 text-gray-400">Загрузка настроек…</div>;
  }

  const patch = (next: Partial<RiskSettings>) => setFormState((prev) => ({ ...(prev as RiskSettings), ...next }));

  const saveTelegram = async () => {
    try {
      if (tgToken) {
        await apiClient.post('/tokens', {
          key_name: 'TELEGRAM_BOT_TOKEN',
          value: tgToken,
          label: 'Telegram Bot Token',
          category: 'telegram',
        });
      }
      if (tgChatId) {
        await apiClient.post('/tokens', {
          key_name: 'TELEGRAM_CHAT_ID',
          value: tgChatId,
          label: 'Telegram Chat ID',
          category: 'telegram',
        });
      }
      toast.success('Telegram токены сохранены');
    } catch {
      toast.error('Не удалось сохранить Telegram токены');
    }
  };

  const testTelegram = async () => {
    setTgTesting(true);
    try {
      const tokens = (await apiClient.get('/tokens')).data as Array<{ id: string; key_name: string }>;
      const tokenRow = tokens.find((item) => item.key_name === 'TELEGRAM_BOT_TOKEN');
      if (!tokenRow) {
        toast.error('Сначала сохраните Telegram Bot Token');
        return;
      }
      const res = await apiClient.post(`/tokens/test/${tokenRow.id}`);
      toast[res.data.ok ? 'success' : 'error'](res.data.message);
    } catch {
      toast.error('Проверка Telegram не удалась');
    } finally {
      setTgTesting(false);
    }
  };

  const handleSave = () => {
    updateSettings(formState, {
      onSuccess: () => toast.success('Настройки сохранены'),
      onError: () => toast.error('Не удалось сохранить настройки'),
    });
  };

  const confirmAndToggleBot = () => setConfirmAction(status?.is_running ? 'stop' : 'start');

  const executeBotAction = () => {
    const action = confirmAction;
    if (!action) return;

    const runAction = () => {
      controlBot(action, {
        onSuccess: () => toast.success(action === 'start' ? 'Бот запущен' : 'Бот остановлен'),
        onError: () => toast.error('Не удалось выполнить команду'),
      });
    };

    if (action === 'start') {
      updateSettings({ ...formState, bot_enabled: true }, {
        onSuccess: runAction,
        onError: () => toast.error('Сначала не удалось сохранить режим торговли'),
      });
    } else {
      runAction();
    }

    setConfirmAction(null);
  };

  return (
    <>
      <div className="p-6 max-w-5xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <Shield className="w-7 h-7 text-blue-500" />
          <div>
            <h1 className="text-3xl font-bold text-gray-100">Настройки системы</h1>
            <p className="text-sm text-gray-500 mt-1">Режимы торговли, риск-параметры, AI и рабочие интеграции.</p>
          </div>
        </div>

        <SectionCard title="Управление ботом" description="Запуск и остановка сканирования рынка. Открытые позиции при остановке не закрываются автоматически.">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <div className={clsx('w-3 h-3 rounded-full', status?.is_running ? 'bg-green-500 animate-pulse' : 'bg-red-500')} />
                <div className="text-gray-100 font-semibold">{status?.is_running ? 'Бот запущен' : 'Бот остановлен'}</div>
                <TradeModeChip mode={formState.trade_mode} />
              </div>
              <div className="text-sm text-gray-500">Активный инструмент: {status?.active_instrument_id || 'нет открытых позиций'}</div>
              <div className="text-sm text-gray-500">Подключение: market data — {status?.connection.market_data}, broker — {status?.connection.broker}</div>
              {status?.warnings?.map((warning) => (
                <div key={warning} className="text-sm text-yellow-300 bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-3 py-2">{warning}</div>
              ))}
            </div>
            <button
              onClick={confirmAndToggleBot}
              disabled={isControlPending || isUpdating}
              className={clsx(
                'inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl font-semibold transition-colors disabled:opacity-60',
                status?.is_running ? 'bg-red-600 hover:bg-red-500 text-white' : 'bg-green-600 hover:bg-green-500 text-white',
              )}
            >
              {status?.is_running ? <Square className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              {status?.is_running ? 'Остановить бота' : 'Запустить бота'}
            </button>
          </div>
        </SectionCard>

        <SectionCard title={<HelpLabel label="Режим торговли" helpId="trade_mode" />} description="Выбирайте auto_live только после проверки T-Bank токена, account id и лимитов риска.">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {modes.map((mode) => (
              <button
                key={mode.value}
                type="button"
                onClick={() => patch({ trade_mode: mode.value })}
                className={clsx(
                  'rounded-xl border p-4 text-left transition-colors',
                  formState.trade_mode === mode.value ? 'border-blue-500 bg-blue-600/10 text-blue-100' : 'border-gray-800 bg-gray-950 text-gray-300 hover:border-gray-600',
                )}
              >
                <div className="font-semibold">{mode.title}</div>
                <div className="mt-1 text-sm text-gray-400">{mode.desc}</div>
              </button>
            ))}
          </div>
        </SectionCard>

        <SectionCard title="Профиль риска" description="Готовые пресеты быстро меняют базовые настройки риска.">
          <div className="flex flex-wrap gap-2">
            {(['conservative', 'balanced', 'aggressive'] as const).map((profile) => (
              <button
                key={profile}
                type="button"
                onClick={() => patch({ risk_profile: profile, ...presets[profile] })}
                className={clsx(
                  'px-3 py-2 rounded-lg border text-sm capitalize transition-colors',
                  formState.risk_profile === profile ? 'bg-blue-600 border-blue-500 text-white' : 'bg-gray-950 border-gray-800 text-gray-300 hover:border-gray-600',
                )}
              >
                {profile}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <Field label="Риск на сделку (%)" helpId="risk_per_trade">
              <Input type="number" min={0.1} max={10} step={0.1} value={formState.risk_per_trade_pct} onChange={(v: number) => patch({ risk_per_trade_pct: v })} />
            </Field>
            <Field label="Дневной лимит потерь (%)" helpId="daily_loss_limit">
              <Input type="number" min={0.5} max={20} step={0.1} value={formState.daily_loss_limit_pct} onChange={(v: number) => patch({ daily_loss_limit_pct: v })} />
            </Field>
            <Field label="Максимум открытых позиций" helpId="max_positions">
              <Input type="number" min={1} max={20} step={1} value={formState.max_concurrent_positions} onChange={(v: number) => patch({ max_concurrent_positions: v })} />
            </Field>
            <Field label="Минимальный R/R" helpId="rr">
              <Input type="number" min={1} max={10} step={0.1} value={formState.rr_min} onChange={(v: number) => patch({ rr_min: v })} />
            </Field>
            <Field label="Порог решения (0–100)" helpId="decision_threshold">
              <Input type="number" min={0} max={100} step={1} value={formState.decision_threshold} onChange={(v: number) => patch({ decision_threshold: v })} />
            </Field>
            <Field label="Время стопа (баров)">
              <Input type="number" min={1} max={30} step={1} value={formState.time_stop_bars} onChange={(v: number) => patch({ time_stop_bars: v })} />
            </Field>
            <Field label="Пауза после серии убытков: количество" helpId="cooldown">
              <Input type="number" min={1} max={10} step={1} value={formState.cooldown_after_losses.losses} onChange={(v: number) => patch({ cooldown_after_losses: { ...formState.cooldown_after_losses, losses: v } })} />
            </Field>
            <Field label="Пауза после серии убытков: минут" helpId="cooldown">
              <Input type="number" min={5} max={240} step={5} value={formState.cooldown_after_losses.minutes} onChange={(v: number) => patch({ cooldown_after_losses: { ...formState.cooldown_after_losses, minutes: v } })} />
            </Field>
            <Field label="Бумажный баланс счёта">
              <Input type="number" min={1000} step={1000} value={formState.account_balance} onChange={(v: number) => patch({ account_balance: v })} />
            </Field>
          </div>
        </SectionCard>

        <SectionCard title="AI-конфигурация" description="Настройки для финальной оценки сигнала через LLM-провайдера.">
          <AISettingsPanel settings={formState} onUpdate={patch} />
        </SectionCard>

        <SectionCard title="Telegram уведомления" description="Удобно для контроля сигналов и сделок с телефона.">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Field label="Telegram Bot Token">
              <Input value={tgToken} onChange={setTgToken} placeholder="Оставьте пустым, если уже сохранён на странице токенов" />
            </Field>
            <Field label="Telegram Chat ID">
              <Input value={tgChatId} onChange={setTgChatId} placeholder="Например: -100123456789" />
            </Field>
          </div>
          <div>
            <div className="text-sm text-gray-400 mb-2 inline-flex items-center gap-2">
              <Bell className="w-4 h-4 text-sky-400" /> События для уведомлений
            </div>
            <div className="flex flex-wrap gap-2">
              {[
                ['signal_created', 'Новый сигнал'],
                ['trade_executed', 'Сделка'],
                ['sl_hit', 'Стоп-лосс'],
                ['tp_hit', 'Тейк-профит'],
                ['daily_loss_limit', 'Дневной лимит'],
              ].map(([key, label]) => {
                const active = selectedTgEvents.includes(key);
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => {
                      const next = active ? selectedTgEvents.filter((v) => v !== key) : [...selectedTgEvents, key];
                      patch({ notification_events: next.join(',') });
                    }}
                    className={clsx('px-3 py-2 rounded-lg text-sm transition-colors', active ? 'bg-sky-700 text-white' : 'bg-gray-950 border border-gray-800 text-gray-300 hover:border-gray-600')}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <button onClick={saveTelegram} className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-sm font-medium">Сохранить Telegram токены</button>
            <button onClick={testTelegram} disabled={tgTesting} className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 text-sm font-medium disabled:opacity-60">{tgTesting ? 'Проверка…' : 'Проверить Telegram'}</button>
          </div>
        </SectionCard>

        <SectionCard title="Режим разработчика" description="Локальные служебные настройки клиента.">
          <div className="space-y-4">
            <div className="rounded-xl border border-gray-800 bg-gray-950 px-4 py-3 text-xs font-mono text-gray-500">
              API_BASE: {import.meta.env.VITE_API_URL || '/api/v1'}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-300">Mock Mode</span>
              <button
                onClick={() => {
                  setMockMode(!isMockMode);
                  window.location.reload();
                }}
                className={clsx('w-12 h-6 rounded-full p-1 transition-colors relative', isMockMode ? 'bg-yellow-500' : 'bg-gray-700')}
              >
                <div className={clsx('w-4 h-4 bg-white rounded-full shadow-sm transition-transform', isMockMode ? 'translate-x-6' : 'translate-x-0')} />
              </button>
            </div>
            <Field label="Bearer token для API">
              <div className="flex gap-2">
                <Input value={localToken} onChange={setLocalToken} placeholder="Вставьте токен доступа" />
                <button onClick={() => setAuthToken(localToken || null)} className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium">Применить</button>
              </div>
            </Field>
          </div>
        </SectionCard>

        <div className="flex flex-wrap items-center justify-between gap-3 pb-8">
          <div className="inline-flex items-start gap-2 text-sm text-yellow-200 bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-4 py-3">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>Сначала сохраните настройки, потом запускайте бота. Так вы не получите старт со старыми параметрами.</span>
          </div>
          <button onClick={handleSave} disabled={isUpdating} className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold disabled:opacity-60">
            <Save className="w-4 h-4" />
            {isUpdating ? 'Сохранение…' : 'Сохранить конфигурацию'}
          </button>
        </div>
      </div>

      {confirmAction && (
        <ConfirmModal
          title={confirmAction === 'start' ? 'Запустить бота?' : 'Остановить бота?'}
          description={confirmAction === 'start' ? 'Бот начнёт искать сигналы с текущими сохранёнными настройками.' : 'Новые входы перестанут открываться, но уже открытые позиции останутся под наблюдением.'}
          confirmLabel={confirmAction === 'start' ? 'Запустить' : 'Остановить'}
          variant={confirmAction === 'stop' ? 'danger' : 'default'}
          onConfirm={executeBotAction}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </>
  );
}
