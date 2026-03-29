import { Link } from 'react-router-dom';
import type { UiStrings } from '@/i18n/strings';
import type { ResolvedLanguage } from '@/lib/language';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { getEventCategoryLabel } from '@/lib/eventCategories';
import { formatDate } from '@/lib/utils';
import type { Event } from '@/types';
import { Calendar, Edit, Eye, MoreHorizontal, Plus, Trash2, Users } from 'lucide-react';

type Props = Readonly<{
  events: Event[];
  isBulkUpdating: boolean;
  language: ResolvedLanguage;
  now: Date;
  onBulkStatusUpdate: (status: 'draft' | 'published') => void;
  onClearSelection: () => void;
  onDelete: (eventId: number) => void;
  onOpenBulkTags: () => void;
  onSelectAll: (checked: boolean) => void;
  onToggleSelected: (eventId: number, checked: boolean) => void;
  selectAllState: boolean | 'indeterminate';
  selectedCount: number;
  selectedEventIds: Set<number>;
  texts: UiStrings['organizerDashboard'];
}>;

type OrganizerEventRowProps = Readonly<{
  event: Event;
  language: ResolvedLanguage;
  now: Date;
  onDelete: (eventId: number) => void;
  onToggleSelected: (eventId: number, checked: boolean) => void;
  selectedEventIds: Set<number>;
  texts: UiStrings['organizerDashboard'];
}>;

/** Render the localized status badge shown for one organizer-owned event row. */
function statusBadge(texts: UiStrings['organizerDashboard'], status: Event['status'], isPast: boolean) {
  if (status === 'draft') {
    return <Badge variant="secondary">{texts.statusDraft}</Badge>;
  }
  if (isPast) {
    return <Badge variant="outline">{texts.statusEnded}</Badge>;
  }
  return <Badge variant="default">{texts.statusActive}</Badge>;
}

/** Render the bulk action toolbar that appears after organizer event selection. */
function OrganizerBulkActionsBar({
  isBulkUpdating,
  onBulkStatusUpdate,
  onClearSelection,
  onOpenBulkTags,
  selectedCount,
  texts,
}: Readonly<{
  isBulkUpdating: boolean;
  onBulkStatusUpdate: (status: 'draft' | 'published') => void;
  onClearSelection: () => void;
  onOpenBulkTags: () => void;
  selectedCount: number;
  texts: UiStrings['organizerDashboard'];
}>) {
  return (
    <div className="flex flex-col gap-3 rounded-md border p-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="text-sm text-muted-foreground">
        {texts.bulk.selected}: <span className="font-medium text-foreground">{selectedCount}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={isBulkUpdating}
          onClick={() => onBulkStatusUpdate('published')}
        >
          {texts.bulk.publish}
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={isBulkUpdating}
          onClick={() => onBulkStatusUpdate('draft')}
        >
          {texts.bulk.unpublish}
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={isBulkUpdating}
          onClick={onOpenBulkTags}
        >
          {texts.bulk.tags}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={isBulkUpdating}
          onClick={onClearSelection}
        >
          {texts.bulk.clear}
        </Button>
      </div>
    </div>
  );
}

/** Render the empty organizer state shown before the first event is created. */
function OrganizerEventsEmptyState({ texts }: Readonly<{ texts: UiStrings['organizerDashboard'] }>) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Calendar className="mb-4 h-12 w-12 text-muted-foreground" />
      <h3 className="text-lg font-semibold">{texts.emptyTitle}</h3>
      <p className="mt-2 text-muted-foreground">{texts.emptyDescription}</p>
      <Button asChild className="mt-4">
        <Link to="/organizer/events/new">
          <Plus className="mr-2 h-4 w-4" />
          {texts.emptyCreateButton}
        </Link>
      </Button>
    </div>
  );
}

/** Render the per-row action menu for one organizer-owned event. */
function OrganizerEventActions({
  eventId,
  onDelete,
  texts,
}: Readonly<{
  eventId: number;
  onDelete: (eventId: number) => void;
  texts: UiStrings['organizerDashboard'];
}>) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem asChild>
          <Link to={`/events/${eventId}`}>
            <Eye className="mr-2 h-4 w-4" />
            {texts.actionView}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link to={`/organizer/events/${eventId}/edit`}>
            <Edit className="mr-2 h-4 w-4" />
            {texts.actionEdit}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link to={`/organizer/events/${eventId}/participants`}>
            <Users className="mr-2 h-4 w-4" />
            {texts.actionParticipants}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem className="text-destructive" onClick={() => onDelete(eventId)}>
          <Trash2 className="mr-2 h-4 w-4" />
          {texts.actionDelete}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Render one event row with selection, metrics, and actions for organizers. */
