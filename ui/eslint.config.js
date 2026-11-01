import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';

const browserGlobals = {
  ...globals.browser,
};

export default tseslint.config(
  {
    ignores: [
      'dist',
      'coverage',
      'playwright-report',
      'test-results',
      '.eslintrc.cjs',
      '.stylelintrc.cjs',
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  reactHooks.configs.flat.recommended,
  reactRefresh.configs.vite,
  {
    // react-hooks/set-state-in-effect ships with eslint-plugin-react-hooks 7.1.1
    // (required for the eslint 10 toolchain that allows minimatch >= 11 for
    // GHSA-g3hv-75wg-m249). The 11 findings are pre-existing effect patterns
    // that predate this rule; adopting it is a separate code-change task.
    // Configured off 2026-11-01 to keep the enforced lint policy unchanged
    // through the security toolchain bump.
    rules: {
      'react-hooks/set-state-in-effect': 'off',
    },
  },
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: browserGlobals,
    },
    rules: {
      'react-refresh/only-export-components': [
        'error',
        { allowConstantExport: true, allowExportNames: ['useAuth', 'useTheme', 'useI18n'] },
      ],
    },
  },
  {
    files: ['playwright.config.ts', 'e2e/**/*.{ts,tsx}'],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
  },
  {
    files: ['src/components/ui/**/*.{ts,tsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    files: ['tests/mock-component-modules.tsx'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    files: [
      'tests/high-impact-pages-coverage.fixtures.tsx',
      'tests/mega-pages-branches.fixtures.tsx',
    ],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
);
