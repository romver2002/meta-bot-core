import { defineConfig } from 'vitest/config'

export default defineConfig({
  base: './',
  build: {
    emptyOutDir: true,
  },
  server: {
    host: '127.0.0.1',
    port: 5174,
    strictPort: true,
    open: false,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  preview: {
    host: '127.0.0.1',
    port: 4174,
    strictPort: true,
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
    clearMocks: true,
    restoreMocks: true,
  },
})
