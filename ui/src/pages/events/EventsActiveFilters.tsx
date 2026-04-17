/**
 * Active filter chips rendered under the events filter bar. Extracted from
 * EventsPage.tsx so the top-level page stays below Lizard's NLOC / CCN limits.
 */

import type { ReactNode } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { format } from 'date-fns';
import type { Locale } from 'date-fns';
import { X } from 'lucide-react';
import { getEventCategoryLabel } from '@/lib/eventCategories';
import type { ResolvedLanguage } from '@/lib/language';
import type { EventsPageFilters } from './useEventsPageFilters';

type FilterKey = 'search' | 'category' | 'start_date' | 'city' | 'location';

export type EventsActiveFiltersProps = {
  filters: EventsPageFilters;
  hasActiveFilters: boolean;
  language: ResolvedLanguage;
  dateFnsLocale: Locale;
  labels: {
    activeFilters: string;
    filterSearch: string;
    filterFrom: string;
    filterCity: string;
    filterLocation: string;
    clearAll: string;
  };
  onUpdateFilter: (patch: Partial<EventsPageFilters>) => void;
  onClearAll: () => void;
};

/** Render the pill-list summary of every filter currently applied. */
export function EventsActiveFilters({
  filters,
  hasActiveFilters,
  language,
  dateFnsLocale,
  labels,
  onUpdateFilter,
  onClearAll,
}: EventsActiveFiltersProps) {
  if (!hasActiveFilters) {
    return null;
  }

  const clearPatches: Record<FilterKey, Partial<EventsPageFilters>> = {
    search: { search: '' },
    category: { category: '' },
    start_date: { start_date: '', end_date: '' },
    city: { city: '' },
    location: { location: '' },
  };

  function renderChip(key: FilterKey, label: ReactNode) {
    return (
      <Badge key={key} variant="secondary" className="gap-1">
        {label}
        <X
          className="h-3 w-3 cursor-pointer"
          onClick={() => onUpdateFilter(clearPatches[key])}
        />
      </Badge>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-muted-foreground">{labels.activeFilters}</span>
      {filters.search &&
        renderChip('search', `${labels.filterSearch}: ${filters.search}`)}
      {filters.category &&
        renderChip('category', getEventCategoryLabel(filters.category, language))}
      {filters.start_date &&
        renderChip(
          'start_date',
          `${labels.filterFrom}: ${format(new Date(filters.start_date), 'd MMM', {
            locale: dateFnsLocale,
          })}`,
        )}
      {filters.city && renderChip('city', `${labels.filterCity}: ${filters.city}`)}
      {filters.location &&
        renderChip('location', `${labels.filterLocation}: ${filters.location}`)}
      <Button variant="ghost" size="sm" onClick={onClearAll}>
        {labels.clearAll}
      </Button>
    </div>
  );
}
