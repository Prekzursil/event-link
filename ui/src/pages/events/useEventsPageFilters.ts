import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { format } from 'date-fns';
import type { EventFilters } from '@/types';
import type { Locale } from 'date-fns';
import { useAuth } from '@/contexts/AuthContext';
import { useI18n } from '@/contexts/LanguageContext';

const ALL_CATEGORIES_VALUE = '__all__';
export const EVENTS_PAGE_RECOMMENDATIONS_ENABLED =
  (import.meta.env.VITE_FEATURE_RECOMMENDATIONS ?? 'true').toLowerCase() !== 'false';
const RECOMMENDATIONS_ENABLED = EVENTS_PAGE_RECOMMENDATIONS_ENABLED;

export type EventsPageFilters = EventFilters & {
  tags: string[];
  page: number;
  page_size: number;
  sort: NonNullable<EventFilters['sort']>;
};

export type EventsPageFiltersApi = {
  filters: EventsPageFilters;
  hasActiveFilters: boolean;
  dateRangeLabel: string;
  selectedDateRange: { from: Date | undefined; to: Date | undefined };
  defaultCalendarMonth: Date;
  updateFilters: (next: Partial<EventFilters>) => void;
  handleCategoryChange: (value: string) => void;
  clearFilters: () => void;
};

/** Parses a query-string date into a local midnight Date for calendar rendering. */
function parseQueryDate(value: string | undefined): Date | undefined {
  return value ? new Date(`${value}T00:00:00`) : undefined;
}

/** Normalizes the sort query parameter to one of the two supported sort modes. */
function resolveSort(
  sortParam: string,
  isAuthenticated: boolean,
  role: string | undefined,
): EventsPageFilters['sort'] {
  if (sortParam === 'recommended' || sortParam === 'time') {
    return sortParam;
  }
  return isAuthenticated && role === 'student' && RECOMMENDATIONS_ENABLED
    ? 'recommended'
    : 'time';
}

/** Derives filter inputs from the search parameters using simple fallbacks. */
function readScalarFilters(searchParams: URLSearchParams) {
  return {
    search: searchParams.get('search') || '',
    category: searchParams.get('category') || '',
    start_date: searchParams.get('start_date') || '',
    end_date: searchParams.get('end_date') || '',
    city: searchParams.get('city') || '',
    location: searchParams.get('location') || '',
    tagsParam: searchParams.get('tags') || '',
    sortParam: searchParams.get('sort') || '',
    page: Number.parseInt(searchParams.get('page') || '1', 10),
    page_size: Number.parseInt(searchParams.get('page_size') || '12', 10),
  };
}

/** Renders the date-range chip label using the caller-provided localization strings. */
function computeDateRangeLabel(
  filters: EventsPageFilters,
  placeholder: string,
  locale: Locale,
): string {
  if (!filters.start_date) {
    return placeholder;
  }
  if (!filters.end_date) {
    return format(new Date(filters.start_date), 'd MMM yyyy', { locale });
  }
  const startLabel = format(new Date(filters.start_date), 'd MMM', { locale });
  const endLabel = format(new Date(filters.end_date), 'd MMM', { locale });
  return `${startLabel} - ${endLabel}`;
}

type UseFiltersOptions = {
  dateRangePlaceholder: string;
  dateFnsLocale: Locale;
};

/**
 * Consolidates EventsPage filter state:
 * reads URL params, computes the default sort mode, memoises the filters
 * object, and exposes helpers to update params or swap the synthetic
 * all-categories selector value back to the query-string form.
 */
export function useEventsPageFilters(options: UseFiltersOptions): EventsPageFiltersApi {
  const { dateRangePlaceholder, dateFnsLocale } = options;
  const [searchParams, setSearchParams] = useSearchParams();
  const { isAuthenticated, user } = useAuth();

  const scalars = readScalarFilters(searchParams);
  const sort = resolveSort(scalars.sortParam, isAuthenticated, user?.role);

  const filters = useMemo<EventsPageFilters>(
    () => ({
      search: scalars.search,
      category: scalars.category,
      start_date: scalars.start_date,
      end_date: scalars.end_date,
      city: scalars.city,
      location: scalars.location,
      tags: scalars.tagsParam ? scalars.tagsParam.split(',').filter(Boolean) : [],
      sort,
      page: scalars.page,
      page_size: scalars.page_size,
    }),
    [
      scalars.search,
      scalars.category,
      scalars.start_date,
      scalars.end_date,
      scalars.city,
      scalars.location,
      scalars.tagsParam,
      sort,
      scalars.page,
      scalars.page_size,
    ],
  );

  const dateRangeLabel = useMemo(
    () => computeDateRangeLabel(filters, dateRangePlaceholder, dateFnsLocale),
    [filters, dateRangePlaceholder, dateFnsLocale],
  );

  const hasActiveFilters = Boolean(
    filters.search ||
      filters.category ||
      filters.start_date ||
      filters.end_date ||
      filters.city ||
      filters.location ||
      filters.tags.length > 0,
  );
  const selectedDateRange = {
    from: parseQueryDate(filters.start_date),
    to: parseQueryDate(filters.end_date),
  };
  const defaultCalendarMonth = parseQueryDate(filters.start_date) ?? new Date();

  const updateFilters = useCallback(
    (next: Partial<EventFilters>) => {
      const params = new URLSearchParams(searchParams);
      Object.entries(next).forEach(([key, value]) => {
        if (value === '' || value === null || value === undefined) {
          params.delete(key);
          return;
        }
        params.set(key, String(value));
      });
      if (!('page' in next)) {
        params.set('page', '1');
      }
      setSearchParams(params);
    },
    [searchParams, setSearchParams],
  );

  const handleCategoryChange = useCallback(
    (value: string) => {
      updateFilters({ category: value === ALL_CATEGORIES_VALUE ? '' : value });
    },
    [updateFilters],
  );

  const clearFilters = useCallback(() => setSearchParams({}), [setSearchParams]);

  return {
    filters,
    hasActiveFilters,
    dateRangeLabel,
    selectedDateRange,
    defaultCalendarMonth,
    updateFilters,
    handleCategoryChange,
    clearFilters,
  };
}

export const EVENTS_PAGE_ALL_CATEGORIES_VALUE = ALL_CATEGORIES_VALUE;