function OrganizerEventRow({
  event,
  language,
  now,
  onDelete,
  onToggleSelected,
  selectedEventIds,
  texts,
}: OrganizerEventRowProps) {
  const isPast = new Date(event.start_time) < now;
  const categoryLabel = getEventCategoryLabel(event.category, language);

  return (
    <TableRow key={event.id}>
      <TableCell>
        <Checkbox
          checked={selectedEventIds.has(event.id)}
          onCheckedChange={(checked) => onToggleSelected(event.id, checked === true)}
          aria-label={texts.bulk.selectOneAria}
        />
      </TableCell>
      <TableCell>
        <Link to={`/events/${event.id}`} className="font-medium hover:underline">
          {event.title}
        </Link>
        {categoryLabel && (
          <span className="ml-2 text-sm text-muted-foreground">({categoryLabel})</span>
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
      <TableCell>{statusBadge(texts, event.status, isPast)}</TableCell>
      <TableCell>
        <OrganizerEventActions eventId={event.id} onDelete={onDelete} texts={texts} />
      </TableCell>
    </TableRow>
  );
}

/** Render the organizer events table once at least one event exists. */
function OrganizerEventsTableContent({
  events,
  isBulkUpdating,
  language,
  now,
  onBulkStatusUpdate,
  onClearSelection,
  onDelete,
  onOpenBulkTags,
  onSelectAll,
  onToggleSelected,
  selectAllState,
  selectedCount,
  selectedEventIds,
  texts,
}: Props) {
  return (
    <div className="space-y-4">
      {selectedCount > 0 && (
        <OrganizerBulkActionsBar
          isBulkUpdating={isBulkUpdating}
          onBulkStatusUpdate={onBulkStatusUpdate}
          onClearSelection={onClearSelection}
          onOpenBulkTags={onOpenBulkTags}
          selectedCount={selectedCount}
          texts={texts}
        />
      )}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[40px]">
              <Checkbox
                checked={selectAllState}
                onCheckedChange={(checked) => onSelectAll(checked === true)}
                aria-label={texts.bulk.selectAllAria}
              />
            </TableHead>
            <TableHead>{texts.tableHeaderTitle}</TableHead>
            <TableHead>{texts.tableHeaderDate}</TableHead>
            <TableHead>{texts.tableHeaderParticipants}</TableHead>
            <TableHead>{texts.tableHeaderStatus}</TableHead>
            <TableHead className="w-[70px]" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {events.map((event) => (
            <OrganizerEventRow
              key={event.id}
              event={event}
              language={language}
              now={now}
              onDelete={onDelete}
              onToggleSelected={onToggleSelected}
              selectedEventIds={selectedEventIds}
              texts={texts}
            />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

/** Render the organizer-owned event list with selection and per-row actions. */
export function OrganizerEventsTable({
  events,
  isBulkUpdating,
  language,
  now,
  onBulkStatusUpdate,
  onClearSelection,
  onDelete,
  onOpenBulkTags,
  onSelectAll,
  onToggleSelected,
  selectAllState,
  selectedCount,
  selectedEventIds,
  texts,
}: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{texts.tableTitle}</CardTitle>
      </CardHeader>
      <CardContent>
        {events.length === 0 ? (
          <OrganizerEventsEmptyState texts={texts} />
        ) : (
          <OrganizerEventsTableContent
            events={events}
            isBulkUpdating={isBulkUpdating}
            language={language}
            now={now}
            onBulkStatusUpdate={onBulkStatusUpdate}
            onClearSelection={onClearSelection}
            onDelete={onDelete}
            onOpenBulkTags={onOpenBulkTags}
            onSelectAll={onSelectAll}
            onToggleSelected={onToggleSelected}
            selectAllState={selectAllState}
            selectedCount={selectedCount}
            selectedEventIds={selectedEventIds}
            texts={texts}
          />
        )}
      </CardContent>
    </Card>
  );
}
