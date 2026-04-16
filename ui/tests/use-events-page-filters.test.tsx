import React from 'react';
import { act, renderHook } from '@testing-library/react';
import { MemoryRouter, useSearchParams } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import {
  EVENTS_PAGE_ALL_CATEGORIES_VALUE,
  useEventsPageFilters,
} from '@/pages/events/useEventsPageFilters';

/**
 * Builds a wrapper that yields both the hook API and the raw params the hook
 * writes back to the URL; needed because the hook depends on the router.
 */
const authState: {
  isAuthenticated: boolean;
  user: { role?: string } | null;
} = {
  isAuthenticated: false,
  user: null,
};

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => authState,
}));

/**
 * Joint hook that exercises useEventsPageFilters alongside useSearchParams
 * so tests can inspect the URL mutations produced by the filter helpers.
 */
function useHarness(initialRoute: string) {
  const [params] = useSearchParams();
  const api = useEventsPageFilters({
    dateRangePlaceholder: 'placeholder',
    dateFnsLocale: undefined as never,
  });
  return { api, params, initialRoute };
}

/**
 * Renders a hook inside a MemoryRouter using the given initial URL.
 */
function renderWithRouter(initialRoute: string) {
  return renderHook(() => useHarness(initialRoute), {
    wrapper: ({ children }) => (
      <MemoryRouter initialEntries={[initialRoute]}>{children}</MemoryRouter>
    ),
  });
}

describe('useEventsPageFilters', () => {
  beforeEach(() => {
    authState.isAuthenticated = false;
    authState.user = null;
  });

  it('returns default filters when no query parameters are present', () => {
    const { result } = renderWithRouter('/events');
    expect(result.current.api.filters).toMatchObject({
      search: '',
      category: '',
      tags: [],
      page: 1,
      page_size: 12,
      sort: 'time',
    });
    expect(result.current.api.hasActiveFilters).toBe(false);
    expect(result.current.api.dateRangeLabel).toBe('placeholder');
    expect(result.current.api.selectedDateRange.from).toBeUndefined();
    expect(result.current.api.selectedDateRange.to).toBeUndefined();
  });

  it('parses tags and honours explicit sort parameter', () => {
    const { result } = renderWithRouter(
      '/events?tags=ai,ml,&search=hello&category=Technical&page=2&page_size=24&sort=recommended',
    );
    expect(result.current.api.filters.tags).toEqual(['ai', 'ml']);
    expect(result.current.api.filters.sort).toBe('recommended');
    expect(result.current.api.filters.page).toBe(2);
    expect(result.current.api.filters.page_size).toBe(24);
    expect(result.current.api.hasActiveFilters).toBe(true);
  });

  it('falls back to recommended sort for authenticated students', () => {
    authState.isAuthenticated = true;
    authState.user = { role: 'student' };
    const { result } = renderWithRouter('/events');
    expect(result.current.api.filters.sort).toBe('recommended');
  });

  it('falls back to time sort for organizers/admins without explicit sort', () => {
    authState.isAuthenticated = true;
    authState.user = { role: 'organizer' };
    const { result } = renderWithRouter('/events');
    expect(result.current.api.filters.sort).toBe('time');
  });

  it('renders a single date label when only start_date is set', async () => {
    const { enUS } = await import('date-fns/locale/en-US');
    const { result } = renderHook(
      () =>
        useEventsPageFilters({
          dateRangePlaceholder: 'placeholder',
          dateFnsLocale: enUS,
        }),
      {
        wrapper: ({ children }) => (
          <MemoryRouter initialEntries={['/events?start_date=2030-05-01']}>{children}</MemoryRouter>
        ),
      },
    );
    expect(result.current.dateRangeLabel).toContain('2030');
    expect(result.current.selectedDateRange.from).toBeInstanceOf(Date);
  });

  it('renders a range label when both dates are set', async () => {
    const { enUS } = await import('date-fns/locale/en-US');
    const { result } = renderHook(
      () =>
        useEventsPageFilters({
          dateRangePlaceholder: 'placeholder',
          dateFnsLocale: enUS,
        }),
      {
        wrapper: ({ children }) => (
          <MemoryRouter
            initialEntries={['/events?start_date=2030-05-01&end_date=2030-05-10']}
          >
            {children}
          </MemoryRouter>
        ),
      },
    );
    expect(result.current.dateRangeLabel).toMatch(/-/);
  });

  it('updateFilters clears empty values and resets the page', () => {
    const { result } = renderWithRouter('/events?search=old&page=3');
    act(() => {
      result.current.api.updateFilters({ search: '' });
    });
    expect(result.current.api.filters.search).toBe('');
    expect(result.current.api.filters.page).toBe(1);
  });

  it('handleCategoryChange maps the all-categories sentinel to an empty string', () => {
    const { result } = renderWithRouter('/events?category=Technical');
    act(() => {
      result.current.api.handleCategoryChange(EVENTS_PAGE_ALL_CATEGORIES_VALUE);
    });
    expect(result.current.api.filters.category).toBe('');
  });

  it('handleCategoryChange sets a concrete category', () => {
    const { result } = renderWithRouter('/events');
    act(() => {
      result.current.api.handleCategoryChange('Music');
    });
    expect(result.current.api.filters.category).toBe('Music');
  });

  it('clearFilters wipes the URL state', () => {
    const { result } = renderWithRouter('/events?search=hello&category=Technical&page=5');
    act(() => {
      result.current.api.clearFilters();
    });
    expect(result.current.api.filters.search).toBe('');
    expect(result.current.api.filters.category).toBe('');
    expect(result.current.api.filters.page).toBe(1);
  });
});
