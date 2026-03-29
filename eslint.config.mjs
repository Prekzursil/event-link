import { createRequire } from 'node:module';

const uiRequire = createRequire(new URL('./ui/package.json', import.meta.url));
const js = uiRequire('@eslint/js');
const globals = uiRequire('globals');
const reactHooks = uiRequire('eslint-plugin-react-hooks');
const reactRefresh = uiRequire('eslint-plugin-react-refresh');
const tseslint = uiRequire('typescript-eslint');
const importPlugin = uiRequire('eslint-plugin-import');

const uiFiles = ['ui/**/*.{ts,tsx}'];
const uiAutomationFiles = ['ui/playwright.config.ts', 'ui/e2e/**/*.{ts,tsx}'];
const uiGlobals = { ...globals.browser };
const uiAutomationGlobals = { ...globals.browser, ...globals.node };
const loadtestGlobals = { ...globals.node };

/** Scope a shared ESLint config object to one file glob set. */
const scopeConfig = (config, files) => ({
  ...config,
  files,
});

export default [
  {
    ignores: [
      'ui/dist/**',
      'ui/coverage/**',
      'ui/playwright-report/**',
      'ui/test-results/**',
      'coverage-100/**',
    ],
  },
  scopeConfig(js.configs.recommended, uiFiles),
  ...tseslint.configs.recommended.map((config) => scopeConfig(config, uiFiles)),
  scopeConfig(reactHooks.configs.flat.recommended, uiFiles),
  scopeConfig(reactRefresh.configs.vite, uiFiles),
  {
    files: uiFiles,
    plugins: {
      import: importPlugin,
    },
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: uiGlobals,
    },
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
    rules: {
      'react-refresh/only-export-components': [
        'error',
        { allowConstantExport: true, allowExportNames: ['useAuth', 'useTheme', 'useI18n'] },
      ],
    },
  },
  {
    files: uiAutomationFiles,
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: uiAutomationGlobals,
    },
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    files: ['loadtests/**/*.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: loadtestGlobals,
    },
    settings: {
      'import/core-modules': ['k6', 'k6/http'],
    },
  },
];
