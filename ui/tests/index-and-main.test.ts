import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('main entry bootstrap', () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, 'matchMedia', {
      writable: true,
      configurable: true,
      value: vi.fn().mockImplementation(() => ({
        matches: true,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
      })),
    });
  });

  it(
    'covers main.tsx bootstrap',
    async () => {
      vi.resetModules();

      document.body.innerHTML = '<div id="root"></div>';

      const renderSpy = vi.fn();
      const createRootSpy = vi.fn(() => ({ render: renderSpy }));
      const applyThemePreferenceSpy = vi.fn();
      const getStoredThemePreferenceSpy = vi.fn(() => 'dark');

      vi.doMock('react-dom/client', () => ({
        createRoot: createRootSpy,
      }));

      vi.doMock('@/lib/theme', () => ({
        applyThemePreference: applyThemePreferenceSpy,
        getStoredThemePreference: getStoredThemePreferenceSpy,
      }));

      vi.doMock('../src/App.tsx', () => ({
        default: () => null,
      }));

      vi.doMock('../src/index.css', () => ({}));

      await import('../src/main.tsx');

      expect(getStoredThemePreferenceSpy).toHaveBeenCalledTimes(1);
      expect(applyThemePreferenceSpy).toHaveBeenCalledWith('dark');
      expect(createRootSpy).toHaveBeenCalledTimes(1);
      expect(renderSpy).toHaveBeenCalledTimes(1);
    },
    30000,
  );
});
