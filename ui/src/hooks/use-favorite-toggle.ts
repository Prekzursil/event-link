import { useState } from 'react';
import eventService from '@/services/event.service';
import { useToast } from '@/hooks/use-toast';

type ToastStrings = Readonly<{
  errorTitle: string;
  errorDescription: string;
}>;

type ToggleOptions = Readonly<{
  /** Optional guard run before toggling; return false to abort (e.g. auth check). */
  guard?: () => boolean;
  /** Optional callback invoked after a successful un-favorite (e.g. drop from a list). */
  onRemoved?: (eventId: number) => void;
}>;

export type FavoriteToggle = Readonly<{
  favorites: Set<number>;
  setFavorites: React.Dispatch<React.SetStateAction<Set<number>>>;
  toggleFavorite: (
    eventId: number,
    shouldFavorite: boolean,
    options?: ToggleOptions,
  ) => Promise<void>;
}>;

/**
 * Own the favorites set and the add/remove API flow shared by every page that
 * renders favoritable event cards. Pages supply their own error-toast copy and
 * may pass a guard (e.g. auth check) or an ``onRemoved`` callback.
 */
export function useFavoriteToggle(strings: ToastStrings): FavoriteToggle {
  const [favorites, setFavorites] = useState<Set<number>>(new Set());
  const { toast } = useToast();

  const toggleFavorite = async (
    eventId: number,
    shouldFavorite: boolean,
    options?: ToggleOptions,
  ): Promise<void> => {
    if (options?.guard && !options.guard()) {
      return;
    }
    try {
      if (shouldFavorite) {
        await eventService.addToFavorites(eventId);
        setFavorites((prev) => new Set([...prev, eventId]));
      } else {
        await eventService.removeFromFavorites(eventId);
        setFavorites((prev) => {
          const next = new Set(prev);
          next.delete(eventId);
          return next;
        });
        options?.onRemoved?.(eventId);
      }
    } catch {
      toast({
        title: strings.errorTitle,
        description: strings.errorDescription,
        variant: 'destructive',
      });
    }
  };

  return { favorites, setFavorites, toggleFavorite };
}
