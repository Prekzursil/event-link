import { Edit, RotateCcw, ShieldCheck, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { LoadingPage } from '@/components/ui/loading';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { formatDateTime } from '@/lib/utils';
import { RefreshCw } from 'lucide-react';
import { getModerationPresentation } from './shared';
import type { AdminDashboardController } from './useAdminDashboardController';

type Props = {
  controller: AdminDashboardController;
};

export function AdminEventsTab({ controller }: Props) {
  const {
    events,
    eventsFlaggedOnly,
    eventsIncludeDeleted,
    eventsPage,
    eventsSearch,
    eventsStatus,
    eventsTotal,
    handleDeleteEvent,
    handleRestoreEvent,
    handleReviewEvent,
    isLoadingEvents,
    language,
    loadEvents,
    reviewingEventId,
    setEventsFlaggedOnly,
    setEventsIncludeDeleted,
    setEventsSearch,
    setEventsStatus,
    t,
    totalEventPages,
  } = controller;

  return (
    <div className="mt-6 space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t.adminDashboard.events.title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end">
            <div className="flex-1">
              <label className="mb-1 block text-sm font-medium">{t.adminDashboard.events.searchLabel}</label>
              <Input
                value={eventsSearch}
                onChange={(event) => setEventsSearch(event.target.value)}
                placeholder={t.adminDashboard.events.searchPlaceholder}
              />
            </div>
            <div className="w-full md:w-56">
              <label className="mb-1 block text-sm font-medium">{t.adminDashboard.events.statusLabel}</label>
              <Select value={eventsStatus} onValueChange={(value) => setEventsStatus(value as 'all' | 'draft' | 'published')}>
                <SelectTrigger>
                  <SelectValue placeholder={t.adminDashboard.events.statusAll} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t.adminDashboard.events.statusAll}</SelectItem>
                  <SelectItem value="published">{t.adminDashboard.events.statusPublished}</SelectItem>
                  <SelectItem value="draft">{t.adminDashboard.events.statusDraft}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                checked={eventsIncludeDeleted}
                onCheckedChange={(checked) => setEventsIncludeDeleted(Boolean(checked))}
              />
              <span className="text-sm">{t.adminDashboard.events.includeDeleted}</span>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                checked={eventsFlaggedOnly}
                onCheckedChange={(checked) => setEventsFlaggedOnly(Boolean(checked))}
              />
              <span className="text-sm">{t.adminDashboard.events.flaggedOnly}</span>
            </div>
            <Button onClick={() => loadEvents(1)} disabled={isLoadingEvents}>
              <RefreshCw className="mr-2 h-4 w-4" />
              {t.adminDashboard.events.apply}
            </Button>
          </div>

          {isLoadingEvents ? (
            <LoadingPage message={t.adminDashboard.events.loading} />
          ) : events.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t.adminDashboard.events.empty}</p>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t.adminDashboard.events.table.title}</TableHead>
                    <TableHead>{t.adminDashboard.events.table.city}</TableHead>
                    <TableHead>{t.adminDashboard.events.table.date}</TableHead>
                    <TableHead>{t.adminDashboard.events.table.owner}</TableHead>
                    <TableHead>{t.adminDashboard.events.table.status}</TableHead>
                    <TableHead>{t.adminDashboard.events.table.moderation}</TableHead>
                    <TableHead className="text-right">{t.adminDashboard.events.table.seats}</TableHead>
                    <TableHead className="w-[160px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {events.map((event) => {
                    const deleted = Boolean(event.deleted_at);
                    const moderationStatus = event.moderation_status || 'clean';
                    const moderation = getModerationPresentation(
                      moderationStatus,
                      t.adminDashboard.events.moderation,
                    );
                    const isReviewingCurrent = reviewingEventId === event.id;
                    const reviewActionLabel = isReviewingCurrent
                      ? t.adminDashboard.events.moderation.reviewing
                      : t.adminDashboard.events.moderation.markReviewed;

                    return (
                      <TableRow key={event.id} className={deleted ? 'opacity-70' : undefined}>
                        <TableCell>
                          <Link to={`/events/${event.id}`} className="font-medium hover:underline">
                            {event.title}
                          </Link>
                          {deleted && (
                            <Badge className="ml-2" variant="destructive">
                              {t.adminDashboard.events.deletedBadge}
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>{event.city || '-'}</TableCell>
                        <TableCell>{formatDateTime(event.start_time, language)}</TableCell>
                        <TableCell>
                          <div className="text-sm">{event.owner_email}</div>
                          {event.owner_name && <div className="text-xs text-muted-foreground">{event.owner_name}</div>}
                        </TableCell>
                        <TableCell>
                          <Badge variant={event.status === 'draft' ? 'secondary' : 'default'}>
                            {event.status === 'draft'
                              ? t.adminDashboard.events.statusDraft
                              : t.adminDashboard.events.statusPublished}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="space-y-1">
                            <Badge variant={moderation.variant}>{moderation.label}</Badge>
                            {typeof event.moderation_score === 'number' && (
                              <div className="text-xs text-muted-foreground">
                                {t.adminDashboard.events.moderation.scoreLabel} {event.moderation_score.toFixed(2)}
                              </div>
                            )}
                            {event.moderation_flags?.length ? (
                              <div className="text-xs text-muted-foreground">
                                {event.moderation_flags.slice(0, 3).join(', ')}
                                {event.moderation_flags.length > 3 ? '…' : ''}
                              </div>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          {event.seats_taken}/{event.max_seats ?? '-'}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button asChild variant="outline" size="sm" disabled={deleted}>
                              <Link to={`/organizer/events/${event.id}/edit`}>
                                <Edit className="mr-2 h-4 w-4" />
                                {t.adminDashboard.events.actions.edit}
                              </Link>
                            </Button>
                            {moderationStatus === 'flagged' && !deleted && (
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={isReviewingCurrent}
                                onClick={() => handleReviewEvent(event.id)}
                              >
                                <ShieldCheck className="mr-2 h-4 w-4" />
                                {reviewActionLabel}
                              </Button>
                            )}
                            {deleted ? (
                              <Button variant="outline" size="sm" onClick={() => handleRestoreEvent(event.id)}>
                                <RotateCcw className="mr-2 h-4 w-4" />
                                {t.adminDashboard.events.actions.restore}
                              </Button>
                            ) : (
                              <Button variant="destructive" size="sm" onClick={() => handleDeleteEvent(event.id)}>
                                <Trash2 className="mr-2 h-4 w-4" />
                                {t.adminDashboard.events.actions.delete}
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>

              <div className="mt-4 flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {t.adminDashboard.pagination.page} {eventsPage} / {totalEventPages} • {t.adminDashboard.pagination.total} {eventsTotal}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={eventsPage <= 1}
                    onClick={() => loadEvents(eventsPage - 1)}
                  >
                    {t.adminDashboard.pagination.prev}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={eventsPage >= totalEventPages}
                    onClick={() => loadEvents(eventsPage + 1)}
                  >
                    {t.adminDashboard.pagination.next}
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
