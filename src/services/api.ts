import axios from 'axios';
import { useAppStore } from '../store';
import { toast } from 'sonner';

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const apiClient = axios.create({
    baseURL: BASE_URL,
    timeout: 15000,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor to add Auth Token
apiClient.interceptors.request.use(
    (config) => {
        const token = useAppStore.getState().authToken;
        if (token) {
            config.headers = config.headers ?? {};
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        // Optional: Handle 401 Unauthorized globally
        if (error.response?.status === 401) {
            console.warn('Unauthorized access');
            toast.error('Unauthorized: Please check your token');
        } else {
            const payloadMessage = typeof error.response?.data === 'object'
                ? error.response?.data?.message || error.response?.data?.detail
                : undefined;
            const msg = payloadMessage || error.message || 'API Error';
            toast.error(String(msg));
        }
        return Promise.reject(error);
    }
);
