/// <reference types="vite-plugin-pwa/client" />
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { registerSW } from 'virtual:pwa-register'

// Automatically check for updates and reload when a new version is found
const updateSW = registerSW({
  onNeedRefresh() {
    // We can auto-update without asking, or we can prompt.
    // For a simple PWA, auto-updating on next load or immediate reload is usually fine.
    // We'll immediately activate the new service worker.
    updateSW(true)
  },
  onOfflineReady() {
    console.log('App ready to work offline')
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
