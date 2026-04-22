import React from 'react';
import { render } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi } from 'vitest';

import { LanguageProvider } from '@/contexts/LanguageContext';
import { makeEvent } from './page-test-data';

/**
 * Renders the language route scaffolding for tests.
 */
export function renderLanguageRoute(path: string, routePath: string, element: React.ReactElement) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LanguageProvider>
        <Routes>
          <Route path={routePath} element={element} />
        </Routes>
      </LanguageProvider>
    </MemoryRouter>,
  );
}

/**
 * Returns the element value or fails loudly when absent.
 */
export function requireElement<T extends Element>(value: T | null | undefined, label: string): T {
  if (value == null) {
    throw new Error(`Expected ${label}`);
  }
  return value;
}

/**
 * Returns the input value or fails loudly when absent.
 */
export function requireInput(value: Element | null, label: string): HTMLInputElement {
  if (!(value instanceof HTMLInputElement)) {
    throw new TypeError(`Expected ${label}`);
  }
  return value;
}

/**
 * Installs a mutable value hook for tests.
 */
export function defineMutableValue<T extends object, V = undefined>(target: T, key: PropertyKey, value?: V): V | undefined {
  Object.defineProperty(target, key, {
    writable: true,
    configurable: true,
    value,
  });
  return value;
}

/**
 * Sets the english preference fixture state.
 */
export function setEnglishPreference() {
  localStorage.setItem('language_preference', 'en');
}

export interface MatchMediaMock {
  media: string;
  matches: boolean;
  addEventListener: ReturnType<typeof vi.fn>;
  removeEventListener: ReturnType<typeof vi.fn>;
  addListener: ReturnType<typeof vi.fn>;
  removeListener: ReturnType<typeof vi.fn>;
}

/**
 * Installs a matchMedia mock on globalThis and returns the stub so tests
 * can capture the registered change handler.
 */
export function mountMatchMediaMock(): MatchMediaMock {
  const mock: MatchMediaMock = {
    media: '(min-width: 640px)',
    matches: true,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
  };
  Object.defineProperty(globalThis, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn(() => mock),
  });
  return mock;
}

/**
 * Reads the change listener that a matchMedia consumer registered on the
 * mocked MediaQueryList. Callers use this to simulate viewport toggles.
 */
export function readMatchMediaChangeHandler(mock: MatchMediaMock) {
  const [, handler] = mock.addEventListener.mock.calls[0] as [
    string,
    (event: { matches: boolean }) => void,
  ];
  return handler;
}

/**
 * Awaits a microtask so any pending .catch() handlers attached to a
 * rejected promise get a chance to run before the test asserts.
 */
export async function flushMicrotasks() {
  await Promise.resolve();
}

/**
 * Canonical single-event list fixture used by tests that exercise the
 * events-page impression-tracking analytics path.
 */
export const SOLO_EVENT_PAGE = {
  items: [makeEvent(1, { title: 'Analytics Probe Event', seats_taken: 0, tags: [] })],
  total: 1,
  page: 1,
  page_size: 12,
  total_pages: 1,
} as const;
