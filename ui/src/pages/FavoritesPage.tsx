import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import eventService from '@/services/event.service';
import type { Event } from '@/types';
import { EventCard } from '@/components/events/EventCard';
import { Button } from '@/components/ui/button';
import { LoadingPage } from '@/components/ui/loading';
import { useToast } from '@/hooks/use-toast';
import { useI18n } from '@/contexts/LanguageContext';
import { Heart, Search } from 'lucide-react';

type FavoritesTranslations = ReturnType<typeof useI18n>['t']['favorites'];
type FavoritesGridProps = Readonly<{
  events: Event[];
  favorites: Set<number>;
  onFavoriteToggle: (eventId: number, shouldFavorite: boolean) => Promise<void>;
}>;
type FavoritesSectionProps = Readonly<{ favorites: FavoritesTranslations }>;

/**
 * Test helper: favorite ids.
 */
function favoriteIds(events: Event[]): Set<number> {
  return new Set(events.map((event) => event.id));
}

/**
 * Test helper: favorites header.
 */
function FavoritesHeader({ favorites }: FavoritesSectionProps) {
  return (
    <div className="mb-8">
      <h1 className="text-3xl font-bold">{favorites.title}</h1>
      <p className="mt-2 text-muted-foreground">{favorites.subtitle}</p>
    </div>
  );
}

/**
 * Test helper: favorites empty state.
 */
function FavoritesEmptyState({ favorites }: FavoritesSectionProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Heart className="mb-4 h-12 w-12 text-muted-foreground" />
      <h3 className="text-lg font-semibold">{favorites.emptyTitle}</h3>
      <p className="mt-2 text-muted-foreground">{favorites.emptyDescription}</p>
      <Button asChild className="mt-4">
        <Link to="/">
          <Search className="mr-2 h-4 w-4" />
          {favorites.exploreEvents}
        </Link>
      </Button>
    </div>
  );
}

/**
 * Test helper: favorites grid.
 */
function FavoritesGrid({ events, favorites, onFavoriteToggle }: FavoritesGridProps) {
  return (
    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {events.map((event) => (
        <EventCard
          key={event.id}
          event={event}
          onFavoriteToggle={onFavoriteToggle}
          isFavorite={favorites.has(event.id)}
        />
      ))}
    </div>
  );
}

/**
 * Test helper: favorites page.
 */
export function FavoritesPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [favorites, setFavorites] = useState<Set<number>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const { toast } = useToast();
  const { t } = useI18n();

  const loadFavorites = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await eventService.getFavorites();
      setEvents(response.items);
      setFavorites(favoriteIds(response.items));
    } catch {
      toast({
        title: t.favorites.loadErrorTitle,
        description: t.favorites.loadErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [toast, t]);

  useEffect(() => {
    loadFavorites();
  }, [loadFavorites]);

  const handleFavoriteToggle = async (eventId: number, shouldFavorite: boolean) => {
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
        // Remove from displayed list
        setEvents((prev) => prev.filter((e) => e.id !== eventId));
      }
    } catch {
      toast({
        title: t.favorites.updateErrorTitle,
        description: t.favorites.updateErrorDescription,
        variant: 'destructive',
      });
    }
  };

  if (isLoading) {
    return <LoadingPage message={t.favorites.loading} />;
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <FavoritesHeader favorites={t.favorites} />
      {events.length === 0 ? (
        <FavoritesEmptyState favorites={t.favorites} />
      ) : (
        <FavoritesGrid
          events={events}
          favorites={favorites}
          onFavoriteToggle={handleFavoriteToggle}
        />
      )}
    </div>
  );
}
