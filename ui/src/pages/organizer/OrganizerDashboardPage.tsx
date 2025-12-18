import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import eventService from '@/services/event.service';
import type { Event } from '@/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { LoadingPage } from '@/components/ui/loading';
import { useToast } from '@/hooks/use-toast';
import { useI18n } from '@/contexts/LanguageContext';
import {
  Plus,
  Calendar,
  Users,
  Eye,
  Edit,
  Trash2,
  MoreHorizontal,
  CalendarDays,
  UserCheck,
  Clock,
} from 'lucide-react';
import { formatDate } from '@/lib/utils';
import { getEventCategoryLabel } from '@/lib/eventCategories';

export function OrganizerDashboardPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const { toast } = useToast();
  const { language, t } = useI18n();

  const loadEvents = useCallback(async () => {
    setIsLoading(true);
    try {
      const events = await eventService.getOrganizerEvents();
      setEvents(events);
    } catch {
      toast({
        title: t.organizerDashboard.loadErrorTitle,
        description: t.organizerDashboard.loadErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [t, toast]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  const handleDelete = async (eventId: number) => {
    if (!confirm(t.organizerDashboard.deleteConfirm)) return;

    try {
      await eventService.deleteEvent(eventId);
      setEvents((prev) => prev.filter((e) => e.id !== eventId));
      toast({
        title: t.organizerDashboard.deleteSuccessTitle,
        description: t.organizerDashboard.deleteSuccessDescription,
      });
    } catch {
      toast({
        title: t.organizerDashboard.deleteErrorTitle,
        description: t.organizerDashboard.deleteErrorDescription,
        variant: 'destructive',
      });
    }
  };

  if (isLoading) {
    return <LoadingPage message={t.organizerDashboard.loading} />;
  }

  const now = new Date();
  const upcomingEvents = events.filter((e) => new Date(e.start_time) >= now);
  const totalParticipants = events.reduce((acc, e) => acc + e.seats_taken, 0);
  const draftEvents = events.filter((e) => e.status === 'draft');

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t.organizerDashboard.title}</h1>
          <p className="mt-2 text-muted-foreground">
            {t.organizerDashboard.subtitle}
          </p>
        </div>
        <Button asChild>
          <Link to="/organizer/events/new">
            <Plus className="mr-2 h-4 w-4" />
            {t.organizerDashboard.newEvent}
          </Link>
        </Button>
      </div>

      {/* Stats */}
      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">{t.organizerDashboard.statsTotalEvents}</CardTitle>
            <CalendarDays className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{events.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">{t.organizerDashboard.statsUpcomingEvents}</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{upcomingEvents.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">{t.organizerDashboard.statsTotalParticipants}</CardTitle>
            <UserCheck className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalParticipants}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">{t.organizerDashboard.statsDrafts}</CardTitle>
            <Edit className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{draftEvents.length}</div>
          </CardContent>
        </Card>
      </div>

      {/* Events Table */}
      <Card>
        <CardHeader>
          <CardTitle>{t.organizerDashboard.tableTitle}</CardTitle>
        </CardHeader>
        <CardContent>
          {events.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Calendar className="mb-4 h-12 w-12 text-muted-foreground" />
              <h3 className="text-lg font-semibold">{t.organizerDashboard.emptyTitle}</h3>
              <p className="mt-2 text-muted-foreground">
                {t.organizerDashboard.emptyDescription}
              </p>
              <Button asChild className="mt-4">
                <Link to="/organizer/events/new">
                  <Plus className="mr-2 h-4 w-4" />
                  {t.organizerDashboard.emptyCreateButton}
                </Link>
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t.organizerDashboard.tableHeaderTitle}</TableHead>
                  <TableHead>{t.organizerDashboard.tableHeaderDate}</TableHead>
                  <TableHead>{t.organizerDashboard.tableHeaderParticipants}</TableHead>
                  <TableHead>{t.organizerDashboard.tableHeaderStatus}</TableHead>
                  <TableHead className="w-[70px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((event) => {
                  const isPast = new Date(event.start_time) < now;
                  const categoryLabel = getEventCategoryLabel(event.category, language);
                  return (
                    <TableRow key={event.id}>
                      <TableCell>
                        <Link
                          to={`/events/${event.id}`}
                          className="font-medium hover:underline"
                        >
                          {event.title}
                        </Link>
                        {categoryLabel && (
                          <span className="ml-2 text-sm text-muted-foreground">
                            ({categoryLabel})
                          </span>
                        )}
                      </TableCell>
                      <TableCell>{formatDate(event.start_time, language)}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Users className="h-4 w-4 text-muted-foreground" />
                          {event.seats_taken}
                          {event.max_seats && ` / ${event.max_seats}`}
                        </div>
                      </TableCell>
                      <TableCell>
                        {event.status === 'draft' ? (
                          <Badge variant="secondary">{t.organizerDashboard.statusDraft}</Badge>
                        ) : isPast ? (
                          <Badge variant="outline">{t.organizerDashboard.statusEnded}</Badge>
                        ) : (
                          <Badge variant="default">{t.organizerDashboard.statusActive}</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem asChild>
                              <Link to={`/events/${event.id}`}>
                                <Eye className="mr-2 h-4 w-4" />
                                {t.organizerDashboard.actionView}
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem asChild>
                              <Link to={`/organizer/events/${event.id}/edit`}>
                                <Edit className="mr-2 h-4 w-4" />
                                {t.organizerDashboard.actionEdit}
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem asChild>
                              <Link to={`/organizer/events/${event.id}/participants`}>
                                <Users className="mr-2 h-4 w-4" />
                                {t.organizerDashboard.actionParticipants}
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-destructive"
                              onClick={() => handleDelete(event.id)}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              {t.organizerDashboard.actionDelete}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
