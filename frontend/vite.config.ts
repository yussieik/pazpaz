import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv, type UserConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import type { Plugin } from 'vite'
import crypto from 'crypto'

// Polyfill for crypto.hash (Node.js 20.11 compatibility)
// The crypto.hash method was added in Node.js v21.7.0, but we're on v20.11
if (!crypto.hash) {
  // @ts-expect-error - Adding polyfill for missing crypto.hash in Node.js 20.11
  crypto.hash = (algorithm: string, data: string | Buffer, outputEncoding?: string) => {
    const hash = crypto.createHash(algorithm).update(data)
    return outputEncoding
      ? hash.digest(outputEncoding as crypto.BinaryToTextEncoding)
      : hash.digest()
  }
}

/**
 * HTML Transform Plugin for CSP Meta Tag
 * =======================================
 * Replaces placeholders in index.html with environment-specific values:
 * - %VITE_CSP_SCRIPT_SRC% → 'unsafe-eval' (dev) or '' (prod)
 * - %VITE_API_URL% → API endpoint URL for connect-src directive
 *
 * This allows CSP to adapt to development (Vite HMR needs eval) vs production (strict).
 */
function cspHtmlTransform(mode: string, env: Record<string, string>): Plugin {
  return {
    name: 'csp-html-transform',
    transformIndexHtml(html) {
      // Development: Allow 'unsafe-eval' for Vite HMR (Hot Module Replacement)
      // Production: Remove 'unsafe-eval' for strict CSP
      const scriptSrc = mode === 'development' ? "'unsafe-eval'" : ''

      // API URL for connect-src directive
      // Development: http://localhost:8000 (proxy handles /api → backend)
      // Production: https://api.pazpaz.com or configured URL
      const apiUrl = env.VITE_API_URL || 'http://localhost:8000'

      return html
        .replace(/%VITE_CSP_SCRIPT_SRC%/g, scriptSrc)
        .replace(/%VITE_API_URL%/g, apiUrl)
    },
  }
}

/**
 * Base Vite Configuration
 * ========================
 * Returns configuration object based on mode and environment variables.
 * Exported as factory function for use by vitest.config.ts
 */
export function getViteConfig(mode: string): UserConfig {
  // Load environment variables (VITE_* prefix)
  const env = loadEnv(mode, process.cwd(), 'VITE_')

  // Proxy target for API requests
  // Docker Compose: http://api:8000 (service name)
  // Native development: http://localhost:8000 (host machine)
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'
  const wsProxyTarget = apiProxyTarget.replace('http://', 'ws://')

  return {
    plugins: [vue(), cspHtmlTransform(mode, env)],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        '/ws': {
          target: wsProxyTarget,
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
    },

    // HIPAA Compliance: Remove console.debug statements in production builds
    // console.error and console.warn are preserved for error handling
    esbuild: {
      drop: ['debugger', 'console'],
      pure: ['console.debug'],
    },
  }
}

// https://vite.dev/config/
// Default export for Vite CLI (npm run dev, npm run build)
export default defineConfig(({ mode }) => getViteConfig(mode))
