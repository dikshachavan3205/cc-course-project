import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The FastAPI hub runs on :8000 (see data_backend/main.py). Proxy only the
// API paths so the frontend talks to a same-origin URL in dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/status': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/history': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/interruption': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
});