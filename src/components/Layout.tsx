import { Outlet, NavLink } from 'react-router-dom';
import { LayoutDashboard, List, Settings, Activity, Zap } from 'lucide-react';
import { useAppStore } from '../store';
import clsx from 'clsx';
import { Toaster } from 'sonner';
import { ConnectionStatus } from '../features/dashboard/ConnectionStatus';

const Layout = () => {
    const { connectionStatus, isMockMode } = useAppStore();

    const navItems = [
        { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
        { to: '/signals', icon: List, label: 'Signals' },
        { to: '/activity', icon: Activity, label: 'Activity' },
        { to: '/settings', icon: Settings, label: 'Settings' },
    ];

    return (
        <div className="flex h-screen bg-gray-950 text-gray-100 font-sans">
            {/* Sidebar */}
            <aside className="w-16 md:w-64 border-r border-gray-800 flex flex-col transition-all duration-300">
                <div className="h-16 flex items-center justify-center md:justify-start md:px-6 border-b border-gray-800">
                    <Zap className="w-6 h-6 text-yellow-400 mr-0 md:mr-3" />
                    <span className="hidden md:inline font-bold text-xl tracking-tight">BotPanel</span>
                </div>

                <nav className="flex-1 py-6 space-y-1">
                    {navItems.map((item) => (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            className={({ isActive }) =>
                                clsx(
                                    'flex items-center px-4 py-3 mx-2 rounded-lg transition-colors',
                                    isActive
                                        ? 'bg-blue-600/10 text-blue-400'
                                        : 'text-gray-400 hover:bg-gray-900 hover:text-gray-200'
                                )
                            }
                        >
                            <item.icon className="w-5 h-5 md:mr-3" />
                            <span className="hidden md:inline font-medium">{item.label}</span>
                        </NavLink>
                    ))}
                </nav>

                {/* Footer / Status */}
                <div className="p-4 border-t border-gray-800 text-xs space-y-3">
                    {/* Scenario A: UI Demo Mode (Autonomous) */}
                    {useAppStore.getState().isUiDemoMode ? (
                        <div className="flex flex-col space-y-2">
                            <div className="text-center bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-1.5 rounded font-bold uppercase tracking-wider text-[10px]">
                                Demo Mode (UI)
                            </div>
                            <div className="text-[10px] text-gray-500 text-center">
                                No server required
                            </div>
                        </div>
                    ) : (
                        /* Scenario B: Connected to Backend (Real or Mock) */
                        <>
                            <div className="flex items-center justify-between">
                                <span className="text-gray-500">System</span>
                                <div className="flex items-center space-x-2">
                                    <div className={clsx("w-2 h-2 rounded-full transition-colors duration-500",
                                        connectionStatus === 'connected' ? "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]" : "bg-red-500 animate-pulse"
                                    )} title="Core Connection" />
                                    <span className={clsx("text-[10px] font-medium transition-colors",
                                        connectionStatus === 'connected' ? "text-green-500" : "text-red-500"
                                    )}>
                                        {connectionStatus === 'connected' ? 'ONLINE' : 'OFFLINE'}
                                    </span>
                                </div>
                            </div>

                            <div className="flex items-center justify-between">
                                <span className="text-gray-500">Source</span>
                                <div className="flex items-center space-x-1">
                                    {/* TODO: Add proper broker provider from health check store if available */}
                                    <span className="text-[10px] font-mono text-gray-400">
                                        {isMockMode ? 'MOCK' : 'TBANK'}
                                    </span>
                                    {isMockMode && (
                                        <div className="w-1.5 h-1.5 rounded-full bg-yellow-500/50" title="Mock Data" />
                                    )}
                                </div>
                            </div>
                        </>
                    )}

                    <div className="text-[10px] text-gray-600 font-mono text-center pt-2 border-t border-gray-900">
                        Updated: {new Date().toLocaleTimeString()}
                    </div>

                    <div className="flex justify-between text-[9px] text-gray-700 mt-2 font-mono">
                        <span>v{import.meta.env.VITE_APP_VERSION || '1.1.0'}</span>
                        <span>{import.meta.env.VITE_COMMIT_HASH || 'dev'}</span>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto relative flex flex-col">
                {!useAppStore.getState().isUiDemoMode && (
                    <div className="absolute top-4 right-4 z-50">
                        <ConnectionStatus />
                    </div>
                )}
                <Outlet />
            </main>
            <Toaster position="top-right" theme="dark" />
        </div>
    );
};

export default Layout;
