import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect } from 'react';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import App from './App';
import { ErrorBoundary } from './components/ErrorBoundary';
import { streamService } from './services/stream';
import { useBackendRuntime } from './features/system/useBackendRuntime';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: false,
      staleTime: 5_000,
    },
  },
});


function AppBootstrap() {
  useBackendRuntime();

  useEffect(() => {
    streamService.setQueryClient(queryClient);
    streamService.connect();
    return () => {
      streamService.disconnect();
    };
  }, []);

  return <App />;
}

export function RootApp() {
  return (
    <ErrorBoundary sectionName="каркасе приложения" resetKey="root-app">
      <QueryClientProvider client={queryClient}>
        <AppBootstrap />
        {import.meta.env.DEV ? <ReactQueryDevtools initialIsOpen={false} /> : null}
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
