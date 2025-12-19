import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    chunkSizeWarningLimit: 750,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    css: true,
    include: ['tests/**/*.{test,spec}.?(c|m)[jt]s?(x)'],
    exclude: ['e2e/**', 'node_modules/**', 'dist/**', 'coverage/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary', 'lcov'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.d.ts', 'src/types/**', 'tests/**', '**/*.test.*', '**/*.spec.*'],
      thresholds: {
        lines: 5,
        functions: 5,
        branches: 2,
        statements: 5,
      },
    },
  },
})
