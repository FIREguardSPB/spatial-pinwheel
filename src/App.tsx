import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import DashboardPage from './features/dashboard/DashboardPage';
import SignalsPage from './features/signals/SignalsPage';
import SettingsPage from './features/settings/SettingsPage';
import ActivityPage from './features/activity/ActivityPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="signals" element={<SignalsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="activity" element={<ActivityPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
