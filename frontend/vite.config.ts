import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  build: {
    // CSP-Compatible Build Configuration
    // ===================================
    // Vite 5+ generates CSP-compatible production builds by default:
    // - No eval() or Function() constructor in production bundles
    // - Code-splitting chunks are loaded via <script src="..."> (external scripts)
    // - No inline scripts in generated HTML (all scripts are external files)
    //
    // External scripts are allowed by CSP via 'script-src 'self'' directive.
    // The nonce is only needed for inline scripts/styles, which Vite doesn't generate.
    //
    // Rollup Configuration:
    // - Manual chunks for better caching (vendor code separate from app code)
    // - This ensures browser can cache vendor.js independently of app code
    rollupOptions: {
      output: {
        // Separate vendor dependencies for optimal caching
        // Vendor bundle changes less frequently than app code
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
          ui: ['@fullcalendar/core', '@fullcalendar/vue3', '@vueuse/core'],
        },
      },
    },

    // Source maps for production debugging (do not expose source code)
    // Use 'hidden' to generate .map files without linking from JS
    // This allows error tracking without exposing source to users
    sourcemap: 'hidden',

    // Ensure build targets modern browsers that support ES modules
    // This allows for smaller bundles and better performance
    target: 'esnext',

    // Minification removes inline scripts and consolidates code
    minify: 'esbuild',

    // HIPAA Compliance: Remove console.debug statements in production builds
    // console.error and console.warn are preserved for error handling
    esbuild: {
      drop: ['console.debug'],
    },
  },
})
