import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useEffect } from 'react';
import Layout from './components/Layout';
import { useAppStore } from './store/index';
import TokensPage from './features/tokens/TokensPage';
import DashboardPage from './features/dashboard/DashboardPage';
import SignalsPage    from './features/signals/SignalsPage';
import SettingsPage   from './features/settings/SettingsPage';
import ActivityPage   from './features/activity/ActivityPage';
import TradesPage     from './features/trades/TradesPage';
import AccountPage    from './features/account/AccountPage';
import BacktestPage   from './features/backtest/BacktestPage';

function App() {
  const theme = useAppStore(s => s.theme);
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    document.documentElement.classList.toggle('light', theme === 'light');
  }, [theme]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index             element={<DashboardPage />} />
          <Route path="signals"   element={<SignalsPage />}   />
          <Route path="trades"    element={<TradesPage />}    />
          <Route path="account"   element={<AccountPage />}   />
          <Route path="backtest"  element={<BacktestPage />}  />
          <Route path="activity"  element={<ActivityPage />}  />
          <Route path="settings"  element={<SettingsPage />}  />
          <Route path="tokens"    element={<TokensPage />}    />
          <Route path="*"         element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
