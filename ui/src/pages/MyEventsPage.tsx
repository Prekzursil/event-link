import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import eventService from '@/services/event.service';
import type { Event } from '@/types';
import { EventCard } from '@/components/events/EventCard';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { LoadingPage } from '@/components/ui/loading';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { useI18n } from '@/contexts/LanguageContext';
import { Calendar, CalendarPlus, Clock, History, Search, Plus, Megaphone } from 'lucide-react';

export function MyEventsPage() {
  const { isOrganizer } = useAuth();
  const { t } = useI18n();
  const [upcomingEvents, setUpcomingEvents] = useState<Event[]>([]);
  const [pastEvents, setPastEvents] = useState<Event[]>([]);
  const [organizerEvents, setOrganizerEvents] = useState<Event[]>([]);
  const [favorites, setFavorites] = useState<Set<number>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [isDownloadingCalendar, setIsDownloadingCalendar] = useState(false);
  const { toast } = useToast();

  const loadEvents = useCallback(async () => {
    setIsLoading(true);
    try {
      const events = await eventService.getMyEvents();
      const now = new Date();

      const upcoming = events.filter(
        (event: Event) => new Date(event.start_time) >= now
      );
      const past = events.filter(
        (event: Event) => new Date(event.start_time) < now
      );

      // Sort upcoming by date ascending
      upcoming.sort(
        (a: Event, b: Event) =>
          new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
      );

      // Sort past by date descending
      past.sort(
        (a: Event, b: Event) =>
          new Date(b.start_time).getTime() - new Date(a.start_time).getTime()
      );

      setUpcomingEvents(upcoming);
      setPastEvents(past);

      // Load organizer events if user is organizer
      if (isOrganizer) {
        const orgEvents = await eventService.getOrganizerEvents();
        // Sort by date descending (newest first)
        orgEvents.sort(
          (a: Event, b: Event) =>
            new Date(b.start_time).getTime() - new Date(a.start_time).getTime()
        );
        setOrganizerEvents(orgEvents);
      }
    } catch {
      toast({
        title: t.myEvents.loadErrorTitle,
        description: t.myEvents.loadErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [toast, isOrganizer, t]);

  const loadFavorites = useCallback(async () => {
    try {
      const response = await eventService.getFavorites();
      setFavorites(new Set(response.items.map((e) => e.id)));
    } catch {
      // Silent fail
    }
  }, []);

  useEffect(() => {
    loadEvents();
    loadFavorites();
  }, [loadEvents, loadFavorites]);

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
      }
    } catch {
      toast({
        title: t.myEvents.favoritesErrorTitle,
        description: t.myEvents.favoritesErrorDescription,
        variant: 'destructive',
      });
    }
  };

  const handleDownloadCalendar = async () => {
    setIsDownloadingCalendar(true);
    try {
      const ics = await eventService.getMyCalendar();
      const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'eventlink-calendar.ics';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);

      toast({
        title: t.myEvents.calendarDownloadedTitle,
        description: t.myEvents.calendarDownloadedDescription,
      });
    } catch {
      toast({
        title: t.myEvents.calendarDownloadErrorTitle,
        description: t.myEvents.calendarDownloadErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsDownloadingCalendar(false);
    }
  };

  if (isLoading) {
    return <LoadingPage message={t.myEvents.loading} />;
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t.myEvents.title}</h1>
          <p className="mt-2 text-muted-foreground">
            {isOrganizer ? t.myEvents.subtitleOrganizer : t.myEvents.subtitleStudent}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={handleDownloadCalendar}
            disabled={isDownloadingCalendar}
          >
            <CalendarPlus className="mr-2 h-4 w-4" />
            {isDownloadingCalendar ? t.myEvents.calendarDownloading : t.myEvents.calendarButton}
          </Button>
          {isOrganizer && (
            <Button asChild>
              <Link to="/organizer/events/new">
                <Plus className="mr-2 h-4 w-4" />
                {t.nav.newEvent}
              </Link>
            </Button>
          )}
        </div>
      </div>

      {upcomingEvents.length === 0 && pastEvents.length === 0 && organizerEvents.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Calendar className="mb-4 h-12 w-12 text-muted-foreground" />
          <h3 className="text-lg font-semibold">{t.myEvents.emptyTitle}</h3>
          <p className="mt-2 text-muted-foreground">
            {t.myEvents.emptyDescription}
          </p>
          <Button asChild className="mt-4">
            <Link to="/">
              <Search className="mr-2 h-4 w-4" />
              {t.myEvents.exploreEvents}
            </Link>
          </Button>
        </div>
      ) : (
        <Tabs defaultValue={isOrganizer ? "organized" : "upcoming"} className="w-full">
          <TabsList className="mb-6">
            {isOrganizer && (
              <TabsTrigger value="organized" className="gap-2">
                <Megaphone className="h-4 w-4" />
                {t.myEvents.tabOrganized} ({organizerEvents.length})
              </TabsTrigger>
            )}
            <TabsTrigger value="upcoming" className="gap-2">
              <Clock className="h-4 w-4" />
              {t.myEvents.tabUpcoming} ({upcomingEvents.length})
            </TabsTrigger>
            <TabsTrigger value="past" className="gap-2">
              <History className="h-4 w-4" />
              {t.myEvents.tabPast} ({pastEvents.length})
            </TabsTrigger>
          </TabsList>

          {isOrganizer && (
            <TabsContent value="organized">
              {organizerEvents.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Megaphone className="mb-4 h-12 w-12 text-muted-foreground" />
                  <h3 className="text-lg font-semibold">{t.myEvents.organizedEmptyTitle}</h3>
                  <p className="mt-2 text-muted-foreground">
                    {t.myEvents.organizedEmptyDescription}
                  </p>
                  <Button asChild className="mt-4">
                    <Link to="/organizer/events/new">
                      <Plus className="mr-2 h-4 w-4" />
                      {t.myEvents.organizedCreateButton}
                    </Link>
                  </Button>
                </div>
              ) : (
                <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {organizerEvents.map((event) => (
                    <EventCard
                      key={event.id}
                      event={event}
                      onFavoriteToggle={handleFavoriteToggle}
                      isFavorite={favorites.has(event.id)}
                      showEditButton
                    />
                  ))}
                </div>
              )}
            </TabsContent>
          )}

          <TabsContent value="upcoming">
            {upcomingEvents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Clock className="mb-4 h-12 w-12 text-muted-foreground" />
                <h3 className="text-lg font-semibold">{t.myEvents.upcomingEmptyTitle}</h3>
                <p className="mt-2 text-muted-foreground">
                  {t.myEvents.upcomingEmptyDescription}
                </p>
              </div>
            ) : (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {upcomingEvents.map((event) => (
                  <EventCard
                    key={event.id}
                    event={event}
                    onFavoriteToggle={handleFavoriteToggle}
                    isFavorite={favorites.has(event.id)}
                  />
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="past">
            {pastEvents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <History className="mb-4 h-12 w-12 text-muted-foreground" />
                <h3 className="text-lg font-semibold">{t.myEvents.pastEmptyTitle}</h3>
                <p className="mt-2 text-muted-foreground">
                  {t.myEvents.pastEmptyDescription}
                </p>
              </div>
            ) : (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {pastEvents.map((event) => (
                  <EventCard
                    key={event.id}
                    event={event}
                    onFavoriteToggle={handleFavoriteToggle}
                    isFavorite={favorites.has(event.id)}
                  />
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
