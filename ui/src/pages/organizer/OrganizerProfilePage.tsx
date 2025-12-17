import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import eventService from '@/services/event.service';
import type { OrganizerProfile } from '@/types';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { LoadingPage } from '@/components/ui/loading';
import { EventCard } from '@/components/events/EventCard';
import {
  Calendar,
  ExternalLink,
  Mail,
  Building2,
  CalendarDays,
  History,
  ArrowLeft,
} from 'lucide-react';
import { isPast } from 'date-fns';

export function OrganizerProfilePage() {
  const { id } = useParams<{ id: string }>();
  const [profile, setProfile] = useState<OrganizerProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      loadProfile(parseInt(id));
    }
  }, [id]);

  const loadProfile = async (organizerId: number) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await eventService.getOrganizerProfile(organizerId);
      setProfile(data);
    } catch (err) {
      console.error('Failed to load organizer profile:', err);
      setError('Nu am putut încărca profilul organizatorului');
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return <LoadingPage message="Se încarcă profilul..." />;
  }

  if (error || !profile) {
    return (
      <div className="container mx-auto px-4 py-16">
        <Card className="mx-auto max-w-md">
          <CardContent className="pt-6 text-center">
            <Building2 className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
            <h2 className="mb-2 text-xl font-semibold">Organizator negăsit</h2>
            <p className="mb-4 text-muted-foreground">
              {error || 'Acest organizator nu există sau nu mai este disponibil.'}
            </p>
            <Button asChild>
              <Link to="/events">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Înapoi la evenimente
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Separate events into upcoming and past
  const now = new Date();
  const upcomingEvents = profile.events.filter(
    (event) => new Date(event.start_time) >= now
  );
  const pastEvents = profile.events.filter(
    (event) => new Date(event.start_time) < now
  );

  const displayName = profile.org_name || profile.full_name || 'Organizator';
  const initials = displayName
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Back Button */}
      <Button variant="ghost" className="mb-6" asChild>
        <Link to="/events">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Înapoi la evenimente
        </Link>
      </Button>

      {/* Profile Header */}
      <Card className="mb-8">
        <CardContent className="pt-6">
          <div className="flex flex-col items-center gap-6 md:flex-row md:items-start">
            {/* Avatar */}
            <Avatar className="h-24 w-24 md:h-32 md:w-32">
              <AvatarImage src={profile.org_logo_url} alt={displayName} />
              <AvatarFallback className="text-2xl">{initials}</AvatarFallback>
            </Avatar>

            {/* Info */}
            <div className="flex-1 text-center md:text-left">
              <h1 className="mb-2 text-2xl font-bold md:text-3xl">{displayName}</h1>
              
              {profile.org_description && (
                <p className="mb-4 text-muted-foreground">{profile.org_description}</p>
              )}

              <div className="flex flex-wrap justify-center gap-4 md:justify-start">
                {profile.email && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Mail className="h-4 w-4" />
                    <a href={`mailto:${profile.email}`} className="hover:text-primary">
                      {profile.email}
                    </a>
                  </div>
                )}
                
                {profile.org_website && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <ExternalLink className="h-4 w-4" />
                    <a 
                      href={profile.org_website} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="hover:text-primary"
                    >
                      Website
                    </a>
                  </div>
                )}
              </div>

              {/* Stats */}
              <div className="mt-4 flex flex-wrap justify-center gap-4 md:justify-start">
                <Badge variant="secondary" className="text-sm">
                  <CalendarDays className="mr-1 h-4 w-4" />
                  {profile.events.length} evenimente
                </Badge>
                <Badge variant="secondary" className="text-sm">
                  <Calendar className="mr-1 h-4 w-4" />
                  {upcomingEvents.length} viitoare
                </Badge>
                <Badge variant="outline" className="text-sm">
                  <History className="mr-1 h-4 w-4" />
                  {pastEvents.length} trecute
                </Badge>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Events Tabs */}
      <Tabs defaultValue="upcoming" className="w-full">
        <TabsList className="mb-6">
          <TabsTrigger value="upcoming" className="gap-2">
            <Calendar className="h-4 w-4" />
            Viitoare ({upcomingEvents.length})
          </TabsTrigger>
          <TabsTrigger value="past" className="gap-2">
            <History className="h-4 w-4" />
            Trecute ({pastEvents.length})
          </TabsTrigger>
          <TabsTrigger value="all" className="gap-2">
            <CalendarDays className="h-4 w-4" />
            Toate ({profile.events.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="upcoming">
          {upcomingEvents.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <Calendar className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
                <h3 className="mb-2 text-lg font-medium">Niciun eveniment viitor</h3>
                <p className="text-muted-foreground">
                  Acest organizator nu are evenimente programate în viitor.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {upcomingEvents.map((event) => (
                <EventCard key={event.id} event={event} />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="past">
          {pastEvents.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <History className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
                <h3 className="mb-2 text-lg font-medium">Niciun eveniment trecut</h3>
                <p className="text-muted-foreground">
                  Acest organizator nu are evenimente trecute.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {pastEvents.map((event) => (
                <EventCard key={event.id} event={event} isPast />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="all">
          {profile.events.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <CalendarDays className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
                <h3 className="mb-2 text-lg font-medium">Niciun eveniment</h3>
                <p className="text-muted-foreground">
                  Acest organizator nu are evenimente.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {profile.events.map((event) => (
                <EventCard 
                  key={event.id} 
                  event={event} 
                  isPast={isPast(new Date(event.start_time))}
                />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default OrganizerProfilePage;
