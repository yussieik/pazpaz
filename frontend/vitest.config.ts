import { fileURLToPath } from 'node:url'
import { mergeConfig, defineConfig, configDefaults } from 'vitest/config'
import { getViteConfig } from './vite.config'
import crypto from 'crypto'

// Polyfill for crypto.hash (Node.js 20.11 compatibility)
if (!crypto.hash) {
  // @ts-expect-error - Adding polyfill for missing crypto.hash in Node.js 20.11
  crypto.hash = (algorithm: string, data: string | Buffer, outputEncoding?: string) => {
    const hash = crypto.createHash(algorithm).update(data)
    return outputEncoding
      ? hash.digest(outputEncoding as BufferEncoding)
      : hash.digest()
  }
}

export default mergeConfig(
  getViteConfig('test'),
  defineConfig({
    test: {
      environment: 'happy-dom',
      exclude: [...configDefaults.exclude, 'e2e/**'],
      root: fileURLToPath(new URL('./', import.meta.url)),
      pool: 'forks',
      poolOptions: {
        forks: {
          isolate: true,
        },
      },
      coverage: {
        provider: 'v8',
        reporter: ['text', 'json', 'html'],
        exclude: [
          'node_modules/**',
          'src/api/schema.ts', // Generated file
          '**/*.config.ts',
          '**/*.config.js',
          '**/*.cjs',
          '**/*.d.ts',
          'src/main.ts',
          'src/router/**', // Router config
          'src/components/HelloWorld.vue', // Unused template component
          'coverage/**',
          'dist/**',
        ],
        thresholds: {
          lines: 85,
          functions: 85,
          branches: 80,
          statements: 85,
        },
      },
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
    },
  })
)
