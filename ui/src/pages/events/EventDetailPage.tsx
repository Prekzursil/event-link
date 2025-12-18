import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import eventService from '@/services/event.service';
import type { EventDetail } from '@/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';
import { useAuth } from '@/contexts/AuthContext';
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
import { formatDate, cn } from '@/lib/utils';

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

  useEffect(() => {
    const loadEvent = async () => {
      if (!id) return;
      setIsLoading(true);
      try {
        const data = await eventService.getEvent(parseInt(id));
        setEvent(data);
      } catch {
        toast({
          title: 'Eroare',
          description: 'Evenimentul nu a fost găsit',
          variant: 'destructive',
        });
        navigate('/');
      } finally {
        setIsLoading(false);
      }
    };
    loadEvent();
  }, [id, navigate, toast]);

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
        title: 'Înscriere reușită!',
        description: 'Te-ai înscris cu succes la acest eveniment.',
        variant: 'success' as const,
      });
    } catch (error: unknown) {
      setEvent(previous);
      const axiosError = error as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Eroare',
        description: axiosError.response?.data?.detail || 'Nu am putut finaliza înscrierea',
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
        title: 'Dezabonare reușită',
        description: 'Te-ai dezabonat de la acest eveniment.',
      });
    } catch (error: unknown) {
      setEvent(previous);
      const axiosError = error as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Eroare',
        description: axiosError.response?.data?.detail || 'Nu am putut finaliza dezabonarea',
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
        title: 'Email trimis',
        description: 'Am retrimis emailul de confirmare pentru acest eveniment.',
        variant: 'success' as const,
      });
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Eroare',
        description: axiosError.response?.data?.detail || 'Nu am putut retrimite emailul',
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
        title: 'Eroare',
        description: 'Nu am putut actualiza favoritele',
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
      } catch {
        // User cancelled
      }
    } else {
      await navigator.clipboard.writeText(url);
      toast({
        title: 'Link copiat!',
        description: 'Link-ul a fost copiat în clipboard.',
      });
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
        title: 'Eveniment duplicat!',
        description: 'Vei fi redirecționat către pagina de editare.',
        variant: 'success' as const,
      });
      // Navigate to edit the cloned event
      navigate(`/organizer/events/${clonedEvent.id}/edit`);
    } catch (error: unknown) {
      const axiosError = error as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Eroare',
        description: axiosError.response?.data?.detail || 'Nu am putut duplica evenimentul',
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
        Înapoi
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
              {event.status === 'draft' && <Badge variant="secondary">Draft</Badge>}
              {isPast && <Badge variant="secondary">Încheiat</Badge>}
              {isFull && !isPast && <Badge variant="destructive">Complet</Badge>}
            </div>
          </div>

          {/* Title & Category */}
          <div className="mb-6">
            {event.category && (
              <Badge variant="outline" className="mb-2">
                {event.category}
              </Badge>
            )}
            <h1 className="text-3xl font-bold">{event.title}</h1>
          </div>

          {/* Quick Info */}
          <div className="mb-6 grid gap-4 sm:grid-cols-2">
            <div className="flex items-center gap-3 rounded-lg border p-4">
              <Calendar className="h-5 w-5 text-primary" />
              <div>
                <p className="text-sm text-muted-foreground">Data</p>
                <p className="font-medium">{formatDate(event.start_time)}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-lg border p-4">
              <Clock className="h-5 w-5 text-primary" />
              <div>
                <p className="text-sm text-muted-foreground">Ora</p>
                <p className="font-medium">
                  {new Date(event.start_time).toLocaleTimeString('ro-RO', {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                  {event.end_time &&
                    ` - ${new Date(event.end_time).toLocaleTimeString('ro-RO', {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}`}
                </p>
              </div>
            </div>
            {(event.city || event.location) && (
              <div className="flex items-center gap-3 rounded-lg border p-4">
                <MapPin className="h-5 w-5 text-primary" />
                <div>
                  <p className="text-sm text-muted-foreground">Locație</p>
                  <p className="font-medium">
                    {[event.city, event.location].filter(Boolean).join(' • ')}
                  </p>
                </div>
              </div>
            )}
            <div className="flex items-center gap-3 rounded-lg border p-4">
              <Users className="h-5 w-5 text-primary" />
              <div>
                <p className="text-sm text-muted-foreground">Participanți</p>
                <p className="font-medium">
                  {event.seats_taken}
                  {event.max_seats && ` / ${event.max_seats}`} locuri ocupate
                </p>
              </div>
            </div>
          </div>

          <Separator className="my-6" />

          {/* Description */}
          <div className="mb-6">
            <h2 className="mb-4 text-xl font-semibold">Descriere</h2>
            <div className="prose prose-neutral dark:prose-invert max-w-none">
              {event.description ? (
                <p className="whitespace-pre-wrap">{event.description}</p>
              ) : (
                <p className="text-muted-foreground">
                  Nu există o descriere pentru acest eveniment.
                </p>
              )}
            </div>
          </div>

          {/* Tags */}
          {event.tags.length > 0 && (
            <div className="mb-6">
              <h2 className="mb-4 text-xl font-semibold">Etichete</h2>
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
              <h3 className="mb-4 text-lg font-semibold">Înregistrare</h3>

              {event.is_owner ? (
                <div className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    Ești organizatorul acestui eveniment.
                  </p>
                  <Button asChild className="w-full">
                    <Link to={`/organizer/events/${event.id}/edit`}>
                      Editează evenimentul
                    </Link>
                  </Button>
                  <Button asChild variant="outline" className="w-full">
                    <Link to={`/organizer/events/${event.id}/participants`}>
                      Vezi participanții
                    </Link>
                  </Button>
                  <Button 
                    variant="outline" 
                    className="w-full"
                    onClick={handleClone}
                    disabled={isCloning}
                  >
                    <Copy className="mr-2 h-4 w-4" />
                    {isCloning ? 'Se duplică...' : 'Duplică evenimentul'}
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  {event.is_registered ? (
                    <>
                      <div className="rounded-lg bg-green-50 p-4 text-center dark:bg-green-900/20">
                        <p className="font-medium text-green-700 dark:text-green-400">
                          ✓ Ești înscris la acest eveniment
                        </p>
                      </div>
                      <Button
                        variant="secondary"
                        className="w-full"
                        onClick={handleResendRegistrationEmail}
                        disabled={isResendingEmail}
                      >
                        {isResendingEmail ? 'Se trimite...' : 'Retrimite email de confirmare'}
                      </Button>
                      {!isPast && (
                        <Button
                          variant="outline"
                          className="w-full"
                          onClick={handleUnregister}
                          disabled={isRegistering}
                        >
                          Dezabonare
                        </Button>
                      )}
                    </>
                  ) : isPast ? (
                    <p className="text-center text-muted-foreground">
                      Acest eveniment s-a încheiat
                    </p>
                  ) : isFull ? (
                    <p className="text-center text-destructive">
                      Nu mai sunt locuri disponibile
                    </p>
                  ) : (
                    <Button
                      className="w-full"
                      onClick={handleRegister}
                      disabled={isRegistering}
                    >
                      {isRegistering ? 'Se înscrie...' : 'Înscrie-te la eveniment'}
                    </Button>
                  )}

                  {/* Available Seats */}
                  {typeof event.available_seats === 'number' && !isPast && (
                    <p className="text-center text-sm text-muted-foreground">
                      {event.available_seats} locuri disponibile
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
                Adaugă în calendar
              </Button>
            </div>

            {/* Organizer Info */}
            <div className="rounded-xl border p-6">
              <h3 className="mb-4 text-lg font-semibold">Organizator</h3>
              <Link
                to={`/organizers/${event.owner_id}`}
                className="flex items-center gap-3 hover:underline"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                  <User className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="font-medium">{event.owner_name || 'Organizator'}</p>
                  <p className="text-sm text-muted-foreground">Vezi profilul</p>
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
