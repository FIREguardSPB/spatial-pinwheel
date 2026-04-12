import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const proxyTarget = env.VITE_DEV_PROXY_TARGET || `http://127.0.0.1:${env.APP_PORT || '8001'}`;

  return {
    plugins: [react()],
    server: {
      watch: {
        ignored: [
          '**/backend/**',
          '**/__pycache__/**',
          '**/*.pyc',
          '**/*.pyo',
          '**/*.log',
          '**/*.sqlite',
          '**/*.sqlite3',
          '**/*.db',
          '**/tmp/**',
          '**/.pytest_cache/**',
        ],
      },
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          timeout: 0,
          proxyTimeout: 0,
          headers: {
            Connection: 'keep-alive',
          },
        },
      },
    },
  };
});
