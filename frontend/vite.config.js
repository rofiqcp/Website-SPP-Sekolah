import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'force-jsx-for-js',
      enforce: 'pre',
      transform(src, id) {
        if (!id.endsWith('.js')) return null;
        if (!/<[a-zA-Z]/.test(src) || !/>/.test(src)) return null;
        // Let @vitejs/plugin-react handle JSX in .js via its esbuild by
        // forcing a loader override. We do this by name-mapping to .jsx
        // so the react plugin's esbuild transform (_rollup.getJsxPragma)
        // kicks in with JSX enabled.
        const map = { code: src, map: null };
        return {
          code: src,
          map: null,
          meta: {
            vite: {
              loaderContext: undefined,
            },
          },
        };
      },
      handleHotUpdate({ file, server }) {
        // noop
      },
    },
  ],
  build: {
    rollupOptions: {
      external: [],
    },
  },
  resolve: {
    extensions: ['.js', '.jsx', '.json', '.ts', '.tsx'],
  },
  server: {
    host: '0.0.0.0',
    port: Number(process.env.VITE_FRONTEND_PORT || 5100),
    allowedHosts: ['sekolah.otomasi.app', 'localhost', '127.0.0.1'],
    proxy: {
      '/api': 'http://127.0.0.1:5101',
      '/health': 'http://127.0.0.1:5101',
    },
  },
});
