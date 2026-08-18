/// <reference types="vitest/config" />

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/vitest-setup.ts'],
    globals: true,
    // The first case in a file pays for transforming the whole app graph, and
    // v8 instrumentation makes that slower still; the 5s default sits close
    // enough to the real cost to fail at random under `--coverage`.
    testTimeout: 20000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/test/**', 'src/**/*.d.ts', 'src/main.tsx', 'src/vite-env.d.ts'],
      // A ratchet, not an aspiration: set just under what the suite covers
      // today, so a change that drops coverage fails here rather than quietly
      // eroding it. Raise these as coverage grows.
      thresholds: {
        statements: 84,
        branches: 69,
        functions: 83,
        lines: 85,
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:3001',
        changeOrigin: true,
      },
    },
  },
})
