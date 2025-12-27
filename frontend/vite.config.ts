import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Only proxy API calls to Flask
      // All frontend routes (including /@username) are handled by Vite/React Router
      // OG tag injection only happens in production (Flask serving built assets)
      '/api': {
        target: 'http://localhost:5050',
        changeOrigin: true,
      },
    },
  },
})
