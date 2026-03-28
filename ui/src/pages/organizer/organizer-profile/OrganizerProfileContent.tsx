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

type BackToEventsButtonProps = {
  label: string;
  className?: string;
};

type OrganizerContactLinksProps = {
  email?: string | null;
  website?: string | null;
  websiteLabel: string;
};

type OrganizerStatsProps = {
  totalEvents: number;
  upcomingCount: number;
  pastCount: number;
  labels: LoadedController['t']['organizerProfile']['stats'];
};

/** Renders the shared back-to-events call to action. */
function BackToEventsButton({ label, className }: BackToEventsButtonProps) {
  return (
    <Button variant="ghost" className={className} asChild>
      <Link to="/events">
        <ArrowLeft className="mr-2 h-4 w-4" />
        {label}
      </Link>
    </Button>
  );
}

/** Renders the organizer email and website links when they are available. */
function OrganizerContactLinks({ email, website, websiteLabel }: OrganizerContactLinksProps) {
  return (
    <div className="flex flex-wrap justify-center gap-4 md:justify-start">
      {email ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Mail className="h-4 w-4" />
          <a href={`mailto:${email}`} className="hover:text-primary">
            {email}
          </a>
        </div>
      ) : null}

      {website ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <ExternalLink className="h-4 w-4" />
          <a href={website} target="_blank" rel="noopener noreferrer" className="hover:text-primary">
            {websiteLabel}
          </a>
        </div>
      ) : null}
    </div>
  );
}

/** Renders the organizer summary badges. */
function OrganizerStats({ totalEvents, upcomingCount, pastCount, labels }: OrganizerStatsProps) {
  return (
    <div className="mt-4 flex flex-wrap justify-center gap-4 md:justify-start">
      <Badge variant="secondary" className="text-sm">
        <CalendarDays className="mr-1 h-4 w-4" />
        {totalEvents} {labels.events}
      </Badge>
      <Badge variant="secondary" className="text-sm">
        <Calendar className="mr-1 h-4 w-4" />
        {upcomingCount} {labels.upcoming}
      </Badge>
      <Badge variant="outline" className="text-sm">
        <History className="mr-1 h-4 w-4" />
        {pastCount} {labels.past}
      </Badge>
    </div>
  );
}

/** Renders the organizer fallback state when the profile is missing or fails to load. */
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
          <BackToEventsButton label={controller.t.organizerProfile.backToEvents} />
        </CardContent>
      </Card>
    </div>
  );
}

/** Renders the organizer hero card for a loaded profile. */
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

            <OrganizerContactLinks
              email={profile.email}
              website={profile.org_website}
              websiteLabel={controller.t.organizerProfile.website}
            />
            <OrganizerStats
              totalEvents={profile.events.length}
              upcomingCount={controller.upcomingEvents.length}
              pastCount={controller.pastEvents.length}
              labels={controller.t.organizerProfile.stats}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

/** Renders the empty-state card for a tab that has no events to show. */
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

/** Renders the organizer event cards for a given tab. */
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

/** Renders the tabbed organizer event sections for upcoming, past, and all events. */
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

/** Renders the organizer profile page once the controller has finished loading. */
export function OrganizerProfileContent({ controller }: Props) {
  const { profile } = controller;
  if (controller.hasError || !profile) {
    return <NotFoundState controller={controller} />;
  }

  const loadedController = { ...controller, profile };

  return (
    <div className="container mx-auto px-4 py-8">
      <BackToEventsButton label={controller.t.organizerProfile.backToEvents} className="mb-6" />

      <OrganizerHeader controller={loadedController} />
      <OrganizerEventsTabs controller={loadedController} />
    </div>
  );
}
