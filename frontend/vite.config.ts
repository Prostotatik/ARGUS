import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// LIVE mode: /api -> FastAPI backend on :8000. REPLAY mode needs no backend (static /replay/*).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
