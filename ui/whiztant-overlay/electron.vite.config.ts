import { defineConfig, externalizeDepsPlugin } from 'electron-vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: {
        input: {
          index: path.resolve(__dirname, 'src/main/index.ts'),
        },
      },
    },
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: {
        input: {
          index: path.resolve(__dirname, 'src/preload/index.ts'),
        },
      },
    },
  },
  renderer: {
    root: path.resolve(__dirname, 'src/renderer'),
    build: {
      rollupOptions: {
        input: {
          pill: path.resolve(__dirname, 'src/renderer/pill/index.html'),
          overlay: path.resolve(__dirname, 'src/renderer/overlay/index.html'),
          settings: path.resolve(__dirname, 'src/renderer/settings/index.html'),
        },
      },
    },
    plugins: [react()],
  },
});
