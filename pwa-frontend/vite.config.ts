import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import { demoPlugin } from './dev/demo-plugin'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    proxy: mode === 'demo' ? undefined : { '/api': 'http://127.0.0.1:8000' },
  },
  preview: {
    proxy: mode === 'demo' ? undefined : { '/api': 'http://127.0.0.1:8000' },
  },
  plugins: [
    ...(mode === 'demo' ? [demoPlugin()] : []),
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        id: '/',
        start_url: '/',
        scope: '/',
        name: 'Codeforces Picker',
        short_name: 'CF Picker',
        description: 'Anti-doomscrolling Codeforces problem picker',
        theme_color: '#0f172a',
        background_color: '#0f172a',
        display: 'standalone',
        icons: [
          {
            src: '/pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png'
          },
          {
            src: '/pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable',
          }
        ]
      },
      workbox: {
        // API errors/offline requests must not receive the app's HTML shell.
        navigateFallbackDenylist: [/^\/api\//],
      },
    })
  ],
}))
