import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

import { LanguageProvider } from '@/contexts/LanguageContext';
import { ForbiddenPage } from '@/pages/ForbiddenPage';
import { NotFoundPage } from '@/pages/NotFoundPage';

function renderWithProviders(node: React.ReactNode) {
  return render(
    <MemoryRouter>
      <LanguageProvider>{node}</LanguageProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
});

describe('simple pages', () => {
  it('renders ForbiddenPage with back link', () => {
    renderWithProviders(<ForbiddenPage />);
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    const back = screen.getByRole('link');
    expect(back).toHaveAttribute('href', '/');
  });

  it('renders NotFoundPage with back link', () => {
    renderWithProviders(<NotFoundPage />);
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    const back = screen.getByRole('link');
    expect(back).toHaveAttribute('href', '/');
  });
});
