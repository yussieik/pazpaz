import { fileURLToPath } from 'node:url'
import { mergeConfig, defineConfig, configDefaults } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'happy-dom',
      exclude: [...configDefaults.exclude, 'e2e/**'],
      root: fileURLToPath(new URL('./', import.meta.url)),
      pool: 'forks',
      poolOptions: {
        forks: {
          singleFork: true,
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
