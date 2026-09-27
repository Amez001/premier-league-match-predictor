import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // In dev, FastAPI runs separately (uvicorn api.main:app --reload --port 8000).
    // In "prod" locally, FastAPI serves the built frontend/dist/ itself, so
    // this proxy is dev-only and has no effect on the built app.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
