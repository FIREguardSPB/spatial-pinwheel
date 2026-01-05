import { useState, useEffect } from 'react';
import { useBotStatus, useBotControl, useSettings, useUpdateSettings } from './hooks';
import type { RiskSettings } from '../../types';
import { Play, Square, Shield, Save, AlertCircle } from 'lucide-react';
import clsx from 'clsx';
import { useAppStore } from '../../store';

export default function SettingsPage() {
    const { data: status } = useBotStatus();
    const { mutate: controlBot, isPending: isControlPending } = useBotControl();

    const { data: settings } = useSettings();
    const { mutate: updateSettings, isPending: isUpdating } = useUpdateSettings();

    const [formState, setFormState] = useState<RiskSettings | null>(null);

    useEffect(() => {
        if (settings) setFormState(settings);
    }, [settings]);

    const { isMockMode, setMockMode, authToken, setAuthToken } = useAppStore();
    const [localToken, setLocalToken] = useState(authToken || '');

    const handleApplyPreset = (profile: RiskSettings['risk_profile']) => {
        if (!formState) return;
        let newSettings: Partial<RiskSettings> = { risk_profile: profile };

        switch (profile) {
            case 'conservative':
                newSettings = {
                    ...newSettings,
                    risk_per_trade_pct: 0.5,
                    daily_loss_limit_pct: 1.0,
                    max_concurrent_positions: 1,
                    decision_threshold: 80,
                    rr_min: 1.8,
                    atr_stop_hard_min: 0.4, atr_stop_hard_max: 4.0,
                    atr_stop_soft_min: 0.8, atr_stop_soft_max: 2.2,
                    w_regime: 20, w_volatility: 15, w_momentum: 15, w_levels: 20, w_costs: 15, w_liquidity: 5
                };
                break;
            case 'balanced':
                newSettings = {
                    ...newSettings,
                    risk_per_trade_pct: 1.0,
                    daily_loss_limit_pct: 2.0,
                    max_concurrent_positions: 3,
                    decision_threshold: 70,
                    rr_min: 1.5,
                    atr_stop_hard_min: 0.3, atr_stop_hard_max: 5.0,
                    atr_stop_soft_min: 0.6, atr_stop_soft_max: 2.5,
                    w_regime: 20, w_volatility: 15, w_momentum: 15, w_levels: 20, w_costs: 15, w_liquidity: 5
                };
                break;
            case 'aggressive':
                newSettings = {
                    ...newSettings,
                    risk_per_trade_pct: 2.0,
                    daily_loss_limit_pct: 5.0,
                    max_concurrent_positions: 5,
                    decision_threshold: 60,
                    rr_min: 1.3,
                    atr_stop_hard_min: 0.25, atr_stop_hard_max: 6.0,
                    atr_stop_soft_min: 0.5, atr_stop_soft_max: 3.0,
                    w_regime: 20, w_volatility: 15, w_momentum: 15, w_levels: 20, w_costs: 15, w_liquidity: 5
                };
                break;
        }
        setFormState({ ...formState, ...newSettings });
    };

    const handleSave = () => {
        if (formState) updateSettings(formState);
    };

    const confirmAndToggleBot = () => {
        const action = status?.is_running ? 'stop' : 'start';
        if (confirm(`Are you sure you want to ${action.toUpperCase()} the bot?`)) {
            controlBot(action);
        }
    };

    if (!formState) return <div className="p-8">Loading settings...</div>;

    return (
        <div className="p-6 max-w-4xl mx-auto">
            <h1 className="text-3xl font-bold mb-8 text-gray-100 flex items-center">
                <Shield className="mr-3 text-blue-500" /> System Settings
            </h1>

            {/* Bot Control Section */}
            <section className="mb-8 bg-gray-900 border border-gray-800 rounded-lg p-6">
                <h2 className="text-xl font-bold mb-4 text-gray-200">Bot Control</h2>
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                        <div className={clsx("w-3 h-3 rounded-full animate-pulse", status?.is_running ? "bg-green-500" : "bg-red-500")} />
                        <div className="flex flex-col">
                            <span className="font-mono text-lg text-gray-300">
                                Status: <span className={status?.is_running ? "text-green-500" : "text-red-500"}>{status?.is_running ? "RUNNING" : "STOPPED"}</span>
                            </span>
                            <span className="text-xs text-gray-500 font-mono">
                                Mode: {status?.mode} | Paper: {status?.is_paper ? 'YES' : 'NO'} | Active: {status?.active_instrument_id || 'None'}
                            </span>
                            {!status?.is_paper && (
                                <span className="text-xs text-red-500 font-bold animate-pulse mt-1">
                                    ⚠️ LIVE TRADING DANGER
                                </span>
                            )}
                        </div>
                    </div>
                    <button
                        onClick={confirmAndToggleBot}
                        disabled={isControlPending}
                        className={clsx(
                            "flex items-center px-6 py-2 rounded-lg font-bold transition-colors",
                            status?.is_running
                                ? "bg-red-600 hover:bg-red-500 text-white"
                                : "bg-green-600 hover:bg-green-500 text-white"
                        )}
                    >
                        {status?.is_running ? <><Square className="w-4 h-4 mr-2" /> STOP BOT</> : <><Play className="w-4 h-4 mr-2" /> START BOT</>}
                    </button>
                </div>
            </section>

            {/* Risk Configuration */}
            <section className="mb-8 bg-gray-900 border border-gray-800 rounded-lg p-6">
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-xl font-bold text-gray-200">Risk Configuration</h2>
                    <div className="flex space-x-2">
                        {['conservative', 'balanced', 'aggressive'].map((p) => (
                            <button
                                key={p}
                                onClick={() => handleApplyPreset(p as any)}
                                className={clsx(
                                    "px-3 py-1 text-xs rounded border transition-colors capitalize",
                                    formState.risk_profile === p
                                        ? "bg-blue-600 border-blue-600 text-white"
                                        : "border-gray-700 text-gray-400 hover:border-gray-500"
                                )}
                            >
                                {p}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div>
                        <label className="block text-sm text-gray-500 mb-1">Risk Per Trade (%)</label>
                        <input
                            type="number"
                            value={formState.risk_per_trade_pct}
                            onChange={(e) => setFormState({ ...formState, risk_per_trade_pct: parseFloat(e.target.value) })}
                            className="w-full bg-gray-950 border border-gray-800 rounded p-2 text-gray-200 focus:border-blue-500 outline-none"
                        />
                    </div>
                    <div>
                        <label className="block text-sm text-gray-500 mb-1">Daily Loss Limit (%)</label>
                        <input
                            type="number"
                            value={formState.daily_loss_limit_pct}
                            onChange={(e) => setFormState({ ...formState, daily_loss_limit_pct: parseFloat(e.target.value) })}
                            className="w-full bg-gray-950 border border-gray-800 rounded p-2 text-gray-200 focus:border-blue-500 outline-none"
                        />
                    </div>
                    <div>
                        <label className="block text-sm text-gray-500 mb-1">Max Concurrent Pos</label>
                        <input
                            type="number"
                            value={formState.max_concurrent_positions}
                            onChange={(e) => setFormState({ ...formState, max_concurrent_positions: parseInt(e.target.value) })}
                            className="w-full bg-gray-950 border border-gray-800 rounded p-2 text-gray-200 focus:border-blue-500 outline-none"
                        />
                    </div>
                </div>

            </section>

            {/* Autotrading Strictness */}
            <section className="mb-8 bg-gray-900 border border-gray-800 rounded-lg p-6">
                <h2 className="text-xl font-bold mb-6 text-gray-200">Autotrading Strictness (Decision Engine)</h2>

                <div className="mb-8">
                    <div className="flex justify-between mb-2">
                        <label className="text-sm text-gray-500">Decision Threshold (%)</label>
                        <span className="text-xl font-bold text-blue-400">{formState.decision_threshold ?? 70}%</span>
                    </div>
                    <input
                        type="range" min="0" max="100"
                        value={formState.decision_threshold ?? 70}
                        onChange={(e) => setFormState({ ...formState, decision_threshold: parseInt(e.target.value) })}
                        className="w-full h-2 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-blue-600"
                    />
                    <p className="text-xs text-gray-600 mt-2">Minimum Score % required to TAKE a trade automatically.</p>
                </div>

                <div className="mb-8">
                    <label className="text-sm text-gray-500 mb-1 block">RR Min (Hard Gate)</label>
                    <input
                        type="number" step="0.1"
                        value={formState.rr_min ?? 1.5}
                        onChange={(e) => setFormState({ ...formState, rr_min: parseFloat(e.target.value) })}
                        className="w-full bg-gray-950 border border-gray-800 rounded p-2 text-gray-200 text-sm focus:border-blue-500 outline-none"
                    />
                    <p className="text-xs text-gray-600 mt-1">Signals with Reward/Risk ratio below this will be HARD REJECTED.</p>
                </div>

                <h3 className="text-sm font-bold text-gray-400 mb-4 uppercase tracking-wider">Scoring Weights (Total points)</h3>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
                    {[
                        { label: 'Regime (Trend)', key: 'w_regime', def: 20 },
                        { label: 'Volatility', key: 'w_volatility', def: 15 },
                        { label: 'Momentum', key: 'w_momentum', def: 15 },
                        { label: 'Levels (S/R)', key: 'w_levels', def: 20 },
                        { label: 'Costs (RR)', key: 'w_costs', def: 15 },
                        { label: 'Liquidity', key: 'w_liquidity', def: 5 },
                    ].map((item) => (
                        <div key={item.key}>
                            <label className="block text-xs text-gray-500 mb-1">{item.label}</label>
                            <input
                                type="number"
                                value={(formState as any)[item.key] ?? item.def}
                                onChange={(e) => setFormState({ ...formState, [item.key]: parseInt(e.target.value) })}
                                className="w-full bg-gray-950 border border-gray-800 rounded p-2 text-gray-200 text-sm focus:border-blue-500 outline-none"
                            />
                        </div>
                    ))}
                </div>

                <h3 className="text-sm font-bold text-gray-400 mb-4 uppercase tracking-wider">Hard Stops (ATR)</h3>
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="block text-xs text-gray-500 mb-1">Min Stop Distance (ATR)</label>
                        <input
                            type="number" step="0.1"
                            value={formState.atr_stop_hard_min ?? 0.6}
                            onChange={(e) => setFormState({ ...formState, atr_stop_hard_min: parseFloat(e.target.value) })}
                            className="w-full bg-gray-950 border border-gray-800 rounded p-2 text-gray-200 text-sm focus:border-blue-500 outline-none"
                        />
                    </div>
                    <div>
                        <label className="block text-xs text-gray-500 mb-1">Max Stop Distance (ATR)</label>
                        <input
                            type="number" step="0.1"
                            value={formState.atr_stop_hard_max ?? 2.5}
                            onChange={(e) => setFormState({ ...formState, atr_stop_hard_max: parseFloat(e.target.value) })}
                            className="w-full bg-gray-950 border border-gray-800 rounded p-2 text-gray-200 text-sm focus:border-blue-500 outline-none"
                        />
                    </div>
                </div>

                <h3 className="text-sm font-bold text-gray-400 mb-4 mt-6 uppercase tracking-wider">Soft Stops (ATR)</h3>
                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="block text-xs text-gray-500 mb-1">Soft Min (Scoring)</label>
                        <input
                            type="number" step="0.1"
                            value={formState.atr_stop_soft_min ?? 0.8}
                            onChange={(e) => setFormState({ ...formState, atr_stop_soft_min: parseFloat(e.target.value) })}
                            className="w-full bg-gray-950 border border-gray-800 rounded p-2 text-gray-200 text-sm focus:border-blue-500 outline-none"
                        />
                    </div>
                    <div>
                        <label className="block text-xs text-gray-500 mb-1">Soft Max (Scoring)</label>
                        <input
                            type="number" step="0.1"
                            value={formState.atr_stop_soft_max ?? 2.0}
                            onChange={(e) => setFormState({ ...formState, atr_stop_soft_max: parseFloat(e.target.value) })}
                            className="w-full bg-gray-950 border border-gray-800 rounded p-2 text-gray-200 text-sm focus:border-blue-500 outline-none"
                        />
                    </div>
                </div>
            </section>

            <div className="mt-8 mb-8 flex justify-end">
                <button
                    onClick={handleSave}
                    disabled={isUpdating}
                    className="flex items-center px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-bold shadow-lg disabled:opacity-50 transition-all transform hover:scale-105"
                >
                    <Save className="w-5 h-5 mr-2" /> Save Full Configuration
                </button>
            </div>

            <section className="bg-gray-900 border border-gray-800 rounded-lg p-6 opacity-80 hover:opacity-100 transition-opacity">
                <h2 className="text-lg font-bold mb-4 text-gray-400 flex items-center">
                    <AlertCircle className="w-4 h-4 mr-2" /> Developer / Connectivity
                </h2>
                <div className="mb-4 text-xs font-mono text-gray-600 bg-gray-950 p-2 rounded border border-gray-800">
                    API_BASE: {import.meta.env.VITE_API_URL || '/api'}
                </div>
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <span className="text-gray-400">Mock Mode</span>
                        <button
                            onClick={() => {
                                setMockMode(!isMockMode);
                                window.location.reload();
                            }}
                            className={clsx(
                                "w-12 h-6 rounded-full p-1 transition-colors relative",
                                isMockMode ? "bg-yellow-500" : "bg-gray-700"
                            )}
                        >
                            <div className={clsx("w-4 h-4 bg-white rounded-full shadow-sm transition-transform", isMockMode ? "translate-x-6" : "translate-x-0")} />
                        </button>
                    </div>

                    <div>
                        <label className="block text-sm text-gray-500 mb-1">Auth Token (Bearer)</label>
                        <div className="flex space-x-2">
                            <input
                                type="password"
                                value={localToken}
                                onChange={(e) => setLocalToken(e.target.value)}
                                className="flex-1 bg-gray-950 border border-gray-800 rounded p-2 text-gray-200"
                                placeholder="Paste JWT (••••••)"
                            />
                            {localToken && (
                                <button
                                    onClick={() => setLocalToken('')}
                                    className="px-2 py-1 text-gray-500 hover:text-gray-300"
                                >
                                    ✕
                                </button>
                            )}
                            <button
                                onClick={() => setAuthToken(localToken)}
                                className="px-3 py-1 bg-blue-600 hover:bg-blue-500 rounded text-sm text-white"
                            >
                                Set
                            </button>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    );
}
