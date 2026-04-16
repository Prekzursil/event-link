import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { recordInteractions, type InteractionType } from '@/services/analytics.service';
import eventService from '@/services/event.service';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { useI18n } from '@/contexts/LanguageContext';
import type { EventDetail } from '@/types';

type AxiosDetailError = {
  response?: {
    data?: {
      detail?: string;
    };
  };
};

/** Read an API error detail when the backend includes one. */
/**
 * Test helper: error detail.
 */
function errorDetail(error: unknown, fallback: string) {
  return (error as AxiosDetailError).response?.data?.detail || fallback;
}

/** Ignore best-effort async work that should not block UI updates. */
function swallowPromise<T>(result?: PromiseLike<T>) {
  Promise.resolve(result).catch(() => undefined);
}

/** Mirror the seat counters that change when a user registers or unregisters. */
function optimisticRegistrationEvent(event: EventDetail, nextRegistered: boolean): EventDetail {
  const seatsDelta = nextRegistered ? 1 : -1;
  return {
    ...event,
    is_registered: nextRegistered,
    seats_taken: Math.max(0, event.seats_taken + seatsDelta),
    available_seats:
      typeof event.available_seats === 'number'
        ? event.available_seats - seatsDelta
        : event.available_seats,
  };
}

/** Record event-detail interactions without surfacing analytics failures. */
function recordEventDetailInteraction(eventId: number, interactionType: InteractionType, meta?: Record<string, unknown>) {
  swallowPromise(recordInteractions([{ interaction_type: interactionType, event_id: eventId, meta }]));
}

/** Compute the display flags derived from the loaded event payload. */
function eventDetailStatus(event: EventDetail | null) {
  return {
    isPast: Boolean(event && new Date(event.start_time) < new Date()),
    isFull: typeof event?.available_seats === 'number' && event.available_seats <= 0,
  };
}

/** Preserve the inferred controller type while keeping the return object local. */
function createEventDetailController<T>(controller: T) {
  return controller;
}

