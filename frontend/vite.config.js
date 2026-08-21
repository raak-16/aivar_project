import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

import path from 'path'

export default defineConfig({
  plugins: [react()],
  base: '/react/',
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/socket.io': {
        target: 'http://127.0.0.1:5000',
        ws: true,
      },
      '/confirmations': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/reviews': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/audit': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/strategies': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, './index.html'),
      },
    },
    assetsDir: 'assets',
  },
})
