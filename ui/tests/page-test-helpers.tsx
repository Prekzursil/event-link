import React from 'react';
import { render } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { LanguageProvider } from '@/contexts/LanguageContext';

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