/** Build the event-detail page controller used by the route component. */
export function useEventDetailController() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { isAuthenticated, user } = useAuth();
  const { language, t } = useI18n();
  const [event, setEvent] = useState<EventDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRegistering, setIsRegistering] = useState(false);
  const [isResendingEmail, setIsResendingEmail] = useState(false);
  const [isFavoriting, setIsFavoriting] = useState(false);
  const [isCloning, setIsCloning] = useState(false);
  const [hideTagId, setHideTagId] = useState('');
  const [isHidingTag, setIsHidingTag] = useState(false);
  const [isBlockingOrganizer, setIsBlockingOrganizer] = useState(false);

  const isStudent = isAuthenticated && user?.role === 'student';

  const loadEvent = useCallback(async () => {
    if (!id) {
      return;
    }
    setIsLoading(true);
    try {
      const data = await eventService.getEvent(Number.parseInt(id, 10));
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
  }, [id, navigate, t, toast]);

  useEffect(() => {
    swallowPromise(loadEvent());
  }, [loadEvent]);

  const eventId = event?.id;
  useEffect(function trackEventDwellEffect() {
    if (!eventId) {
      return undefined;
    }
    const trackedEventId = eventId;
    const startedAt = Date.now();
    recordEventDetailInteraction(trackedEventId, 'view', { source: 'event_detail' });
    /** Persist dwell-time analytics when the event detail view unmounts. */
    function trackDwellOnCleanup(): void {
      const seconds = Math.max(0, Math.round((Date.now() - startedAt) / 1000));
      recordEventDetailInteraction(trackedEventId, 'dwell', { source: 'event_detail', seconds });
    }
    return trackDwellOnCleanup;
  }, [eventId]);

  const handleRequireAuth = useCallback(() => {
    navigate('/login', { state: { from: { pathname: `/events/${id}` } } });
  }, [id, navigate]);

  const handleRegister = useCallback(async () => {
    if (!isAuthenticated) {
      handleRequireAuth();
      return;
    }
    if (!event) {
      return;
    }

    const previousEvent = event;
    setIsRegistering(true);
    setEvent(optimisticRegistrationEvent(event, true));
    try {
      await eventService.registerForEvent(event.id);
      recordEventDetailInteraction(event.id, 'register', { source: 'event_detail' });
      toast({
        title: t.eventDetail.registerSuccessTitle,
        description: t.eventDetail.registerSuccessDescription,
        variant: 'success' as const,
      });
    } catch (error: unknown) {
      setEvent(previousEvent);
      toast({
        title: t.common.error,
        description: errorDetail(error, t.eventDetail.registerErrorFallback),
        variant: 'destructive',
      });
    } finally {
      setIsRegistering(false);
    }
  }, [event, handleRequireAuth, isAuthenticated, t, toast]);

  const handleUnregister = useCallback(async () => {
    if (!event) {
      return;
    }

    const previousEvent = event;
    setIsRegistering(true);
    setEvent(optimisticRegistrationEvent(event, false));
    try {
      await eventService.unregisterFromEvent(event.id);
      recordEventDetailInteraction(event.id, 'unregister', { source: 'event_detail' });
      toast({
        title: t.eventDetail.unregisterSuccessTitle,
        description: t.eventDetail.unregisterSuccessDescription,
      });
    } catch (error: unknown) {
      setEvent(previousEvent);
      toast({
        title: t.common.error,
        description: errorDetail(error, t.eventDetail.unregisterErrorFallback),
        variant: 'destructive',
      });
    } finally {
      setIsRegistering(false);
    }
  }, [event, t, toast]);

  const handleResendRegistrationEmail = useCallback(async () => {
    if (!event) {
      return;
    }

    setIsResendingEmail(true);
    try {
      await eventService.resendRegistrationEmail(event.id);
      toast({
        title: t.eventDetail.resendSuccessTitle,
        description: t.eventDetail.resendSuccessDescription,
        variant: 'success' as const,
      });
    } catch (error: unknown) {
      toast({
        title: t.common.error,
        description: errorDetail(error, t.eventDetail.resendErrorFallback),
        variant: 'destructive',
      });
    } finally {
      setIsResendingEmail(false);
    }
  }, [event, t, toast]);

  const handleFavorite = useCallback(async () => {
    if (!isAuthenticated) {
      handleRequireAuth();
      return;
    }
    if (!event) {
      return;
    }

    setIsFavoriting(true);
    try {
      if (event.is_favorite) {
        await eventService.removeFromFavorites(event.id);
        recordEventDetailInteraction(event.id, 'favorite', { action: 'remove' });
      } else {
        await eventService.addToFavorites(event.id);
        recordEventDetailInteraction(event.id, 'favorite', { action: 'add' });
      }
      setEvent({ ...event, is_favorite: !event.is_favorite });
    } catch {
      toast({
        title: t.eventDetail.favoritesErrorTitle,
        description: t.eventDetail.favoritesErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsFavoriting(false);
    }
  }, [event, handleRequireAuth, isAuthenticated, t, toast]);

  const handleShare = useCallback(async () => {
    if (!event) {
      return;
    }

    const url = globalThis.location.href;
    if (navigator.share) {
      try {
        await navigator.share({
          title: event.title,
          text: event.description,
          url,
        });
        recordEventDetailInteraction(event.id, 'share', { channel: 'native' });
      } catch {
        // User cancelled native sharing.
      }
      return;
    }

    await navigator.clipboard.writeText(url);
    toast({
      title: t.eventDetail.shareCopiedTitle,
      description: t.eventDetail.shareCopiedDescription,
    });
    recordEventDetailInteraction(event.id, 'share', { channel: 'copy' });
  }, [event, t, toast]);

  const handleExportCalendar = useCallback(() => {
    if (!event) {
      return;
    }
    window.open(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/events/${event.id}/ics`);
  }, [event]);

  const handleClone = useCallback(async () => {
    if (!event) {
      return;
    }

    setIsCloning(true);
    try {
      const clonedEvent = await eventService.cloneEvent(event.id);
      toast({
        title: t.eventDetail.cloneSuccessTitle,
        description: t.eventDetail.cloneSuccessDescription,
        variant: 'success' as const,
      });
      navigate(`/organizer/events/${clonedEvent.id}/edit`);
    } catch (error: unknown) {
      toast({
        title: t.common.error,
        description: errorDetail(error, t.eventDetail.cloneErrorFallback),
        variant: 'destructive',
      });
    } finally {
      setIsCloning(false);
    }
  }, [event, navigate, t, toast]);

  const handleHideTag = useCallback(async () => {
    const tagId = Number.parseInt(hideTagId, 10);
    if (!tagId) {
      return;
    }

    setIsHidingTag(true);
    try {
      await eventService.hideTag(tagId);
      setHideTagId('');
      toast({
        title: t.personalization.tagHiddenTitle,
        description: t.personalization.tagHiddenDescription,
        variant: 'success' as const,
      });
    } catch (error: unknown) {
      toast({
        title: t.common.error,
        description: errorDetail(error, t.personalization.tagHiddenErrorFallback),
        variant: 'destructive',
      });
    } finally {
      setIsHidingTag(false);
    }
  }, [hideTagId, t, toast]);

  const handleBlockOrganizer = useCallback(async () => {
    if (!event) {
      return;
    }

    setIsBlockingOrganizer(true);
    try {
      await eventService.blockOrganizer(event.owner_id);
      toast({
        title: t.personalization.organizerBlockedTitle,
        description: t.personalization.organizerBlockedDescription,
        variant: 'success' as const,
      });
    } catch (error: unknown) {
      toast({
        title: t.common.error,
        description: errorDetail(error, t.personalization.organizerBlockedErrorFallback),
        variant: 'destructive',
      });
    } finally {
      setIsBlockingOrganizer(false);
    }
  }, [event, t, toast]);

  const { isPast, isFull } = useMemo(() => eventDetailStatus(event), [event]);

  return createEventDetailController({
    event, handleBlockOrganizer, handleClone, handleExportCalendar, handleFavorite, handleHideTag,
    handleRegister, handleResendRegistrationEmail, handleShare, handleUnregister, hideTagId,
    isBlockingOrganizer, isCloning, isFavoriting, isFull, isHidingTag, isLoading, isPast,
    isRegistering, isResendingEmail, isStudent, language, navigate, setHideTagId, t,
  });
}

export type EventDetailController = ReturnType<typeof useEventDetailController>;
