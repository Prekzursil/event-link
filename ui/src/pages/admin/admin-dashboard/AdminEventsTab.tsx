import type { AdminEvent } from '@/types';
import { Edit, RefreshCw, RotateCcw, ShieldCheck, Trash2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { LoadingPage } from '@/components/ui/loading';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { formatDateTime } from '@/lib/utils';
import { getModerationPresentation } from './shared';
import type { AdminDashboardController } from './useAdminDashboardController';

type Props = {
  controller: AdminDashboardController;
};

type EventsCopy = Props['controller']['t']['adminDashboard']['events'];
type PaginationCopy = Props['controller']['t']['adminDashboard']['pagination'];
type EventStatusFilter = Props['controller']['eventsStatus'];

type FilterToggleProps = {
  checked: boolean;
  label: string;
  onCheckedChange: (checked: boolean) => void;
};

type EventsFiltersBarProps = {
  applyLabel: string;
  eventsFlaggedOnly: boolean;
  eventsIncludeDeleted: boolean;
  eventsSearch: string;
  eventsStatus: EventStatusFilter;
  flaggedOnlyLabel: string;
  includeDeletedLabel: string;
  isLoadingEvents: boolean;
  onApply: () => void;
  onFlaggedOnlyChange: (checked: boolean) => void;
  onIncludeDeletedChange: (checked: boolean) => void;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: EventStatusFilter) => void;
  searchLabel: string;
  searchPlaceholder: string;
  statusAll: string;
  statusDraft: string;
  statusLabel: string;
  statusPublished: string;
};

type EventOwnerCellProps = {
  event: AdminEvent;
};

type EventStatusBadgeProps = {
  event: AdminEvent;
  labels: EventsCopy;
};

type EventModerationCellProps = {
  event: AdminEvent;
  labels: EventsCopy['moderation'];
};

type EventActionsProps = {
  deleted: boolean;
  eventId: number;
  labels: EventsCopy['actions'];
  moderationStatus: string;
  onDelete: (eventId: number) => void;
  onRestore: (eventId: number) => void;
  onReview: (eventId: number) => void;
  reviewActionLabel: string;
  reviewing: boolean;
};

type AdminEventRowProps = {
  event: AdminEvent;
  eventsCopy: EventsCopy;
  language: Props['controller']['language'];
  onDelete: (eventId: number) => void;
  onRestore: (eventId: number) => void;
  onReview: (eventId: number) => void;
  reviewingEventId: number | null;
};

type EventsPaginationProps = {
  copy: PaginationCopy;
  currentPage: number;
  onNext: () => void;
  onPrevious: () => void;
  totalItems: number;
  totalPages: number;
};

type EventsResultsProps = {
  events: AdminEvent[];
  eventsCopy: EventsCopy;
  eventsPage: number;
  eventsTotal: number;
  language: Props['controller']['language'];
  loadNextPage: () => void;
  loadPreviousPage: () => void;
  onDelete: (eventId: number) => void;
  onRestore: (eventId: number) => void;
  onReview: (eventId: number) => void;
  paginationCopy: PaginationCopy;
  reviewingEventId: number | null;
  totalEventPages: number;
};

/** Render a checkbox-style filter row for the admin events controls. */
const FilterToggle = ({ checked, label, onCheckedChange }: FilterToggleProps) => (
  <div className="flex items-center gap-2">
    <Checkbox checked={checked} onCheckedChange={(value) => onCheckedChange(Boolean(value))} />
    <span className="text-sm">{label}</span>
  </div>
);

/** Render the filter controls shown above the admin events table. */
const EventsFiltersBar = ({
  applyLabel,
  eventsFlaggedOnly,
  eventsIncludeDeleted,
  eventsSearch,
  eventsStatus,
  flaggedOnlyLabel,
  includeDeletedLabel,
  isLoadingEvents,
  onApply,
  onFlaggedOnlyChange,
  onIncludeDeletedChange,
  onSearchChange,
  onStatusChange,
  searchLabel,
  searchPlaceholder,
  statusAll,
  statusDraft,
  statusLabel,
  statusPublished,
}: EventsFiltersBarProps) => (
  <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end">
    <div className="flex-1">
      <label className="mb-1 block text-sm font-medium">{searchLabel}</label>
      <Input
        value={eventsSearch}
        onChange={(event) => onSearchChange(event.target.value)}
        placeholder={searchPlaceholder}
      />
    </div>
    <div className="w-full md:w-56">
      <label className="mb-1 block text-sm font-medium">{statusLabel}</label>
      <Select
        value={eventsStatus}
        onValueChange={(value) => onStatusChange(value as EventStatusFilter)}
      >
        <SelectTrigger>
          <SelectValue placeholder={statusAll} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">{statusAll}</SelectItem>
          <SelectItem value="published">{statusPublished}</SelectItem>
          <SelectItem value="draft">{statusDraft}</SelectItem>
        </SelectContent>
      </Select>
    </div>
    <FilterToggle
      checked={eventsIncludeDeleted}
      label={includeDeletedLabel}
      onCheckedChange={onIncludeDeletedChange}
    />
    <FilterToggle
      checked={eventsFlaggedOnly}
      label={flaggedOnlyLabel}
      onCheckedChange={onFlaggedOnlyChange}
    />
    <Button onClick={onApply} disabled={isLoadingEvents}>
      <RefreshCw className="mr-2 h-4 w-4" />
      {applyLabel}
    </Button>
  </div>
);

