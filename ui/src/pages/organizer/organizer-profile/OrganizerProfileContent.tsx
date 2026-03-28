import { Link } from 'react-router-dom';
import { isPast } from 'date-fns';
import { ArrowLeft, Building2, Calendar, CalendarDays, ExternalLink, History, Mail } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { EventCard } from '@/components/events/EventCard';
import type { OrganizerProfileController } from './useOrganizerProfileController';

type Props = {
  controller: OrganizerProfileController;
};

type LoadedController = OrganizerProfileController & {
  profile: NonNullable<OrganizerProfileController['profile']>;
};

function NotFoundState({ controller }: Props) {
  return (
    <div className="container mx-auto px-4 py-16">
      <Card className="mx-auto max-w-md">
        <CardContent className="pt-6 text-center">
          <Building2 className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
          <h2 className="mb-2 text-xl font-semibold">{controller.t.organizerProfile.notFoundTitle}</h2>
          <p className="mb-4 text-muted-foreground">
            {controller.hasError
              ? controller.t.organizerProfile.loadErrorDescription
              : controller.t.organizerProfile.notFoundDescription}
          </p>
          <Button asChild>
            <Link to="/events">
              <ArrowLeft className="mr-2 h-4 w-4" />
              {controller.t.organizerProfile.backToEvents}
            </Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function OrganizerHeader({ controller }: { controller: LoadedController }) {
  const { profile } = controller;

  return (
    <Card className="mb-8">
      <CardContent className="pt-6">
        <div className="flex flex-col items-center gap-6 md:flex-row md:items-start">
          <Avatar className="h-24 w-24 md:h-32 md:w-32">
            <AvatarImage src={profile.org_logo_url} alt={controller.organizerDisplayName} />
            <AvatarFallback className="text-2xl">{controller.initials}</AvatarFallback>
          </Avatar>

          <div className="flex-1 text-center md:text-left">
            <h1 className="mb-2 text-2xl font-bold md:text-3xl">{controller.organizerDisplayName}</h1>

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
                    {controller.t.organizerProfile.website}
                  </a>
                </div>
              )}
            </div>

            <div className="mt-4 flex flex-wrap justify-center gap-4 md:justify-start">
              <Badge variant="secondary" className="text-sm">
                <CalendarDays className="mr-1 h-4 w-4" />
                {profile.events.length} {controller.t.organizerProfile.stats.events}
              </Badge>
              <Badge variant="secondary" className="text-sm">
                <Calendar className="mr-1 h-4 w-4" />
                {controller.upcomingEvents.length} {controller.t.organizerProfile.stats.upcoming}
              </Badge>
              <Badge variant="outline" className="text-sm">
                <History className="mr-1 h-4 w-4" />
                {controller.pastEvents.length} {controller.t.organizerProfile.stats.past}
              </Badge>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyEventsState({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof Calendar;
  title: string;
  description: string;
}) {
  return (
    <Card>
      <CardContent className="py-12 text-center">
        <Icon className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
        <h3 className="mb-2 text-lg font-medium">{title}</h3>
        <p className="text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}

function EventsGrid({
  events,
  showPastState = false,
}: {
  events: OrganizerProfileController['upcomingEvents'];
  showPastState?: boolean;
}) {
  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      {events.map((event) => (
        <EventCard key={event.id} event={event} isPast={showPastState || isPast(new Date(event.start_time))} />
      ))}
    </div>
  );
}

function OrganizerEventsTabs({ controller }: { controller: LoadedController }) {
  const { profile } = controller;

  return (
    <Tabs defaultValue="upcoming" className="w-full">
      <TabsList className="mb-6 h-auto w-full flex flex-wrap justify-start">
        <TabsTrigger value="upcoming" className="gap-2">
          <Calendar className="h-4 w-4" />
          {controller.t.organizerProfile.tabs.upcoming} ({controller.upcomingEvents.length})
        </TabsTrigger>
        <TabsTrigger value="past" className="gap-2">
          <History className="h-4 w-4" />
          {controller.t.organizerProfile.tabs.past} ({controller.pastEvents.length})
        </TabsTrigger>
        <TabsTrigger value="all" className="gap-2">
          <CalendarDays className="h-4 w-4" />
          {controller.t.organizerProfile.tabs.all} ({profile.events.length})
        </TabsTrigger>
      </TabsList>

      <TabsContent value="upcoming">
        {controller.upcomingEvents.length === 0 ? (
          <EmptyEventsState
            icon={Calendar}
            title={controller.t.organizerProfile.emptyUpcomingTitle}
            description={controller.t.organizerProfile.emptyUpcomingDescription}
          />
        ) : (
          <EventsGrid events={controller.upcomingEvents} />
        )}
      </TabsContent>

      <TabsContent value="past">
        {controller.pastEvents.length === 0 ? (
          <EmptyEventsState
            icon={History}
            title={controller.t.organizerProfile.emptyPastTitle}
            description={controller.t.organizerProfile.emptyPastDescription}
          />
        ) : (
          <EventsGrid events={controller.pastEvents} showPastState />
        )}
      </TabsContent>

      <TabsContent value="all">
        {profile.events.length === 0 ? (
          <EmptyEventsState
            icon={CalendarDays}
            title={controller.t.organizerProfile.emptyAllTitle}
            description={controller.t.organizerProfile.emptyAllDescription}
          />
        ) : (
          <EventsGrid events={profile.events} />
        )}
      </TabsContent>
    </Tabs>
  );
}

export function OrganizerProfileContent({ controller }: Props) {
  const { profile } = controller;
  if (controller.hasError || !profile) {
    return <NotFoundState controller={controller} />;
  }

  const loadedController = { ...controller, profile };

  return (
    <div className="container mx-auto px-4 py-8">
      <Button variant="ghost" className="mb-6" asChild>
        <Link to="/events">
          <ArrowLeft className="mr-2 h-4 w-4" />
          {controller.t.organizerProfile.backToEvents}
        </Link>
      </Button>

      <OrganizerHeader controller={loadedController} />
      <OrganizerEventsTabs controller={loadedController} />
    </div>
  );
}
