import pluginVue from 'eslint-plugin-vue'
import vueTsEslintConfig from '@vue/eslint-config-typescript'
import js from '@eslint/js'

export default [
  {
    name: 'app/files-to-lint',
    files: ['**/*.{ts,mts,tsx,vue}'],
  },

  {
    name: 'app/files-to-ignore',
    ignores: [
      '**/dist/**',
      '**/dist-ssr/**',
      '**/coverage/**',
      'scripts/**',
      '*.config.js',
      '*.config.ts',
      '*.config.mjs',
      'node_modules/**',
    ],
  },

  js.configs.recommended,
  ...pluginVue.configs['flat/essential'],
  ...vueTsEslintConfig(),

  {
    name: 'app/rules',
    rules: {
      'vue/multi-word-component-names': 'off',
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
        },
      ],
      // HIPAA Compliance: Prevent console.log in production (may expose PHI)
      // Allow console.debug (stripped in production), console.error, console.warn
      'no-console': [
        'error',
        {
          allow: ['warn', 'error', 'debug'],
        },
      ],
    },
  },

  {
    name: 'app/test-rules',
    files: ['**/*.spec.ts', '**/*.spec.vue', '**/test/**/*.ts', '**/tests/**/*.ts'],
    rules: {
      // Allow 'any' in test files for mocking and test utilities
      '@typescript-eslint/no-explicit-any': 'off',
      // Allow all console methods in test files
      'no-console': 'off',
      // Allow unused variables in test files (common in test setup/teardown)
      '@typescript-eslint/no-unused-vars': 'off',
      // Allow empty interfaces in test files (type augmentation)
      '@typescript-eslint/no-empty-object-type': 'off',
      // Allow require() in test files (for dynamic imports and mocking)
      '@typescript-eslint/no-require-imports': 'off',
    },
  },
]
