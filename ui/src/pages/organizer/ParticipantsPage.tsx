import { useState, useEffect, useCallback, type Dispatch, type SetStateAction } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import eventService from '@/services/event.service';
import type { ParticipantList, Participant } from '@/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { LoadingSpinner } from '@/components/ui/loading';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { useI18n } from '@/contexts/LanguageContext';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  ArrowLeft,
  Users,
  Mail,
  Download,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
} from 'lucide-react';
import { formatDateTime } from '@/lib/utils';

type ParticipantsTexts = ReturnType<typeof useI18n>['t'];
type AttendanceMutationArgs = Readonly<{
  attended: boolean;
  currentData: ParticipantList;
  eventId: number;
  participant: Participant;
  setData: Dispatch<SetStateAction<ParticipantList | null>>;
  setUpdatingAttendance: Dispatch<SetStateAction<Set<number>>>;
  t: ParticipantsTexts;
  toast: ReturnType<typeof useToast>['toast'];
}>;
type EmailSendArgs = Readonly<{
  emailMessage: string;
  emailSubject: string;
  eventId: number;
  onSuccess: () => void;
  setIsEmailing: Dispatch<SetStateAction<boolean>>;
  t: ParticipantsTexts;
  toast: ReturnType<typeof useToast>['toast'];
}>;
type ParticipantsOverviewHeaderProps = Readonly<{
  attendedCount: number;
  isLoading: boolean;
  onExport: () => void;
  onOpenEmail: () => void;
  participantData: ParticipantList;
  t: ParticipantsTexts;
}>;
type ParticipantsEmailDialogProps = Readonly<{
  emailDialogOpen: boolean;
  emailMessage: string;
  emailSubject: string;
  isEmailing: boolean;
  onEmailMessageChange: (value: string) => void;
  onEmailSubjectChange: (value: string) => void;
  onOpenChange: (open: boolean) => void;
  onSend: () => void;
  t: ParticipantsTexts;
}>;
type ParticipantsTableProps = Readonly<{
  data: ParticipantList;
  handleAttendanceChange: (participant: Participant, attended: boolean) => Promise<void>;
  isLoading: boolean;
  language: ReturnType<typeof useI18n>['language'];
  onToggleSort: (column: string) => void;
  skeletonRowKeys: string[];
  t: ParticipantsTexts;
  updatingAttendance: Set<number>;
}>;
type ParticipantsPaginationProps = Readonly<{
  page: number;
  pageSize: number;
  setPage: Dispatch<SetStateAction<number>>;
  setPageSize: Dispatch<SetStateAction<number>>;
  t: ParticipantsTexts;
  totalPages: number;
}>;

/** Generate a bounded list of placeholder-row keys for the loading skeleton. */
function skeletonKeys(pageSize: number) {
  return Array.from({ length: Math.min(pageSize, 10) }, (_, position) => `skeleton-${position + 1}`);
}

/** Update a single participant's attended flag within the current table rows. */
function participantRowsWithAttendance(
  participants: Participant[],
  participantId: number,
  attended: boolean,
) {
  return participants.map((entry) =>
    entry.id === participantId ? { ...entry, attended } : entry,
  );
}

/** Add or remove a participant identifier from the in-flight attendance set. */
function toggledParticipantSet(previous: Set<number>, participantId: number, active: boolean) {
  const next = new Set(previous);
  if (active) {
    next.add(participantId);
  } else {
    next.delete(participantId);
  }
  return next;
}

/** Request one page of organizer participants using the active table settings. */
function loadParticipantsPage(
  eventId: number,
  page: number,
  pageSize: number,
  sortBy: string,
  sortDir: 'asc' | 'desc',
) {
  return eventService.getEventParticipants(eventId, page, pageSize, sortBy, sortDir);
}

