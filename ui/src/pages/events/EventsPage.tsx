import { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import eventService from '@/services/event.service';
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
import { ro } from 'date-fns/locale';
import { EVENT_CATEGORIES } from '@/lib/eventCategories';

const CATEGORIES = ['Toate', ...EVENT_CATEGORIES] as const;

const PAGE_SIZES = [6, 12, 24, 48];

const RECOMMENDATIONS_ENABLED =
  (import.meta.env.VITE_FEATURE_RECOMMENDATIONS ?? 'true').toLowerCase() !== 'false';

export function EventsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [events, setEvents] = useState<Event[]>([]);
  const [recommendations, setRecommendations] = useState<Event[]>([]);
  const [favorites, setFavorites] = useState<Set<number>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [totalPages, setTotalPages] = useState(1);
  const [totalEvents, setTotalEvents] = useState(0);
  const { toast } = useToast();
  const { isAuthenticated } = useAuth();

  // Memoize filters to prevent infinite loops
  const search = searchParams.get('search') || '';
  const category = searchParams.get('category') || '';
  const start_date = searchParams.get('start_date') || '';
  const end_date = searchParams.get('end_date') || '';
  const city = searchParams.get('city') || '';
  const location = searchParams.get('location') || '';
  const tagsParam = searchParams.get('tags') || '';
  const page = parseInt(searchParams.get('page') || '1');
  const page_size = parseInt(searchParams.get('page_size') || '12');

  const filters: EventFilters = useMemo(() => ({
    search,
    category,
    start_date,
    end_date,
    city,
    location,
    tags: tagsParam ? tagsParam.split(',').filter(Boolean) : [],
    page,
    page_size,
  }), [search, category, start_date, end_date, city, location, tagsParam, page, page_size]);

  const updateFilters = useCallback(
    (newFilters: Partial<EventFilters>) => {
      const params = new URLSearchParams(searchParams);

      Object.entries(newFilters).forEach(([key, value]) => {
        if (value === '' || value === null || (Array.isArray(value) && value.length === 0)) {
          params.delete(key);
        } else if (Array.isArray(value)) {
          params.set(key, value.join(','));
        } else {
          params.set(key, String(value));
        }
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
          setTotalPages(Math.ceil(response.total / (filters.page_size || 12)));
        }
      } catch {
        if (!cancelled) {
          toast({
            title: 'Eroare',
            description: 'Nu am putut încărca evenimentele',
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
  }, [filters, toast]);

  useEffect(() => {
    if (!isAuthenticated || !RECOMMENDATIONS_ENABLED) return;
    
    const loadRecommendations = async () => {
      try {
        const recs = await eventService.getRecommendations();
        setRecommendations(recs.slice(0, 4));
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
  }, [isAuthenticated]);

  const handleFavoriteToggle = async (eventId: number, shouldFavorite: boolean) => {
    if (!isAuthenticated) {
      toast({
        title: 'Autentificare necesară',
        description: 'Trebuie să fii autentificat pentru a adăuga la favorite',
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
        title: 'Eroare',
        description: 'Nu am putut actualiza favoritele',
        variant: 'destructive',
      });
    }
  };

  const clearFilters = () => {
    setSearchParams({});
  };

  const hasActiveFilters =
    filters.search ||
    filters.category ||
    filters.start_date ||
    filters.end_date ||
    filters.city ||
    filters.location ||
    (filters.tags && filters.tags.length > 0);

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Evenimente</h1>
        <p className="mt-2 text-muted-foreground">
          Descoperă și participă la evenimentele din comunitatea ta
        </p>
      </div>

      {/* Recommendations Section */}
      {RECOMMENDATIONS_ENABLED && isAuthenticated && recommendations.length > 0 && !hasActiveFilters && (
        <div className="mb-8">
          <div className="mb-4 flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <h2 className="text-xl font-semibold">Recomandate pentru tine</h2>
          </div>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {recommendations.map((event) => (
              <EventCard
                key={event.id}
                event={event}
                onFavoriteToggle={handleFavoriteToggle}
                isFavorite={favorites.has(event.id)}
                showRecommendation
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
              placeholder="Caută evenimente..."
              value={filters.search || ''}
              onChange={(e) => updateFilters({ search: e.target.value })}
              className="pl-10"
            />
          </div>

          {/* Category */}
          <Select
            value={filters.category || 'Toate'}
            onValueChange={(value) =>
              updateFilters({ category: value === 'Toate' ? '' : value })
            }
          >
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Categorie" />
            </SelectTrigger>
            <SelectContent>
              {CATEGORIES.map((cat) => (
                <SelectItem key={cat} value={cat}>
                  {cat}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Date Range */}
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" className="w-[240px] justify-start">
                <CalendarIcon className="mr-2 h-4 w-4" />
                {filters.start_date
                  ? filters.end_date
                    ? `${format(new Date(filters.start_date), 'd MMM', { locale: ro })} - ${format(new Date(filters.end_date), 'd MMM', { locale: ro })}`
                    : format(new Date(filters.start_date), 'd MMM yyyy', { locale: ro })
                  : 'Selectează perioada'}
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
                numberOfMonths={2}
                defaultMonth={filters.start_date ? new Date(filters.start_date + 'T00:00:00') : new Date()}
              />
            </PopoverContent>
          </Popover>

          {/* Location */}
          <Input
            placeholder="Oraș"
            value={filters.city || ''}
            onChange={(e) => updateFilters({ city: e.target.value })}
            className="w-[180px]"
          />

          <Input
            placeholder="Locație"
            value={filters.location || ''}
            onChange={(e) => updateFilters({ location: e.target.value })}
            className="w-[180px]"
          />
        </div>

        {/* Active Filters */}
        {hasActiveFilters && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">Filtre active:</span>
            {filters.search && (
              <Badge variant="secondary" className="gap-1">
                Căutare: {filters.search}
                <X
                  className="h-3 w-3 cursor-pointer"
                  onClick={() => updateFilters({ search: '' })}
                />
              </Badge>
            )}
            {filters.category && (
              <Badge variant="secondary" className="gap-1">
                {filters.category}
                <X
                  className="h-3 w-3 cursor-pointer"
                  onClick={() => updateFilters({ category: '' })}
                />
              </Badge>
            )}
            {filters.start_date && (
              <Badge variant="secondary" className="gap-1">
                De la: {format(new Date(filters.start_date), 'd MMM', { locale: ro })}
                <X
                  className="h-3 w-3 cursor-pointer"
                  onClick={() => updateFilters({ start_date: '', end_date: '' })}
                />
              </Badge>
            )}
            {filters.city && (
              <Badge variant="secondary" className="gap-1">
                Oraș: {filters.city}
                <X
                  className="h-3 w-3 cursor-pointer"
                  onClick={() => updateFilters({ city: '' })}
                />
              </Badge>
            )}
            {filters.location && (
              <Badge variant="secondary" className="gap-1">
                Locație: {filters.location}
                <X
                  className="h-3 w-3 cursor-pointer"
                  onClick={() => updateFilters({ location: '' })}
                />
              </Badge>
            )}
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              Șterge toate
            </Button>
          </div>
        )}
      </div>

      {/* Results Count */}
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {totalEvents} {totalEvents === 1 ? 'eveniment găsit' : 'evenimente găsite'}
        </p>
        <Select
          value={String(filters.page_size || 12)}
          onValueChange={(value) => updateFilters({ page_size: parseInt(value) })}
        >
          <SelectTrigger className="w-[100px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PAGE_SIZES.map((size) => (
              <SelectItem key={size} value={String(size)}>
                {size} / pagină
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Events Grid */}
      {isLoading ? (
        <LoadingPage message="Se încarcă evenimentele..." />
      ) : events.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Filter className="mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="text-lg font-semibold">Nu am găsit evenimente</h3>
          <p className="mt-2 text-muted-foreground">
            Încearcă să modifici filtrele sau să cauți altceva
          </p>
          {hasActiveFilters && (
            <Button variant="outline" className="mt-4" onClick={clearFilters}>
              Șterge filtrele
            </Button>
          )}
        </div>
      ) : (
        <>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {events.map((event) => (
              <EventCard
                key={event.id}
                event={event}
                onFavoriteToggle={handleFavoriteToggle}
                isFavorite={favorites.has(event.id)}
              />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-8 flex items-center justify-center gap-2">
              <Button
                variant="outline"
                size="icon"
                disabled={filters.page === 1}
                onClick={() => updateFilters({ page: (filters.page || 1) - 1 })}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm">
                Pagina {filters.page} din {totalPages}
              </span>
              <Button
                variant="outline"
                size="icon"
                disabled={filters.page === totalPages}
                onClick={() => updateFilters({ page: (filters.page || 1) + 1 })}
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
