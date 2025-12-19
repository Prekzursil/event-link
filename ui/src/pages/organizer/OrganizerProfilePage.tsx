import { useState, useEffect, useCallback } from 'react';
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
import { useI18n } from '@/contexts/LanguageContext';
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
  const [hasError, setHasError] = useState(false);
  const { t } = useI18n();

  const loadProfile = useCallback(
    async (organizerId: number) => {
      setIsLoading(true);
      setHasError(false);
      try {
        const data = await eventService.getOrganizerProfile(organizerId);
        setProfile(data);
      } catch (err) {
        console.error('Failed to load organizer profile:', err);
        setHasError(true);
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    if (id) {
      loadProfile(parseInt(id));
    }
  }, [id, loadProfile]);

  if (isLoading) {
    return <LoadingPage message={t.organizerProfile.loading} />;
  }

  if (hasError || !profile) {
    return (
      <div className="container mx-auto px-4 py-16">
        <Card className="mx-auto max-w-md">
          <CardContent className="pt-6 text-center">
            <Building2 className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
            <h2 className="mb-2 text-xl font-semibold">{t.organizerProfile.notFoundTitle}</h2>
            <p className="mb-4 text-muted-foreground">
              {hasError ? t.organizerProfile.loadErrorDescription : t.organizerProfile.notFoundDescription}
            </p>
            <Button asChild>
              <Link to="/events">
                <ArrowLeft className="mr-2 h-4 w-4" />
                {t.organizerProfile.backToEvents}
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

  const displayName = profile.org_name || profile.full_name || t.organizerProfile.organizerFallback;
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
          {t.organizerProfile.backToEvents}
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
                      {t.organizerProfile.website}
                    </a>
                  </div>
                )}
              </div>

              {/* Stats */}
              <div className="mt-4 flex flex-wrap justify-center gap-4 md:justify-start">
                <Badge variant="secondary" className="text-sm">
                  <CalendarDays className="mr-1 h-4 w-4" />
                  {profile.events.length} {t.organizerProfile.stats.events}
                </Badge>
                <Badge variant="secondary" className="text-sm">
                  <Calendar className="mr-1 h-4 w-4" />
                  {upcomingEvents.length} {t.organizerProfile.stats.upcoming}
                </Badge>
                <Badge variant="outline" className="text-sm">
                  <History className="mr-1 h-4 w-4" />
                  {pastEvents.length} {t.organizerProfile.stats.past}
                </Badge>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Events Tabs */}
      <Tabs defaultValue="upcoming" className="w-full">
        <TabsList className="mb-6 h-auto w-full flex flex-wrap justify-start">
          <TabsTrigger value="upcoming" className="gap-2">
            <Calendar className="h-4 w-4" />
            {t.organizerProfile.tabs.upcoming} ({upcomingEvents.length})
          </TabsTrigger>
          <TabsTrigger value="past" className="gap-2">
            <History className="h-4 w-4" />
            {t.organizerProfile.tabs.past} ({pastEvents.length})
          </TabsTrigger>
          <TabsTrigger value="all" className="gap-2">
            <CalendarDays className="h-4 w-4" />
            {t.organizerProfile.tabs.all} ({profile.events.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="upcoming">
          {upcomingEvents.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <Calendar className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
                <h3 className="mb-2 text-lg font-medium">{t.organizerProfile.emptyUpcomingTitle}</h3>
                <p className="text-muted-foreground">
                  {t.organizerProfile.emptyUpcomingDescription}
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
                <h3 className="mb-2 text-lg font-medium">{t.organizerProfile.emptyPastTitle}</h3>
                <p className="text-muted-foreground">
                  {t.organizerProfile.emptyPastDescription}
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
                <h3 className="mb-2 text-lg font-medium">{t.organizerProfile.emptyAllTitle}</h3>
                <p className="text-muted-foreground">
                  {t.organizerProfile.emptyAllDescription}
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
