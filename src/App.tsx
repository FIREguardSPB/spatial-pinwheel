import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useEffect, type ReactNode } from 'react';
import Layout from './components/Layout';
import { ErrorBoundary } from './components/ErrorBoundary';
import { useAppStore } from './store/index';
import TokensPage from './features/tokens/TokensPage';
import DashboardPage from './features/dashboard/DashboardPage';
import SignalsPage from './features/signals/SignalsPage';
import SettingsPage from './features/settings/SettingsPage';
import ActivityPage from './features/activity/ActivityPage';
import TradesPage from './features/trades/TradesPage';
import AccountPage from './features/account/AccountPage';
import BacktestPage from './features/backtest/BacktestPage';

function RoutedBoundary({ name, children }: { name: string; children: ReactNode }) {
  const location = useLocation();
  return (
    <ErrorBoundary sectionName={name} resetKey={`${location.pathname}:${name}`}>
      {children}
    </ErrorBoundary>
  );
}

function App() {
  const theme = useAppStore((s) => s.theme);
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    document.documentElement.classList.toggle('light', theme === 'light');
  }, [theme]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<RoutedBoundary name="дашборде"><DashboardPage /></RoutedBoundary>} />
          <Route path="signals" element={<RoutedBoundary name="сигналах"><SignalsPage /></RoutedBoundary>} />
          <Route path="trades" element={<RoutedBoundary name="сделках"><TradesPage /></RoutedBoundary>} />
          <Route path="account" element={<RoutedBoundary name="счёте"><AccountPage /></RoutedBoundary>} />
          <Route path="backtest" element={<RoutedBoundary name="бэктесте"><BacktestPage /></RoutedBoundary>} />
          <Route path="activity" element={<RoutedBoundary name="журнале событий"><ActivityPage /></RoutedBoundary>} />
          <Route path="settings" element={<RoutedBoundary name="настройках"><SettingsPage /></RoutedBoundary>} />
          <Route path="tokens" element={<RoutedBoundary name="токенах"><TokensPage /></RoutedBoundary>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