/** Optimistically toggle attendee presence and roll back the row on failure. */
async function mutateAttendance(args: AttendanceMutationArgs) {
  const {
    attended,
    currentData,
    eventId,
    participant,
    setData,
    setUpdatingAttendance,
    t,
    toast,
  } = args;
  const participantId = participant.id;
  const previous = participant.attended;

  setUpdatingAttendance((value) => toggledParticipantSet(value, participantId, true));
  setData({
    ...currentData,
    participants: participantRowsWithAttendance(currentData.participants, participantId, attended),
  });

  try {
    await eventService.updateParticipantAttendance(eventId, participantId, attended);
    toast({
      title: t.common.success,
      description: attended ? t.participants.attendanceConfirmed : t.participants.attendanceCleared,
    });
  } catch {
    setData({
      ...currentData,
      participants: participantRowsWithAttendance(currentData.participants, participantId, previous),
    });
    toast({
      title: t.common.error,
      description: t.participants.attendanceUpdateErrorDescription,
      variant: 'destructive',
    });
  } finally {
    setUpdatingAttendance((value) => toggledParticipantSet(value, participantId, false));
  }
}

/** Escape one CSV cell value according to RFC-style quoting rules. */
function escapeCsv(value: string) {
  return `"${value.split('"').join('""')}"`;
}

/** Build the exported participant CSV filename from the event title. */
function csvFilename(title: string, t: ParticipantsTexts) {
  return `${t.participants.csvFilePrefix}-${title.trim().split(' ').filter(Boolean).join('-')}.csv`;
}

/** Create and trigger the CSV export for the currently loaded participants. */
function downloadParticipantsCsv(
  data: ParticipantList,
  language: Parameters<typeof formatDateTime>[1],
  t: ParticipantsTexts,
) {
  const headers = [
    t.participants.csvHeaders.email,
    t.participants.csvHeaders.name,
    t.participants.csvHeaders.registrationDate,
    t.participants.csvHeaders.attended,
  ];
  const rows = data.participants.map((participant) => [
    participant.email,
    participant.full_name || '',
    formatDateTime(participant.registration_time, language),
    participant.attended ? t.participants.csvYes : t.participants.csvNo,
  ]);
  const csv = [headers, ...rows]
    .map((row) => row.map((cell) => escapeCsv(String(cell))).join(','))
    .join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = csvFilename(data.title, t);
  link.click();
}

/** Validate the organizer email draft before sending it to the backend. */
function validateEmailDraft(
  subject: string,
  message: string,
  t: ParticipantsTexts,
) {
  if (!subject.trim()) {
    return t.participants.emailMissingSubject;
  }
  if (!message.trim()) {
    return t.participants.emailMissingMessage;
  }
  return null;
}

/** Send a bulk email to participants after validating the current draft. */
async function sendParticipantsEmail({
  emailMessage,
  emailSubject,
  eventId,
  onSuccess,
  setIsEmailing,
  t,
  toast,
}: EmailSendArgs) {
  const validationMessage = validateEmailDraft(emailSubject, emailMessage, t);
  if (validationMessage) {
    toast({
      title: t.common.error,
      description: validationMessage,
      variant: 'destructive',
    });
    return;
  }

  setIsEmailing(true);
  try {
    const response = await eventService.emailEventParticipants(
      eventId,
      emailSubject.trim(),
      emailMessage.trim(),
    );
    toast({
      title: t.common.success,
      description: t.participants.emailSuccess.replace('{count}', String(response.recipients)),
    });
    onSuccess();
  } catch {
    toast({
      title: t.common.error,
      description: t.participants.emailError,
      variant: 'destructive',
    });
  } finally {
    setIsEmailing(false);
  }
}

/** Render the organizer summary header with counts and participant actions. */
function ParticipantsOverviewHeader({
  attendedCount,
  isLoading,
  onExport,
  onOpenEmail,
  participantData,
  t,
}: ParticipantsOverviewHeaderProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <CardTitle className="flex items-center gap-2">
          <Users className="h-5 w-5" />
          {t.participants.title}
          {isLoading && <LoadingSpinner size="sm" className="ml-2" />}
        </CardTitle>
        <CardDescription className="mt-1">{participantData.title}</CardDescription>
      </div>
      <div className="flex items-center gap-4">
        <Badge variant="outline">
          {participantData.seats_taken}
          {participantData.max_seats && ` / ${participantData.max_seats}`} {t.participants.registeredSuffix}
        </Badge>
        <Badge variant="secondary">
          {attendedCount} {t.participants.attendedSuffix}
        </Badge>
        <Button variant="outline" disabled={participantData.total === 0} onClick={onOpenEmail}>
          <Mail className="mr-2 h-4 w-4" />
          {t.participants.emailParticipants}
        </Button>
        <Button variant="outline" onClick={onExport}>
          <Download className="mr-2 h-4 w-4" />
          {t.participants.exportCsv}
        </Button>
      </div>
    </div>
  );
}

