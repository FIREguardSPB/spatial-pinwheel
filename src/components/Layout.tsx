import { useEffect, useState } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { LayoutDashboard, List, Settings, Activity, Zap, BookMarked, BarChart2, Wallet, TrendingUp, Sun, Moon, KeyRound } from 'lucide-react';
import { useAppStore } from '../store';
import clsx from 'clsx';
import { Toaster } from 'sonner';
import { ConnectionStatus } from '../features/dashboard/ConnectionStatus';
import { GlossaryModal } from './help/HelpSystem';

const Layout = () => {
  const { connectionStatus, isMockMode, theme, toggleTheme, isUiDemoMode } = useAppStore();
  const [glossaryOpen, setGlossaryOpen] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  const navItems = [
    { to: '/',          icon: LayoutDashboard, label: 'Дашборд' },
    { to: '/signals',   icon: List,            label: 'Сигналы'   },
    { to: '/trades',    icon: TrendingUp,      label: 'Сделки'    },
    { to: '/account',   icon: Wallet,          label: 'Счёт'   },
    { to: '/backtest',  icon: BarChart2,       label: 'Бэктест'  },
    { to: '/activity',  icon: Activity,        label: 'События'  },
    { to: '/settings',  icon: Settings,        label: 'Настройки'  },
  { to: '/tokens',    icon: KeyRound,        label: 'Токены'     },
  ];

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 font-sans">
      {/* Sidebar */}
      <aside className="w-16 md:w-64 border-r border-gray-800 flex flex-col transition-all duration-300 shrink-0">
        <div className="h-16 flex items-center justify-center md:justify-start md:px-6 border-b border-gray-800">
          <Zap className="w-6 h-6 text-yellow-400 mr-0 md:mr-3 shrink-0" />
          <span className="hidden md:inline font-bold text-xl tracking-tight">BotPanel</span>
        </div>

        <nav className="flex-1 py-4 space-y-0.5">
          {navItems.map(item => (
            <NavLink key={item.to} to={item.to} end={item.to === '/'}
              className={({ isActive }) => clsx(
                'flex items-center px-3 py-3 mx-2 rounded-lg transition-colors',
                isActive ? 'bg-blue-600/10 text-blue-400' : 'text-gray-400 hover:bg-gray-900 hover:text-gray-200'
              )}>
              <item.icon className="w-5 h-5 md:mr-3 shrink-0" />
              <span className="hidden md:inline font-medium text-sm">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-gray-800 space-y-2">
          {/* Glossary button */}
          <button onClick={() => setGlossaryOpen(true)}
            className="flex items-center w-full px-3 py-2 mx-0 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-900 transition-colors">
            <BookMarked className="w-4 h-4 md:mr-2.5 shrink-0" />
            <span className="hidden md:inline text-xs font-medium">Глоссарий</span>
          </button>

          {!isUiDemoMode && (
            <>
              <button
                onClick={toggleTheme}
                className="flex items-center w-full px-3 py-2 mx-0 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-900 transition-colors"
                title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
              >
                {theme === 'dark'
                  ? <Sun className="w-4 h-4 md:mr-2.5 shrink-0" />
                  : <Moon className="w-4 h-4 md:mr-2.5 shrink-0" />}
                <span className="hidden md:inline text-xs font-medium">
                  {theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
                </span>
              </button>
              <div className="hidden md:flex items-center justify-between text-xs">
                <span className="text-gray-600">Источник</span>
                <span className="font-mono text-gray-500">{isMockMode ? 'MOCK' : 'TBANK'}</span>
              </div>
            </>
          )}

          <div className="flex items-center justify-between text-[10px] text-gray-700 font-mono pt-1 border-t border-gray-900">
            <span>v{import.meta.env.VITE_APP_VERSION || '1.1.0'}</span>
            <div className={clsx('w-1.5 h-1.5 rounded-full', connectionStatus === 'connected' ? 'bg-green-500' : 'bg-red-500 animate-pulse')} />
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto relative flex flex-col min-w-0">
        {!isUiDemoMode && (
          <div className="absolute top-4 right-4 z-50">
            <ConnectionStatus />
          </div>
        )}
        <Outlet />
      </main>

      <Toaster position="top-right" theme="dark" />
      {glossaryOpen && <GlossaryModal onClose={() => setGlossaryOpen(false)} />}
    </div>
  );
};

export default Layout;
