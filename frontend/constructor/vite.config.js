import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Прототип конструктора. Порт 5173 — стандартный dev-порт Vite.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: false,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/healthchecks': 'http://127.0.0.1:8000',
    },
  },
})
