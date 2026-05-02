import tsParser from '@typescript-eslint/parser'
import tsPlugin from '@typescript-eslint/eslint-plugin'
import reactHooksPlugin from 'eslint-plugin-react-hooks'

export default [
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        project: './tsconfig.json',
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      'react-hooks': reactHooksPlugin,
    },
    rules: {
      ...tsPlugin.configs['recommended'].rules,
      ...reactHooksPlugin.configs.recommended.rules,
      // Relax rules that would generate noise without adding safety value
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      // react-hooks/set-state-in-effect fires on `void asyncFn()` patterns which are
      // correct async fetch-on-mount idioms. The rule misfires here because setState
      // is only called when the promise resolves, not synchronously in the effect body.
      'react-hooks/set-state-in-effect': 'off',
    },
  },
  {
    // Ignore generated files entirely (they have their own eslint-disable)
    ignores: ['src/contracts/generated/**'],
  },
]
