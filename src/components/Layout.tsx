import { useEffect, useState } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { LayoutDashboard, List, Settings, Activity, Zap, BookMarked, BarChart2, Wallet, TrendingUp, Sun, Moon, KeyRound } from 'lucide-react';
import { useAppStore } from '../store';
import clsx from 'clsx';
import { Toaster } from 'sonner';
import { GlossaryModal } from './help/HelpSystem';
import { RuntimeStatusBanner } from './RuntimeStatusBanner';

const Layout = () => {
  const { sourceLabel, theme, toggleTheme, isUiDemoMode, backendHealth, lastApiError } = useAppStore();
  const [glossaryOpen, setGlossaryOpen] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Дашборд' },
    { to: '/signals', icon: List, label: 'Сигналы' },
    { to: '/trades', icon: TrendingUp, label: 'Сделки' },
    { to: '/account', icon: Wallet, label: 'Счёт' },
    { to: '/backtest', icon: BarChart2, label: 'Бэктест' },
    { to: '/activity', icon: Activity, label: 'События' },
    { to: '/settings', icon: Settings, label: 'Настройки' },
    { to: '/tokens', icon: KeyRound, label: 'Токены' },
  ];

  const statusTone = lastApiError ? 'bg-rose-500' : backendHealth === 'degraded' ? 'bg-amber-400' : 'bg-emerald-500';
  const statusLabel = lastApiError ? 'есть ошибка API' : backendHealth === 'degraded' ? 'degraded' : 'ready';

  return (
    <div className="flex min-h-screen bg-gray-950 text-gray-100 font-sans">
      <a href="#app-main-content" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white">Перейти к содержимому</a>
      <aside className="hidden md:flex w-20 xl:w-72 border-r border-gray-800 flex-col transition-all duration-300 shrink-0 sticky top-0 h-screen">
        <div className="h-16 flex items-center justify-center xl:justify-start xl:px-6 border-b border-gray-800 gap-3"><Zap className="w-6 h-6 text-yellow-400 shrink-0" /><span className="hidden xl:inline font-bold text-xl tracking-tight">BotPanel</span></div>
        <nav className="flex-1 py-4 space-y-0.5" aria-label="Основная навигация">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.to === '/'} title={item.label} aria-label={item.label} className={({ isActive }) => clsx('flex items-center px-3 py-3 mx-2 rounded-lg transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400', isActive ? 'bg-blue-600/10 text-blue-400' : 'text-gray-400 hover:bg-gray-900 hover:text-gray-200')}>
              <item.icon className="w-5 h-5 xl:mr-3 shrink-0" />
              <span className="hidden xl:inline font-medium text-sm">{item.label}</span>
              <span className="xl:hidden sr-only">{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-gray-800 space-y-2">
          <button type="button" onClick={() => setGlossaryOpen(true)} className="flex items-center w-full px-3 py-2 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-900 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400" title="Глоссарий"><BookMarked className="w-4 h-4 xl:mr-2.5 shrink-0" /><span className="hidden xl:inline text-xs font-medium">Глоссарий</span><span className="xl:hidden sr-only">Глоссарий</span></button>
          {!isUiDemoMode && (
            <>
              <button type="button" onClick={toggleTheme} className="flex items-center w-full px-3 py-2 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-900 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400" title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}>{theme === 'dark' ? <Sun className="w-4 h-4 xl:mr-2.5 shrink-0" /> : <Moon className="w-4 h-4 xl:mr-2.5 shrink-0" />}<span className="hidden xl:inline text-xs font-medium">{theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}</span><span className="xl:hidden sr-only">{theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}</span></button>
              <div className="hidden xl:flex items-center justify-between text-xs"><span className="text-gray-600">Источник</span><span className="font-mono text-gray-500">{sourceLabel || 'API'}</span></div>
              <div className="hidden xl:flex items-center justify-between text-xs"><span className="text-gray-600">Статус UI</span><span className="font-mono text-gray-500">{statusLabel}</span></div>
            </>
          )}
          <div className="flex items-center justify-between text-[10px] text-gray-700 font-mono pt-1 border-t border-gray-900"><span>v{import.meta.env.VITE_APP_VERSION || '1.1.0'}</span><div className={clsx('w-1.5 h-1.5 rounded-full', statusTone)} aria-label={statusLabel} /></div>
        </div>
      </aside>
      <main id="app-main-content" className="flex-1 overflow-y-auto relative flex flex-col min-w-0 pb-20 md:pb-0"><RuntimeStatusBanner /><Outlet /></main>
      <nav className="fixed bottom-0 left-0 right-0 z-40 border-t border-gray-800 bg-gray-950/95 backdrop-blur md:hidden" aria-label="Основные разделы">
        <div className="overflow-x-auto px-2 py-2 scrollbar-thin scrollbar-thumb-gray-800">
          <div className="flex min-w-max gap-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) => clsx(
                  'flex min-w-[72px] flex-col items-center justify-center gap-1 rounded-xl px-3 py-2 text-[11px] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400',
                  isActive ? 'bg-blue-600/10 text-blue-300' : 'text-gray-400 hover:bg-gray-900 hover:text-gray-200',
                )}
              >
                <item.icon className="h-4 w-4" />
                <span className="whitespace-nowrap">{item.label}</span>
              </NavLink>
            ))}
          </div>
        </div>
      </nav>
      <Toaster position="top-right" theme="dark" richColors />
      {glossaryOpen && <GlossaryModal onClose={() => setGlossaryOpen(false)} />}
    </div>
  );
};

export default Layout;
