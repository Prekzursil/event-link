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

function statusBadge(texts: UiStrings['organizerDashboard'], status: Event['status'], isPast: boolean) {
  if (status === 'draft') {
    return <Badge variant="secondary">{texts.statusDraft}</Badge>;
  }
  if (isPast) {
    return <Badge variant="outline">{texts.statusEnded}</Badge>;
  }
  return <Badge variant="default">{texts.statusActive}</Badge>;
}

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
        ) : (
          <>
            {selectedCount > 0 && (
              <div className="mb-4 flex flex-col gap-3 rounded-md border p-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="text-sm text-muted-foreground">
                  {texts.bulk.selected}:{' '}
                  <span className="font-medium text-foreground">{selectedCount}</span>
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
                      <TableCell>{statusBadge(texts, event.status, isPast)}</TableCell>
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
                                {texts.actionView}
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem asChild>
                              <Link to={`/organizer/events/${event.id}/edit`}>
                                <Edit className="mr-2 h-4 w-4" />
                                {texts.actionEdit}
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem asChild>
                              <Link to={`/organizer/events/${event.id}/participants`}>
                                <Users className="mr-2 h-4 w-4" />
                                {texts.actionParticipants}
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-destructive"
                              onClick={() => onDelete(event.id)}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              {texts.actionDelete}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </>
        )}
      </CardContent>
    </Card>
  );
}
