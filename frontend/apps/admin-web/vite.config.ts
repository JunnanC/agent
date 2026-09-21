import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  build: { outDir: '../../dist/admin-web', emptyOutDir: true },
  server: {
    proxy: {
      '/api': { target: 'http://127.0.0.1:8080', changeOrigin: false },
      '/workspace': { target: 'ws://127.0.0.1:8080', ws: true, changeOrigin: false },
      '/files': { target: 'http://127.0.0.1:8080', changeOrigin: false },
    },
  },
})