/** Render the email-composer dialog used to message event participants in bulk. */
function ParticipantsEmailDialog({
  emailDialogOpen,
  emailMessage,
  emailSubject,
  isEmailing,
  onEmailMessageChange,
  onEmailSubjectChange,
  onOpenChange,
  onSend,
  t,
}: ParticipantsEmailDialogProps) {
  return (
    <Dialog open={emailDialogOpen} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.participants.emailDialogTitle}</DialogTitle>
          <DialogDescription>{t.participants.emailDialogDescription}</DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="email-subject">{t.participants.emailSubjectLabel}</Label>
          <Input
            id="email-subject"
            value={emailSubject}
            onChange={(event) => onEmailSubjectChange(event.target.value)}
            placeholder={t.participants.emailSubjectPlaceholder}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email-message">{t.participants.emailMessageLabel}</Label>
          <Textarea
            id="email-message"
            value={emailMessage}
            onChange={(event) => onEmailMessageChange(event.target.value)}
            placeholder={t.participants.emailMessagePlaceholder}
            rows={6}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isEmailing}>
            {t.common.cancel}
          </Button>
          <Button onClick={onSend} disabled={isEmailing}>
            {t.participants.emailSend}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Render the loading skeleton for the organizer participants view. */
function ParticipantsLoadingHeader() {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="space-y-2">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-4 w-56" />
      </div>
      <div className="flex items-center gap-4">
        <Skeleton className="h-6 w-24" />
        <Skeleton className="h-6 w-24" />
        <Skeleton className="h-10 w-32" />
      </div>
    </div>
  );
}

/** Render the placeholder rows used while participant data is loading. */
function ParticipantsLoadingRows() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
  );
}

/** Render the loading skeleton for the organizer participants view. */
function ParticipantsLoadingState({ t }: Readonly<{ t: ParticipantsTexts }>) {
  return (
    <div className="container mx-auto px-4 py-8">
      <Skeleton className="mb-6 h-10 w-48" />

      <Card>
        <CardHeader>
          <ParticipantsLoadingHeader />
        </CardHeader>
        <CardContent><ParticipantsLoadingRows /></CardContent>
      </Card>
      <span className="sr-only">{t.participants.title}</span>
    </div>
  );
}

/** Render one sortable column header for the participants table. */
function ParticipantsSortHeader({
  column,
  label,
  onToggleSort,
}: Readonly<{
  column: string;
  label: string;
  onToggleSort: (column: string) => void;
}>) {
  return (
    <Button
      variant="ghost"
      size="sm"
      className="p-0 font-medium"
      onClick={() => onToggleSort(column)}
    >
      {label}
      <ArrowUpDown className="ml-2 h-4 w-4" />
    </Button>
  );
}

/** Render one loading row in the participants table while data is refreshing. */
function ParticipantsSkeletonRow({ rowKey }: Readonly<{ rowKey: string }>) {
  return (
    <TableRow key={rowKey}>
      <TableCell>
        <div className="flex items-center gap-2">
          <Skeleton className="h-4 w-4 rounded" />
          <Skeleton className="h-4 w-48" />
        </div>
      </TableCell>
      <TableCell>
        <Skeleton className="h-4 w-32" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-4 w-40" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-5 rounded" />
      </TableCell>
    </TableRow>
  );
}

/** Render one participant row with email, registration date, and attendance toggle. */
function ParticipantRow({
  handleAttendanceChange,
  language,
  participant,
  updatingAttendance,
}: Readonly<{
  handleAttendanceChange: (participant: Participant, attended: boolean) => Promise<void>;
  language: ReturnType<typeof useI18n>['language'];
  participant: Participant;
  updatingAttendance: Set<number>;
}>) {
  return (
    <TableRow key={participant.id}>
      <TableCell>
        <div className="flex items-center gap-2">
          <Mail className="h-4 w-4 text-muted-foreground" />
          <a href={`mailto:${participant.email}`} className="hover:underline">
            {participant.email}
          </a>
        </div>
      </TableCell>
      <TableCell>{participant.full_name || '-'}</TableCell>
      <TableCell>{formatDateTime(participant.registration_time, language)}</TableCell>
      <TableCell>
        <div className="flex items-center gap-2">
          <Checkbox
            checked={participant.attended}
            disabled={updatingAttendance.has(participant.id)}
            onCheckedChange={(checked) => handleAttendanceChange(participant, checked === true)}
          />
          {updatingAttendance.has(participant.id) && <LoadingSpinner size="sm" />}
        </div>
      </TableCell>
    </TableRow>
  );
}

