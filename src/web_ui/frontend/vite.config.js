import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5173,
    proxy: {
      // Dev server proxies /api to FastAPI so the frontend can be developed
      // with `npm run dev` while the backend runs separately on :8000.
      '/api': 'http://localhost:8000',
      '/ws':  { target: 'ws://localhost:8000', ws: true }
    }
  }
});