/** Render the organizer information for a single event row. */
const EventOwnerCell = ({ event }: EventOwnerCellProps) => (
  <TableCell>
    <div className="text-sm">{event.owner_email}</div>
    {event.owner_name && <div className="text-xs text-muted-foreground">{event.owner_name}</div>}
  </TableCell>
);

/** Render the published or draft badge for a single event row. */
const EventStatusBadge = ({ event, labels }: EventStatusBadgeProps) => (
  <Badge variant={event.status === 'draft' ? 'secondary' : 'default'}>
    {event.status === 'draft' ? labels.statusDraft : labels.statusPublished}
  </Badge>
);

/** Render moderation information for a single event row. */
const EventModerationCell = ({ event, labels }: EventModerationCellProps) => {
  const moderationStatus = event.moderation_status || 'clean';
  const moderation = getModerationPresentation(moderationStatus, labels);
  const visibleFlags = event.moderation_flags?.slice(0, 3) ?? [];
  const hasMoreFlags = (event.moderation_flags?.length ?? 0) > visibleFlags.length;

  return (
    <TableCell>
      <div className="space-y-1">
        <Badge variant={moderation.variant}>{moderation.label}</Badge>
        {typeof event.moderation_score === 'number' && (
          <div className="text-xs text-muted-foreground">
            {labels.scoreLabel} {event.moderation_score.toFixed(2)}
          </div>
        )}
        {visibleFlags.length > 0 && (
          <div className="text-xs text-muted-foreground">
            {visibleFlags.join(', ')}
            {hasMoreFlags ? '…' : ''}
          </div>
        )}
      </div>
    </TableCell>
  );
};

/** Render the action buttons for a single admin event row. */
const EventActions = ({
  deleted,
  eventId,
  labels,
  moderationStatus,
  onDelete,
  onRestore,
  onReview,
  reviewActionLabel,
  reviewing,
}: EventActionsProps) => (
  <div className="flex justify-end gap-2">
    <Button asChild variant="outline" size="sm" disabled={deleted}>
      <Link to={`/organizer/events/${eventId}/edit`}>
        <Edit className="mr-2 h-4 w-4" />
        {labels.edit}
      </Link>
    </Button>
    {moderationStatus === 'flagged' && !deleted && (
      <Button variant="outline" size="sm" disabled={reviewing} onClick={() => onReview(eventId)}>
        <ShieldCheck className="mr-2 h-4 w-4" />
        {reviewActionLabel}
      </Button>
    )}
    {deleted ? (
      <Button variant="outline" size="sm" onClick={() => onRestore(eventId)}>
        <RotateCcw className="mr-2 h-4 w-4" />
        {labels.restore}
      </Button>
    ) : (
      <Button variant="destructive" size="sm" onClick={() => onDelete(eventId)}>
        <Trash2 className="mr-2 h-4 w-4" />
        {labels.delete}
      </Button>
    )}
  </div>
);

/** Render a single event row in the admin events table. */
const AdminEventRow = ({
  event,
  eventsCopy,
  language,
  onDelete,
  onRestore,
  onReview,
  reviewingEventId,
}: AdminEventRowProps) => {
  const deleted = Boolean(event.deleted_at);
  const moderationStatus = event.moderation_status || 'clean';
  const reviewing = reviewingEventId === event.id;
  const reviewActionLabel = reviewing
    ? eventsCopy.moderation.reviewing
    : eventsCopy.moderation.markReviewed;

  return (
    <TableRow key={event.id} className={deleted ? 'opacity-70' : undefined}>
      <TableCell>
        <Link to={`/events/${event.id}`} className="font-medium hover:underline">
          {event.title}
        </Link>
        {deleted && (
          <Badge className="ml-2" variant="destructive">
            {eventsCopy.deletedBadge}
          </Badge>
        )}
      </TableCell>
      <TableCell>{event.city || '-'}</TableCell>
      <TableCell>{formatDateTime(event.start_time, language)}</TableCell>
      <EventOwnerCell event={event} />
      <TableCell>
        <EventStatusBadge event={event} labels={eventsCopy} />
      </TableCell>
      <EventModerationCell event={event} labels={eventsCopy.moderation} />
      <TableCell className="text-right">
        {event.seats_taken}/{event.max_seats ?? '-'}
      </TableCell>
      <TableCell className="text-right">
        <EventActions
          deleted={deleted}
          eventId={event.id}
          labels={eventsCopy.actions}
          moderationStatus={moderationStatus}
          onDelete={onDelete}
          onRestore={onRestore}
          onReview={onReview}
          reviewActionLabel={reviewActionLabel}
          reviewing={reviewing}
        />
      </TableCell>
    </TableRow>
  );
};

