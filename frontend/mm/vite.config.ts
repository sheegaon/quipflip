import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import packageJson from './package.json'

const projectRoot = fileURLToPath(new URL('.', import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(projectRoot, 'src'),
      '@crowdcraft': resolve(projectRoot, '../crowdcraft/src'),
    },
  },
  define: {
    __APP_VERSION__: JSON.stringify(packageJson.version),
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Remove the incorrect rewrite that was changing /api to /qf
        // MM API endpoints start with /mm, so /api/mm/* should proxy to /mm/*
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
