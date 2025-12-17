import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import eventService from '@/services/event.service';
import type { Event } from '@/types';
import { EventCard } from '@/components/events/EventCard';
import { Button } from '@/components/ui/button';
import { LoadingPage } from '@/components/ui/loading';
import { useToast } from '@/hooks/use-toast';
import { Heart, Search } from 'lucide-react';

export function FavoritesPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [favorites, setFavorites] = useState<Set<number>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const { toast } = useToast();

  const loadFavorites = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await eventService.getFavorites();
      setEvents(response.items);
      setFavorites(new Set(response.items.map((e) => e.id)));
    } catch {
      toast({
        title: 'Eroare',
        description: 'Nu am putut încărca favoritele',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [toast]);

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
        title: 'Eroare',
        description: 'Nu am putut actualiza favoritele',
        variant: 'destructive',
      });
    }
  };

  if (isLoading) {
    return <LoadingPage message="Se încarcă favoritele..." />;
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Favorite</h1>
        <p className="mt-2 text-muted-foreground">
          Evenimentele salvate în lista ta de favorite
        </p>
      </div>

      {events.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Heart className="mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="text-lg font-semibold">Nu ai evenimente favorite</h3>
          <p className="mt-2 text-muted-foreground">
            Adaugă evenimente la favorite pentru a le accesa mai ușor
          </p>
          <Button asChild className="mt-4">
            <Link to="/">
              <Search className="mr-2 h-4 w-4" />
              Explorează evenimente
            </Link>
          </Button>
        </div>
      ) : (
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
      )}
    </div>
  );
}