/** Render the shared pagination footer for the admin events tab. */
const EventsPagination = ({
  copy,
  currentPage,
  onNext,
  onPrevious,
  totalItems,
  totalPages,
}: EventsPaginationProps) => (
  <div className="mt-4 flex items-center justify-between">
    <p className="text-sm text-muted-foreground">
      {copy.page} {currentPage} / {totalPages} • {copy.total} {totalItems}
    </p>
    <div className="flex gap-2">
      <Button variant="outline" size="sm" disabled={currentPage <= 1} onClick={onPrevious}>
        {copy.prev}
      </Button>
      <Button variant="outline" size="sm" disabled={currentPage >= totalPages} onClick={onNext}>
        {copy.next}
      </Button>
    </div>
  </div>
);

/** Render the admin events table or its empty state. */
const EventsResults = ({
  events,
  eventsCopy,
  eventsPage,
  eventsTotal,
  language,
  loadNextPage,
  loadPreviousPage,
  onDelete,
  onRestore,
  onReview,
  paginationCopy,
  reviewingEventId,
  totalEventPages,
}: EventsResultsProps) => {
  if (events.length === 0) {
    return <p className="text-sm text-muted-foreground">{eventsCopy.empty}</p>;
  }

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{eventsCopy.table.title}</TableHead>
            <TableHead>{eventsCopy.table.city}</TableHead>
            <TableHead>{eventsCopy.table.date}</TableHead>
            <TableHead>{eventsCopy.table.owner}</TableHead>
            <TableHead>{eventsCopy.table.status}</TableHead>
            <TableHead>{eventsCopy.table.moderation}</TableHead>
            <TableHead className="text-right">{eventsCopy.table.seats}</TableHead>
            <TableHead className="w-[160px]" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {events.map((event) => (
            <AdminEventRow
              key={event.id}
              event={event}
              eventsCopy={eventsCopy}
              language={language}
              onDelete={onDelete}
              onRestore={onRestore}
              onReview={onReview}
              reviewingEventId={reviewingEventId}
            />
          ))}
        </TableBody>
      </Table>
      <EventsPagination
        copy={paginationCopy}
        currentPage={eventsPage}
        onNext={loadNextPage}
        onPrevious={loadPreviousPage}
        totalItems={eventsTotal}
        totalPages={totalEventPages}
      />
    </>
  );
};

/** Render the admin events tab with filtering, moderation, and pagination controls. */
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

  const eventsCopy = t.adminDashboard.events;
  const paginationCopy = t.adminDashboard.pagination;
  const resultsContent = isLoadingEvents ? (
    <LoadingPage message={eventsCopy.loading} />
  ) : (
    <EventsResults
      events={events}
      eventsCopy={eventsCopy}
      eventsPage={eventsPage}
      eventsTotal={eventsTotal}
      language={language}
      loadNextPage={() => loadEvents(eventsPage + 1)}
      loadPreviousPage={() => loadEvents(eventsPage - 1)}
      onDelete={handleDeleteEvent}
      onRestore={handleRestoreEvent}
      onReview={handleReviewEvent}
      paginationCopy={paginationCopy}
      reviewingEventId={reviewingEventId}
      totalEventPages={totalEventPages}
    />
  );

  return (
    <div className="mt-6 space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{eventsCopy.title}</CardTitle>
        </CardHeader>
        <CardContent>
          <EventsFiltersBar
            applyLabel={eventsCopy.apply}
            eventsFlaggedOnly={eventsFlaggedOnly}
            eventsIncludeDeleted={eventsIncludeDeleted}
            eventsSearch={eventsSearch}
            eventsStatus={eventsStatus}
            flaggedOnlyLabel={eventsCopy.flaggedOnly}
            includeDeletedLabel={eventsCopy.includeDeleted}
            isLoadingEvents={isLoadingEvents}
            onApply={() => loadEvents(1)}
            onFlaggedOnlyChange={setEventsFlaggedOnly}
            onIncludeDeletedChange={setEventsIncludeDeleted}
            onSearchChange={setEventsSearch}
            onStatusChange={setEventsStatus}
            searchLabel={eventsCopy.searchLabel}
            searchPlaceholder={eventsCopy.searchPlaceholder}
            statusAll={eventsCopy.statusAll}
            statusDraft={eventsCopy.statusDraft}
            statusLabel={eventsCopy.statusLabel}
            statusPublished={eventsCopy.statusPublished}
          />
          {resultsContent}
        </CardContent>
      </Card>
    </div>
  );
}
