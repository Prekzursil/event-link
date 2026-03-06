module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
    node: true,
  },
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    ecmaFeatures: {
      jsx: true,
    },
  },
  plugins: ['import', 'n', 'es-x', 'flowtype'],
  rules: {
    // Codacy still exposes a legacy ESLint analyzer on this repo. Keep it aligned with
    // the actual TypeScript/React toolchain instead of defaulting to ES5/Flow-era rules.
    'es-x/no-modules': 'off',
    'es-x/no-block-scoped-variables': 'off',
    'es-x/no-trailing-commas': 'off',
    'flowtype/require-parameter-type': 'off',
    'import/no-unresolved': 'off',
    'n/no-missing-import': 'off',
  },
  ignorePatterns: [
    '**/node_modules/**',
    '**/dist/**',
    '**/coverage/**',
    '**/playwright-report/**',
    '**/test-results/**',
    '**/eslint.config.*',
    'coverage-100/**',
  ],
  overrides: [
    {
      files: ['ui/**/*.{js,jsx,ts,tsx}'],
      settings: {
        'import/resolver': {
          typescript: {
            project: './ui/tsconfig.app.json',
          },
          node: {
            extensions: ['.js', '.jsx', '.ts', '.tsx'],
          },
        },
      },
    },
    {
      files: ['loadtests/**/*.js'],
      settings: {
        'import/core-modules': ['k6', 'k6/http'],
      },
    },
  ],
}
