import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Vite serves the frontend locally and builds it for deployment.
export default defineConfig({
  plugins: [react()],
})