/** Render the participant rows and sortable headers for the organizer table. */
function ParticipantsTable(props: ParticipantsTableProps) {
  const {
    data,
    handleAttendanceChange,
    isLoading,
    language,
    onToggleSort,
    skeletonRowKeys,
    t,
    updatingAttendance,
  } = props;

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>
            <ParticipantsSortHeader
              column="email"
              label={t.participants.table.email}
              onToggleSort={onToggleSort}
            />
          </TableHead>
          <TableHead>
            <ParticipantsSortHeader
              column="full_name"
              label={t.participants.table.name}
              onToggleSort={onToggleSort}
            />
          </TableHead>
          <TableHead>
            <ParticipantsSortHeader
              column="registration_time"
              label={t.participants.table.registrationDate}
              onToggleSort={onToggleSort}
            />
          </TableHead>
          <TableHead className="w-[100px]">{t.participants.table.attended}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {isLoading
          ? skeletonRowKeys.map((rowKey) => <ParticipantsSkeletonRow key={rowKey} rowKey={rowKey} />)
          : data.participants.map((participant) => (
              <ParticipantRow
                key={participant.id}
                handleAttendanceChange={handleAttendanceChange}
                language={language}
                participant={participant}
                updatingAttendance={updatingAttendance}
              />
            ))}
      </TableBody>
    </Table>
  );
}

/** Render the empty-state card body for events with no registered participants. */
function ParticipantsEmptyState({ t }: Readonly<{ t: ParticipantsTexts }>) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Users className="mb-4 h-12 w-12 text-muted-foreground" />
      <h3 className="text-lg font-semibold">{t.participants.emptyTitle}</h3>
      <p className="mt-2 text-muted-foreground">{t.participants.emptyDescription}</p>
    </div>
  );
}

/** Render the participants pagination controls and page-size selector. */
function ParticipantsPageSizeSelect({
  pageSize,
  setPage,
  setPageSize,
}: Readonly<{
  pageSize: number;
  setPage: Dispatch<SetStateAction<number>>;
  setPageSize: Dispatch<SetStateAction<number>>;
}>) {
  return (
    <Select
      value={String(pageSize)}
      onValueChange={(value) => {
        setPageSize(Number.parseInt(value, 10));
        setPage(1);
      }}
    >
      <SelectTrigger className="w-[70px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="10">10</SelectItem>
        <SelectItem value="20">20</SelectItem>
        <SelectItem value="50">50</SelectItem>
        <SelectItem value="100">100</SelectItem>
      </SelectContent>
    </Select>
  );
}

/** Render the previous and next pagination buttons with the page counter. */
function ParticipantsPageButtons({
  page,
  setPage,
  t,
  totalPages,
}: Readonly<{
  page: number;
  setPage: Dispatch<SetStateAction<number>>;
  t: ParticipantsTexts;
  totalPages: number;
}>) {
  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="icon"
        disabled={page === 1}
        onClick={() => setPage((value) => value - 1)}
      >
        <ChevronLeft className="h-4 w-4" />
      </Button>
      <span className="text-sm">
        {t.participants.paginationPage} {page} {t.participants.paginationOf} {totalPages}
      </span>
      <Button
        variant="outline"
        size="icon"
        disabled={page === totalPages}
        onClick={() => setPage((value) => value + 1)}
      >
        <ChevronRight className="h-4 w-4" />
      </Button>
    </div>
  );
}

/** Render the participants pagination controls and page-size selector. */
function ParticipantsPagination({
  page,
  pageSize,
  setPage,
  setPageSize,
  t,
  totalPages,
}: ParticipantsPaginationProps) {
  return (
    <div className="mt-4 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">{t.participants.perPage}</span>
        <ParticipantsPageSizeSelect pageSize={pageSize} setPage={setPage} setPageSize={setPageSize} />
      </div>
      <ParticipantsPageButtons page={page} setPage={setPage} t={t} totalPages={totalPages} />
    </div>
  );
}

