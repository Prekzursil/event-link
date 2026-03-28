import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import {
  Footer,
  LanguageProvider,
  Layout,
  ThemeProvider,
  Toast,
  ToastAction,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
  Toaster,
  getLayoutUiFixtures,
} from './layout-and-ui-smoke.shared';

const { toastState } = getLayoutUiFixtures();

describe('layout and toast smoke', () => {
  it('renders the footer and layout index exports', () => {
    render(
      <MemoryRouter>
        <LanguageProvider>
          <Footer />
        </LanguageProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText(/All rights reserved/i)).toBeInTheDocument();

    render(
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider>
          <LanguageProvider>
            <Routes>
              <Route path="/" element={<Layout />}>
                <Route index element={<div>Outlet Content</div>} />
              </Route>
            </Routes>
          </LanguageProvider>
        </ThemeProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText('Outlet Content')).toBeInTheDocument();
  });

  it('renders the toast primitives and toaster list mapping', () => {
    toastState.toasts = [
      {
        id: '1',
        open: true,
        title: 'Toast title',
        description: 'Toast description',
        variant: 'default',
      },
    ];

    render(
      <ToastProvider>
        <Toast open>
          <div>
            <ToastTitle>Primitive title</ToastTitle>
            <ToastDescription>Primitive description</ToastDescription>
          </div>
          <ToastAction altText="action">Action</ToastAction>
          <ToastClose />
        </Toast>
        <ToastViewport />
      </ToastProvider>,
    );

    expect(screen.getByText('Primitive title')).toBeInTheDocument();
    expect(screen.getByText('Primitive description')).toBeInTheDocument();

    render(<Toaster />);
    expect(screen.getByText('Toast title')).toBeInTheDocument();
  });
});
