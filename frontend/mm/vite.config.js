import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import packageJson from './package.json';
// https://vite.dev/config/
export default defineConfig({
    plugins: [react()],
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
});
