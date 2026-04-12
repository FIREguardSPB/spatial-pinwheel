import ReactDOM from 'react-dom/client';
import { RootApp } from './RootApp';
import './index.css';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element #root not found');
}

const root = ReactDOM.createRoot(rootElement);
root.render(<RootApp />);
