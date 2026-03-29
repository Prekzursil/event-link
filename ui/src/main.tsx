import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'tailwindcss/index.css'
import './index.css'
import App from './App.tsx'
import { applyThemePreference, getStoredThemePreference } from '@/lib/theme'

applyThemePreference(getStoredThemePreference())

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('Missing root element')
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