/** Render the organizer participant-management page for one event. */
export function ParticipantsPage() {
  const { id } = useParams<{ id: string }>();
  const eventId = Number(id);
  const navigate = useNavigate();
  const [data, setData] = useState<ParticipantList | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sortBy, setSortBy] = useState('registration_time');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [updatingAttendance, setUpdatingAttendance] = useState<Set<number>>(() => new Set());
  const [emailDialogOpen, setEmailDialogOpen] = useState(false);
  const [emailSubject, setEmailSubject] = useState('');
  const [emailMessage, setEmailMessage] = useState('');
  const [isEmailing, setIsEmailing] = useState(false);
  const { toast } = useToast();
  const { language, t } = useI18n();
  const skeletonRowKeys = skeletonKeys(pageSize);

  const loadParticipants = useCallback(async () => {
    if (!eventId) {
      setData(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const response = await loadParticipantsPage(eventId, page, pageSize, sortBy, sortDir);
      setData(response);
    } catch {
      toast({
        title: t.common.error,
        description: t.participants.loadErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [eventId, page, pageSize, sortBy, sortDir, t, toast]);

  useEffect(() => {
    loadParticipants();
  }, [loadParticipants]);

  /** Toggle the active participant sort key and reverse direction on repeated clicks. */
  const toggleSort = (column: string) => {
    if (sortBy === column) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(column);
      setSortDir('asc');
    }
  };

  /** Send the currently composed participant email draft and reset the dialog on success. */
  const sendEmailToParticipants = async () => {
    await sendParticipantsEmail({
      emailMessage,
      emailSubject,
      eventId,
      onSuccess: () => {
        setEmailDialogOpen(false);
        setEmailSubject('');
        setEmailMessage('');
      },
      setIsEmailing,
      t,
      toast,
    });
  };

  if (isLoading && !data) {
    return <ParticipantsLoadingState t={t} />;
  }

  if (!data) {
    return null;
  }

  const participantData = data;
  const totalPages = Math.ceil(participantData.total / pageSize);
  const attendedCount = participantData.participants.filter((p) => p.attended).length;

  /** Persist an attendance toggle while keeping the UI optimistic and localized. */
  const handleAttendanceChange = async (participant: Participant, attended: boolean) => {
    await mutateAttendance({
      attended,
      currentData: participantData,
      eventId,
      participant,
      setData,
      setUpdatingAttendance,
      t,
      toast,
    });
  };

  /** Export the currently loaded participant rows to CSV using the active language. */
  const exportToCSV = () => {
    downloadParticipantsCsv(participantData, language, t);
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <ParticipantsEmailDialog
        emailDialogOpen={emailDialogOpen}
        emailMessage={emailMessage}
        emailSubject={emailSubject}
        isEmailing={isEmailing}
        onEmailMessageChange={setEmailMessage}
        onEmailSubjectChange={setEmailSubject}
        onOpenChange={setEmailDialogOpen}
        onSend={sendEmailToParticipants}
        t={t}
      />

      <Button variant="ghost" className="mb-6" onClick={() => navigate('/organizer')}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        {t.participants.backToDashboard}
      </Button>

      <Card>
        <CardHeader>
          <ParticipantsOverviewHeader
            attendedCount={attendedCount}
            isLoading={isLoading}
            onExport={exportToCSV}
            onOpenEmail={() => setEmailDialogOpen(true)}
            participantData={participantData}
            t={t}
          />
        </CardHeader>
        <CardContent>
          {data.participants.length === 0 ? (
            <ParticipantsEmptyState t={t} />
          ) : (
            <>
              <ParticipantsTable
                data={data}
                handleAttendanceChange={handleAttendanceChange}
                isLoading={isLoading}
                language={language}
                onToggleSort={toggleSort}
                skeletonRowKeys={skeletonRowKeys}
                t={t}
                updatingAttendance={updatingAttendance}
              />

              {totalPages > 1 && (
                <ParticipantsPagination
                  page={page}
                  pageSize={pageSize}
                  setPage={setPage}
                  setPageSize={setPageSize}
                  t={t}
                  totalPages={totalPages}
                />
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
