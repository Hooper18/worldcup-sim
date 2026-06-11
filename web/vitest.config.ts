// 独立于 vite.config.ts（沿用 ledger-app 惯例：避免构建插件在 jsdom 里的副作用）
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    globals: true,
  },
})
