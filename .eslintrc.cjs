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
  plugins: ['import'],
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
