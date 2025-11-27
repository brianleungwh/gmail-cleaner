import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// https://vite.dev/config/
export default defineConfig({
  plugins: [svelte()],
  base: '/static/',
  build: {
    // Output to dist in Docker, or ../app/static for local builds
    outDir: process.env.DOCKER_BUILD === 'true' ? 'dist' : '../app/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/auth': 'http://localhost:8000',
      '/collect': 'http://localhost:8000',
      '/cleanup': 'http://localhost:8000',
      '/domains': 'http://localhost:8000',
      '/labels': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true
      }
    }
  }
})
