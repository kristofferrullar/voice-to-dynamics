import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5173,
    proxy: {
      '/status':   { target: 'http://localhost:8080', changeOrigin: true },
      '/start':    { target: 'http://localhost:8080', changeOrigin: true },
      '/stop':     { target: 'http://localhost:8080', changeOrigin: true },
      '/pause':    { target: 'http://localhost:8080', changeOrigin: true },
      '/resume':   { target: 'http://localhost:8080', changeOrigin: true },
      '/language': { target: 'http://localhost:8080', changeOrigin: true },
      '/text':     { target: 'http://localhost:8080', changeOrigin: true },
      '/logs': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['x-accel-buffering'] = 'no';
          });
        }
      },
      '/config': { target: 'http://localhost:8080', changeOrigin: true },
      '/webhook': { target: 'http://localhost:8080', changeOrigin: true },
      '/api':     { target: 'http://localhost:8080', changeOrigin: true }
    }
  }
});
