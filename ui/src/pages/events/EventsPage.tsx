import { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import eventService from '@/services/event.service';
import { recordInteractions, type InteractionEventIn } from '@/services/analytics.service';
import type { Event, EventFilters } from '@/types';
import { EventCard } from '@/components/events/EventCard';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Calendar } from '@/components/ui/calendar';
import { Badge } from '@/components/ui/badge';
import { LoadingPage } from '@/components/ui/loading';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { useI18n } from '@/contexts/LanguageContext';
import {
  Search,
  Filter,
  CalendarIcon,
  X,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import { format } from 'date-fns';
import { getDateFnsLocale } from '@/lib/language';
import { EVENT_CATEGORIES, getEventCategoryLabel } from '@/lib/eventCategories';

const PAGE_SIZES = [6, 12, 24, 48];
const ALL_CATEGORIES_VALUE = '__all__';
const ignoreInteractionError = () => undefined;

const RECOMMENDATIONS_ENABLED =
  (import.meta.env.VITE_FEATURE_RECOMMENDATIONS ?? 'true').toLowerCase() !== 'false';
const CALENDAR_MEDIA_QUERY = '(min-width: 640px)';

function readShowTwoMonthsCalendar() {
  return globalThis.window?.matchMedia?.(CALENDAR_MEDIA_QUERY).matches ?? true;
}

export function EventsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [events, setEvents] = useState<Event[]>([]);
  const [recommendations, setRecommendations] = useState<Event[]>([]);
  const [favorites, setFavorites] = useState<Set<number>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [totalPages, setTotalPages] = useState(1);
  const [totalEvents, setTotalEvents] = useState(0);
  const [showTwoMonthsCalendar, setShowTwoMonthsCalendar] = useState(readShowTwoMonthsCalendar);
  const { toast } = useToast();
  const { isAuthenticated, user } = useAuth();
  const { language, t } = useI18n();

  const dateFnsLocale = useMemo(() => getDateFnsLocale(language), [language]);

  useEffect(() => {
    const media = globalThis.window?.matchMedia?.(CALENDAR_MEDIA_QUERY);
    if (
      !media ||
      typeof media.addEventListener !== 'function' ||
      typeof media.removeEventListener !== 'function'
    ) {
      return;
    }

    const handler = (e: MediaQueryListEvent) => setShowTwoMonthsCalendar(e.matches);
    media.addEventListener('change', handler);
    return () => media.removeEventListener('change', handler);
  }, []);

  const categoryOptions = useMemo(
    () => [
      { value: ALL_CATEGORIES_VALUE, label: t.events.allCategories },
      ...EVENT_CATEGORIES.map((cat) => ({
        value: cat,
        label: getEventCategoryLabel(cat, language),
      })),
    ],
    [language, t],
  );

  // Memoize filters to prevent infinite loops
  const search = searchParams.get('search') || '';
  const category = searchParams.get('category') || '';
  const start_date = searchParams.get('start_date') || '';
  const end_date = searchParams.get('end_date') || '';
  const city = searchParams.get('city') || '';
  const location = searchParams.get('location') || '';
  const tagsParam = searchParams.get('tags') || '';
  const sortParam = searchParams.get('sort') || '';
  const page = Number.parseInt(searchParams.get('page') || '1', 10);
  const page_size = Number.parseInt(searchParams.get('page_size') || '12', 10);
  const defaultSort: EventFilters['sort'] =
    isAuthenticated && user?.role === 'student' && RECOMMENDATIONS_ENABLED
      ? 'recommended'
      : 'time';
  const sort: EventFilters['sort'] =
    sortParam === 'recommended' || sortParam === 'time' ? sortParam : defaultSort;

  const filters = useMemo(
    () => ({
      search,
      category,
      start_date,
      end_date,
      city,
      location,
      tags: tagsParam ? tagsParam.split(',').filter(Boolean) : [],
      sort,
      page,
      page_size,
    }),
    [search, category, start_date, end_date, city, location, tagsParam, sort, page, page_size],
  );
  const dateRangeLabel = useMemo(() => {
    if (!filters.start_date) {
      return t.events.dateRangePlaceholder;
    }
    if (!filters.end_date) {
      return format(new Date(filters.start_date), 'd MMM yyyy', { locale: dateFnsLocale });
    }
    const startLabel = format(new Date(filters.start_date), 'd MMM', { locale: dateFnsLocale });
    const endLabel = format(new Date(filters.end_date), 'd MMM', { locale: dateFnsLocale });
    return `${startLabel} - ${endLabel}`;
  }, [dateFnsLocale, filters.end_date, filters.start_date, t.events.dateRangePlaceholder]);

  const hasActiveFilters =
    filters.search ||
    filters.category ||
    filters.start_date ||
    filters.end_date ||
    filters.city ||
    filters.location ||
    filters.tags.length > 0;
  const handleCategoryChange = (value: string) => {
    updateFilters({ category: value === ALL_CATEGORIES_VALUE ? '' : value });
  };

  const updateFilters = useCallback(
    (newFilters: Partial<EventFilters>) => {
      const params = new URLSearchParams(searchParams);

      Object.entries(newFilters).forEach(([key, value]) => {
        if (value === '' || value === null) {
          params.delete(key);
          return;
        }
        params.set(key, String(value));
      });

      // Reset to page 1 when filters change (except for page changes)
      if (!('page' in newFilters)) {
        params.set('page', '1');
      }

      setSearchParams(params);
    },
    [searchParams, setSearchParams]
  );

  useEffect(() => {
    let cancelled = false;
    
    const loadEvents = async () => {
      setIsLoading(true);
      try {
        const response = await eventService.getEvents(filters);
        if (!cancelled) {
          setEvents(response.items);
          setTotalEvents(response.total);
          setTotalPages(Math.ceil(response.total / filters.page_size));
        }
      } catch {
        if (!cancelled) {
          toast({
            title: t.events.loadErrorTitle,
            description: t.events.loadErrorDescription,
            variant: 'destructive',
          });
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    loadEvents();
    
    return () => {
      cancelled = true;
    };
  }, [filters, toast, t]);

  useEffect(() => {
    if (!events.length) return;
    const timer = globalThis.setTimeout(() => {
      const interactions: InteractionEventIn[] = events.map((event, index) => ({
        interaction_type: 'impression',
        event_id: event.id,
          meta: {
            source: 'events_list',
            position: index,
            page: filters.page,
            sort: filters.sort,
          },
        }));

      if (filters.page === 1 && hasActiveFilters) {
          if (filters.search) {
            interactions.unshift({
              interaction_type: 'search',
              meta: {
                query: filters.search,
                category: filters.category || undefined,
                city: filters.city || undefined,
                location: filters.location || undefined,
                tags: filters.tags.slice(0, 10),
                sort: filters.sort,
              },
            });
          } else {
          interactions.unshift({
            interaction_type: 'filter',
              meta: {
                category: filters.category || undefined,
                city: filters.city || undefined,
                location: filters.location || undefined,
                tags: filters.tags.slice(0, 10),
                start_date: filters.start_date || undefined,
                end_date: filters.end_date || undefined,
                sort: filters.sort,
              },
            });
          }
      }

      void recordInteractions(interactions);
    }, 400);
    return () => globalThis.clearTimeout(timer);
  }, [events, filters, hasActiveFilters]);

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'student' || !RECOMMENDATIONS_ENABLED) return;
    
    const loadRecommendations = async () => {
      try {
        const response = await eventService.getEvents({ page: 1, page_size: 4, sort: 'recommended' });
        setRecommendations(response.items);
      } catch {
        // Silent fail for recommendations
      }
    };

    const loadFavorites = async () => {
      try {
        const response = await eventService.getFavorites();
        setFavorites(new Set(response.items.map((e) => e.id)));
      } catch {
        // Silent fail
      }
    };

    loadRecommendations();
    loadFavorites();
  }, [isAuthenticated, user?.role]);

  const handleFavoriteToggle = async (eventId: number, shouldFavorite: boolean) => {
    if (!isAuthenticated) {
      toast({
        title: t.events.loginRequiredTitle,
        description: t.events.loginRequiredDescription,
        variant: 'destructive',
      });
      return;
    }

    try {
      if (shouldFavorite) {
        await eventService.addToFavorites(eventId);
        setFavorites((prev) => new Set([...prev, eventId]));
      } else {
        await eventService.removeFromFavorites(eventId);
        setFavorites((prev) => {
          const newSet = new Set(prev);
          newSet.delete(eventId);
          return newSet;
        });
      }
    } catch {
      toast({
        title: t.events.favoritesUpdateErrorTitle,
        description: t.events.favoritesUpdateErrorDescription,
        variant: 'destructive',
      });
    }
  };

  const renderEventsGrid = () => (
    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {events.map((event) => (
        <EventCard
          key={event.id}
          event={event}
          onFavoriteToggle={handleFavoriteToggle}
          isFavorite={favorites.has(event.id)}
          showRecommendation={filters.sort === 'recommended'}
          onEventClick={(eventId) => {
            Promise.resolve(
              recordInteractions([
                {
                  interaction_type: 'click',
                  event_id: eventId,
                  meta: { source: 'events_list', sort: filters.sort, page: filters.page },
                },
              ]),
            ).catch(ignoreInteractionError);
          }}
        />
      ))}
    </div>
  );

  const renderEmptyState = () => (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Filter className="mb-4 h-12 w-12 text-muted-foreground" />
      <h3 className="text-lg font-semibold">{t.events.noResultsTitle}</h3>
      <p className="mt-2 text-muted-foreground">
        {t.events.noResultsDescription}
      </p>
      {hasActiveFilters && (
        <Button variant="outline" className="mt-4" onClick={clearFilters}>
          {t.events.clearFilters}
        </Button>
      )}
    </div>
  );

  const clearFilters = () => {
    setSearchParams({});
  };

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold">{t.events.title}</h1>
        <p className="mt-2 text-muted-foreground">
          {t.events.subtitle}
        </p>
      </div>

      {/* Recommendations Section */}
      {RECOMMENDATIONS_ENABLED &&
        isAuthenticated &&
        user?.role === 'student' &&
        recommendations.length > 0 &&
        !hasActiveFilters &&
        filters.sort !== 'recommended' && (
        <div className="mb-8">
          <div className="mb-4 flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <h2 className="text-xl font-semibold">{t.events.recommendationsTitle}</h2>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {recommendations.map((event) => (
              <EventCard
                key={event.id}
                event={event}
                onFavoriteToggle={handleFavoriteToggle}
                isFavorite={favorites.has(event.id)}
                showRecommendation
                onEventClick={(eventId) =>
                  void recordInteractions([
                    { interaction_type: 'click', event_id: eventId, meta: { source: 'recommendations_grid' } },
                  ])
                }
              />
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="mb-6 space-y-4">
        <div className="flex flex-wrap gap-4">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder={t.events.searchPlaceholder}
              value={filters.search || ''}
              onChange={(e) => updateFilters({ search: e.target.value })}
              className="pl-10"
            />
          </div>

          {/* Category */}
          <Select
            value={filters.category || ALL_CATEGORIES_VALUE}
            onValueChange={handleCategoryChange}
          >
            <SelectTrigger className="w-full sm:w-[180px]">
              <SelectValue placeholder={t.events.categoryPlaceholder} />
            </SelectTrigger>
            <SelectContent>
              {categoryOptions.map((cat) => (
                <SelectItem key={cat.value} value={cat.value}>
                  {cat.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Date Range */}
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" className="w-full justify-start sm:w-[240px]">
                <CalendarIcon className="mr-2 h-4 w-4" />
                {dateRangeLabel}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="start">
              <Calendar
                mode="range"
                selected={{
                  from: filters.start_date ? new Date(filters.start_date + 'T00:00:00') : undefined,
                  to: filters.end_date ? new Date(filters.end_date + 'T00:00:00') : undefined,
                }}
                onSelect={(range: { from?: Date; to?: Date } | undefined) => {
                  // Format date as YYYY-MM-DD without timezone conversion
                  const formatLocalDate = (date: Date | undefined) => {
                    if (!date) return '';
                    const year = date.getFullYear();
                    const month = String(date.getMonth() + 1).padStart(2, '0');
                    const day = String(date.getDate()).padStart(2, '0');
                    return `${year}-${month}-${day}`;
                  };
                  updateFilters({
                    start_date: formatLocalDate(range?.from),
                    end_date: formatLocalDate(range?.to),
                  });
                }}
                numberOfMonths={showTwoMonthsCalendar ? 2 : 1}
                defaultMonth={filters.start_date ? new Date(filters.start_date + 'T00:00:00') : new Date()}
                locale={dateFnsLocale}
              />
            </PopoverContent>
          </Popover>

          {/* Location */}
          <Input
            placeholder={t.events.cityPlaceholder}
            value={filters.city || ''}
            onChange={(e) => updateFilters({ city: e.target.value })}
            className="w-full sm:w-[180px]"
          />

          <Input
            placeholder={t.events.locationPlaceholder}
            value={filters.location || ''}
            onChange={(e) => updateFilters({ location: e.target.value })}
            className="w-full sm:w-[180px]"
          />
        </div>

        {/* Active Filters */}
        {hasActiveFilters && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">{t.events.activeFilters}</span>
            {filters.search && (
              <Badge variant="secondary" className="gap-1">
                {t.events.filterSearch}: {filters.search}
                <X
                  className="h-3 w-3 cursor-pointer"
                  onClick={() => updateFilters({ search: '' })}
                />
              </Badge>
            )}
            {filters.category && (
              <Badge variant="secondary" className="gap-1">
                {getEventCategoryLabel(filters.category, language)}
                <X
                  className="h-3 w-3 cursor-pointer"
                  onClick={() => updateFilters({ category: '' })}
                />
              </Badge>
            )}
            {filters.start_date && (
              <Badge variant="secondary" className="gap-1">
                {t.events.filterFrom}: {format(new Date(filters.start_date), 'd MMM', { locale: dateFnsLocale })}
                <X
                  className="h-3 w-3 cursor-pointer"
                  onClick={() => updateFilters({ start_date: '', end_date: '' })}
                />
              </Badge>
            )}
            {filters.city && (
              <Badge variant="secondary" className="gap-1">
                {t.events.filterCity}: {filters.city}
                <X
                  className="h-3 w-3 cursor-pointer"
                  onClick={() => updateFilters({ city: '' })}
                />
              </Badge>
            )}
            {filters.location && (
              <Badge variant="secondary" className="gap-1">
                {t.events.filterLocation}: {filters.location}
                <X
                  className="h-3 w-3 cursor-pointer"
                  onClick={() => updateFilters({ location: '' })}
                />
              </Badge>
            )}
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              {t.events.clearAll}
            </Button>
          </div>
        )}
      </div>

      {/* Results Count */}
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {totalEvents} {totalEvents === 1 ? t.events.foundOne : t.events.foundMany}
        </p>
        <div className="flex items-center gap-2">
          {isAuthenticated && user?.role === 'student' && RECOMMENDATIONS_ENABLED && (
            <Select
              value={filters.sort}
              onValueChange={(value) => updateFilters({ sort: value as EventFilters['sort'] })}
            >
              <SelectTrigger className="w-[160px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="recommended">{t.events.recommendationsTitle}</SelectItem>
                <SelectItem value="time">{t.events.sortSoonest}</SelectItem>
              </SelectContent>
            </Select>
          )}
          <Select
            value={String(filters.page_size)}
            onValueChange={(value) => updateFilters({ page_size: Number.parseInt(value, 10) })}
          >
            <SelectTrigger className="w-[100px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PAGE_SIZES.map((size) => (
                <SelectItem key={size} value={String(size)}>
                  {size}
                  {t.events.perPage}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Events Grid */}
      {isLoading ? (
        <LoadingPage message={t.events.loading} />
      ) : events.length === 0 ? (
        renderEmptyState()
      ) : (
        <>
          {renderEventsGrid()}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-8 flex items-center justify-center gap-2">
              <Button
                variant="outline"
                size="icon"
                disabled={filters.page === 1}
                onClick={() => updateFilters({ page: filters.page - 1 })}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm">
                {t.events.pageLabel} {filters.page} {t.events.pageOf} {totalPages}
              </span>
              <Button
                variant="outline"
                size="icon"
                disabled={filters.page === totalPages}
                onClick={() => updateFilters({ page: filters.page + 1 })}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
