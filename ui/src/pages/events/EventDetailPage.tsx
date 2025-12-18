import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import eventService from '@/services/event.service';
import { recordInteractions } from '@/services/analytics.service';
import type { EventDetail } from '@/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { useI18n } from '@/contexts/LanguageContext';
import {
  Calendar,
  Clock,
  MapPin,
  Users,
  Heart,
  Share2,
  CalendarPlus,
  ArrowLeft,
  User,
  ExternalLink,
  Copy,
} from 'lucide-react';
import { formatDate, formatTime, cn } from '@/lib/utils';
import { getEventCategoryLabel } from '@/lib/eventCategories';

export function EventDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [event, setEvent] = useState<EventDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRegistering, setIsRegistering] = useState(false);
  const [isResendingEmail, setIsResendingEmail] = useState(false);
  const [isFavoriting, setIsFavoriting] = useState(false);
  const [isCloning, setIsCloning] = useState(false);
  const { toast } = useToast();
  const { isAuthenticated } = useAuth();
  const { language, t } = useI18n();

  useEffect(() => {
    const loadEvent = async () => {
      if (!id) return;
      setIsLoading(true);
      try {
        const data = await eventService.getEvent(parseInt(id));
        setEvent(data);
      } catch {
        toast({
          title: t.eventDetail.notFoundTitle,
          description: t.eventDetail.notFoundDescription,
          variant: 'destructive',
        });
        navigate('/');
      } finally {
        setIsLoading(false);
      }
    };
    loadEvent();
  }, [id, navigate, toast, t]);

  const eventId = event?.id;
  useEffect(() => {
    if (!eventId) return;
    const startedAt = Date.now();
    void recordInteractions([{ interaction_type: 'view', event_id: eventId, meta: { source: 'event_detail' } }]);
    return () => {
      const seconds = Math.max(0, Math.round((Date.now() - startedAt) / 1000));
      void recordInteractions([{ interaction_type: 'dwell', event_id: eventId, meta: { source: 'event_detail', seconds } }]);
    };
  }, [eventId]);

  const handleRegister = async () => {
    if (!isAuthenticated) {
      navigate('/login', { state: { from: { pathname: `/events/${id}` } } });
      return;
    }
    if (!event) return;

    setIsRegistering(true);
    const previous = event;
    setEvent({
      ...event,
      is_registered: true,
      seats_taken: event.seats_taken + 1,
      available_seats:
        typeof event.available_seats === 'number' ? event.available_seats - 1 : event.available_seats,
    });
    try {
      await eventService.registerForEvent(event.id);
      toast({
        title: t.eventDetail.registerSuccessTitle,
        description: t.eventDetail.registerSuccessDescription,
        variant: 'success' as const,
      });
    } catch (error: unknown) {
      setEvent(previous);
      const axiosError = error as { response?: { data?: { detail?: string } } };
      toast({
        title: t.common.error,
        description: axiosError.response?.data?.detail || t.eventDetail.registerErrorFallback,
        variant: 'destructive',
      });
    } finally {
      setIsRegistering(false);
    }
  };

  const handleUnregister = async () => {
    if (!event) return;

    setIsRegistering(true);
    const previous = event;
    setEvent({
      ...event,
      is_registered: false,
      seats_taken: Math.max(0, event.seats_taken - 1),
      available_seats:
        typeof event.available_seats === 'number' ? event.available_seats + 1 : event.available_seats,
    });
    try {
      await eventService.unregisterFromEvent(event.id);
      toast({
        title: t.eventDetail.unregisterSuccessTitle,
        description: t.eventDetail.unregisterSuccessDescription,
      });
    } catch (error: unknown) {
      setEvent(previous);
      const axiosError = error as { response?: { data?: { detail?: string } } };
      toast({
        title: t.common.error,
        description: axiosError.response?.data?.detail || t.eventDetail.unregisterErrorFallback,
        variant: 'destructive',
      });
    } finally {
      setIsRegistering(false);
    }
  };

  const handleResendRegistrationEmail = async () => {
    if (!event) return;

    setIsResendingEmail(true);
    try {
      await eventService.resendRegistrationEmail(event.id);
      toast({
        title: t.eventDetail.resendSuccessTitle,
        description: t.eventDetail.resendSuccessDescription,
        variant: 'success' as const,
      });
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      toast({
        title: t.common.error,
        description: axiosError.response?.data?.detail || t.eventDetail.resendErrorFallback,
        variant: 'destructive',
      });
    } finally {
      setIsResendingEmail(false);
    }
  };

  const handleFavorite = async () => {
    if (!isAuthenticated) {
      navigate('/login', { state: { from: { pathname: `/events/${id}` } } });
      return;
    }
    if (!event) return;

    setIsFavoriting(true);
    try {
      if (event.is_favorite) {
        await eventService.removeFromFavorites(event.id);
      } else {
        await eventService.addToFavorites(event.id);
      }
      setEvent((prev) => (prev ? { ...prev, is_favorite: !prev.is_favorite } : null));
    } catch {
      toast({
        title: t.eventDetail.favoritesErrorTitle,
        description: t.eventDetail.favoritesErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsFavoriting(false);
    }
  };

  const handleShare = async () => {
    const url = window.location.href;
    if (navigator.share) {
      try {
        await navigator.share({
          title: event?.title,
          text: event?.description,
          url,
        });
        if (event) {
          void recordInteractions([{ interaction_type: 'share', event_id: event.id, meta: { channel: 'native' } }]);
        }
      } catch {
        // User cancelled
      }
    } else {
      await navigator.clipboard.writeText(url);
      toast({
        title: t.eventDetail.shareCopiedTitle,
        description: t.eventDetail.shareCopiedDescription,
      });
      if (event) {
        void recordInteractions([{ interaction_type: 'share', event_id: event.id, meta: { channel: 'copy' } }]);
      }
    }
  };

  const handleExportCalendar = () => {
    if (!event) return;
    window.open(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/events/${event.id}/ics`);
  };

  const handleClone = async () => {
    if (!event) return;

    setIsCloning(true);
    try {
      const clonedEvent = await eventService.cloneEvent(event.id);
      toast({
        title: t.eventDetail.cloneSuccessTitle,
        description: t.eventDetail.cloneSuccessDescription,
        variant: 'success' as const,
      });
      // Navigate to edit the cloned event
      navigate(`/organizer/events/${clonedEvent.id}/edit`);
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      toast({
        title: t.common.error,
        description: axiosError.response?.data?.detail || t.eventDetail.cloneErrorFallback,
        variant: 'destructive',
      });
    } finally {
      setIsCloning(false);
    }
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Skeleton className="mb-6 h-10 w-24" />

        <div className="grid gap-8 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <Skeleton className="mb-6 aspect-video w-full rounded-xl" />

            <div className="mb-6 space-y-2">
              <Skeleton className="h-6 w-24" />
              <Skeleton className="h-10 w-3/4" />
            </div>

            <div className="mb-6 grid gap-4 sm:grid-cols-2">
              <Skeleton className="h-[88px] rounded-lg" />
              <Skeleton className="h-[88px] rounded-lg" />
              <Skeleton className="h-[88px] rounded-lg" />
              <Skeleton className="h-[88px] rounded-lg" />
            </div>

            <Separator className="my-6" />

            <div className="space-y-3">
              <Skeleton className="h-6 w-40" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          </div>

          <div className="space-y-6">
            <Skeleton className="h-[320px] w-full rounded-xl" />
            <Skeleton className="h-[56px] w-full rounded-xl" />
            <Skeleton className="h-[120px] w-full rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  if (!event) {
    return null;
  }

  const isPast = new Date(event.start_time) < new Date();
  const isFull = typeof event.available_seats === 'number' && event.available_seats <= 0;

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Back Button */}
      <Button variant="ghost" className="mb-6" onClick={() => navigate(-1)}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        {t.eventDetail.back}
      </Button>

      <div className="grid gap-8 lg:grid-cols-3">
        {/* Main Content */}
        <div className="lg:col-span-2">
          {/* Cover Image */}
          <div className="relative mb-6 aspect-video overflow-hidden rounded-xl bg-muted">
            {event.cover_url ? (
              <img
                src={event.cover_url}
                alt={event.title}
                className="h-full w-full object-cover"
                onError={(e) => {
                  (e.target as HTMLImageElement).src =
                    'https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=1200&h=600&fit=crop';
                }}
              />
            ) : (
              <div className="flex h-full items-center justify-center bg-gradient-to-br from-primary/20 to-primary/5">
                <Calendar className="h-24 w-24 text-primary/40" />
              </div>
            )}

            {/* Status Badges */}
            <div className="absolute left-4 top-4 flex flex-wrap gap-2">
              {event.status === 'draft' && <Badge variant="secondary">{t.eventDetail.draft}</Badge>}
              {isPast && <Badge variant="secondary">{t.eventDetail.ended}</Badge>}
              {isFull && !isPast && <Badge variant="destructive">{t.eventDetail.full}</Badge>}
            </div>
          </div>

          {/* Title & Category */}
          <div className="mb-6">
            {event.category && (
              <Badge variant="outline" className="mb-2">
                {getEventCategoryLabel(event.category, language)}
              </Badge>
            )}
            <h1 className="text-3xl font-bold">{event.title}</h1>
          </div>

          {/* Quick Info */}
          <div className="mb-6 grid gap-4 sm:grid-cols-2">
            <div className="flex items-center gap-3 rounded-lg border p-4">
              <Calendar className="h-5 w-5 text-primary" />
              <div>
                <p className="text-sm text-muted-foreground">{t.eventDetail.dateLabel}</p>
                <p className="font-medium">{formatDate(event.start_time, language)}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-lg border p-4">
              <Clock className="h-5 w-5 text-primary" />
              <div>
                <p className="text-sm text-muted-foreground">{t.eventDetail.timeLabel}</p>
                <p className="font-medium">
                  {formatTime(event.start_time, language)}
                  {event.end_time && ` - ${formatTime(event.end_time, language)}`}
                </p>
              </div>
            </div>
            {(event.city || event.location) && (
              <div className="flex items-center gap-3 rounded-lg border p-4">
                <MapPin className="h-5 w-5 text-primary" />
                <div>
                  <p className="text-sm text-muted-foreground">{t.eventDetail.locationLabel}</p>
                  <p className="font-medium">
                    {[event.city, event.location].filter(Boolean).join(' • ')}
                  </p>
                </div>
              </div>
            )}
            <div className="flex items-center gap-3 rounded-lg border p-4">
              <Users className="h-5 w-5 text-primary" />
              <div>
                <p className="text-sm text-muted-foreground">{t.eventDetail.participantsLabel}</p>
                <p className="font-medium">
                  {event.seats_taken}
                  {event.max_seats && ` / ${event.max_seats}`} {t.eventDetail.seatsTakenSuffix}
                </p>
              </div>
            </div>
          </div>

          <Separator className="my-6" />

          {/* Description */}
          <div className="mb-6">
            <h2 className="mb-4 text-xl font-semibold">{t.eventDetail.descriptionTitle}</h2>
            <div className="prose prose-neutral dark:prose-invert max-w-none">
              {event.description ? (
                <p className="whitespace-pre-wrap">{event.description}</p>
              ) : (
                <p className="text-muted-foreground">
                  {t.eventDetail.descriptionEmpty}
                </p>
              )}
            </div>
          </div>

          {/* Tags */}
          {event.tags.length > 0 && (
            <div className="mb-6">
              <h2 className="mb-4 text-xl font-semibold">{t.eventDetail.tagsTitle}</h2>
              <div className="flex flex-wrap gap-2">
                {event.tags.map((tag) => (
                  <Badge key={tag.id} variant="secondary">
                    {tag.name}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="lg:col-span-1">
          <div className="sticky top-24 space-y-6">
            {/* Registration Card */}
            <div className="rounded-xl border p-6">
              <h3 className="mb-4 text-lg font-semibold">{t.eventDetail.registrationTitle}</h3>

              {event.is_owner ? (
                <div className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    {t.eventDetail.ownerNote}
                  </p>
                  <Button asChild className="w-full">
                    <Link to={`/organizer/events/${event.id}/edit`}>
                      {t.eventDetail.editEvent}
                    </Link>
                  </Button>
                  <Button asChild variant="outline" className="w-full">
                    <Link to={`/organizer/events/${event.id}/participants`}>
                      {t.eventDetail.viewParticipants}
                    </Link>
                  </Button>
                  <Button 
                    variant="outline" 
                    className="w-full"
                    onClick={handleClone}
                    disabled={isCloning}
                  >
                    <Copy className="mr-2 h-4 w-4" />
                    {isCloning ? t.eventDetail.cloning : t.eventDetail.cloneEvent}
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  {event.is_registered ? (
                    <>
                      <div className="rounded-lg bg-green-50 p-4 text-center dark:bg-green-900/20">
                        <p className="font-medium text-green-700 dark:text-green-400">
                          {t.eventDetail.registeredOk}
                        </p>
                      </div>
                      <Button
                        variant="secondary"
                        className="w-full"
                        onClick={handleResendRegistrationEmail}
                        disabled={isResendingEmail}
                      >
                        {isResendingEmail ? t.eventDetail.resendingEmail : t.eventDetail.resendEmail}
                      </Button>
                      {!isPast && (
                        <Button
                          variant="outline"
                          className="w-full"
                          onClick={handleUnregister}
                          disabled={isRegistering}
                        >
                          {t.eventDetail.unregister}
                        </Button>
                      )}
                    </>
                  ) : isPast ? (
                    <p className="text-center text-muted-foreground">
                      {t.eventDetail.eventEndedText}
                    </p>
                  ) : isFull ? (
                    <p className="text-center text-destructive">
                      {t.eventDetail.eventFullText}
                    </p>
                  ) : (
                    <Button
                      className="w-full"
                      onClick={handleRegister}
                      disabled={isRegistering}
                    >
                      {isRegistering ? t.eventDetail.registering : t.eventDetail.register}
                    </Button>
                  )}

                  {/* Available Seats */}
                  {typeof event.available_seats === 'number' && !isPast && (
                    <p className="text-center text-sm text-muted-foreground">
                      {event.available_seats} {t.eventDetail.seatsAvailableSuffix}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="icon"
                onClick={handleFavorite}
                disabled={isFavoriting}
                className={cn(event.is_favorite && 'text-red-500')}
              >
                <Heart className={cn('h-4 w-4', event.is_favorite && 'fill-current')} />
              </Button>
              <Button variant="outline" size="icon" onClick={handleShare}>
                <Share2 className="h-4 w-4" />
              </Button>
              <Button variant="outline" className="flex-1" onClick={handleExportCalendar}>
                <CalendarPlus className="mr-2 h-4 w-4" />
                {t.eventDetail.addToCalendar}
              </Button>
            </div>

            {/* Organizer Info */}
            <div className="rounded-xl border p-6">
              <h3 className="mb-4 text-lg font-semibold">{t.eventDetail.organizerTitle}</h3>
              <Link
                to={`/organizers/${event.owner_id}`}
                className="flex items-center gap-3 hover:underline"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                  <User className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="font-medium">{event.owner_name || t.eventDetail.organizerFallback}</p>
                  <p className="text-sm text-muted-foreground">{t.eventDetail.viewProfile}</p>
                </div>
                <ExternalLink className="ml-auto h-4 w-4 text-muted-foreground" />
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
