import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import eventService from '@/services/event.service';
import type { ParticipantList, Participant } from '@/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
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
import { useToast } from '@/hooks/use-toast';
import { useI18n } from '@/contexts/LanguageContext';
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

export function ParticipantsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<ParticipantList | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sortBy, setSortBy] = useState('registration_time');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [updatingAttendance, setUpdatingAttendance] = useState<Set<number>>(() => new Set());
  const { toast } = useToast();
  const { language, t } = useI18n();

  const loadParticipants = useCallback(async () => {
    if (!id) return;
    setIsLoading(true);
    try {
      const response = await eventService.getEventParticipants(
        parseInt(id),
        page,
        pageSize,
        sortBy,
        sortDir
      );
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
  }, [id, page, pageSize, sortBy, sortDir, t, toast]);

  useEffect(() => {
    loadParticipants();
  }, [loadParticipants]);

  const handleAttendanceChange = async (participant: Participant, attended: boolean) => {
    if (!id) return;
    if (updatingAttendance.has(participant.id)) return;
    const previous = participant.attended;

    setUpdatingAttendance((prev) => {
      const next = new Set(prev);
      next.add(participant.id);
      return next;
    });
    setData((prev) =>
      prev
        ? {
            ...prev,
            participants: prev.participants.map((p) => (p.id === participant.id ? { ...p, attended } : p)),
          }
        : null
    );
    try {
      await eventService.updateParticipantAttendance(parseInt(id), participant.id, attended);
      toast({
        title: t.common.success,
        description: attended ? t.participants.attendanceConfirmed : t.participants.attendanceCleared,
      });
    } catch {
      setData((prev) =>
        prev
          ? {
              ...prev,
              participants: prev.participants.map((p) =>
                p.id === participant.id ? { ...p, attended: previous } : p
              ),
            }
          : null
      );
      toast({
        title: t.common.error,
        description: t.participants.attendanceUpdateErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setUpdatingAttendance((prev) => {
        const next = new Set(prev);
        next.delete(participant.id);
        return next;
      });
    }
  };

  const toggleSort = (column: string) => {
    if (sortBy === column) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(column);
      setSortDir('asc');
    }
  };

  const exportToCSV = () => {
    if (!data) return;

    const escapeCsv = (value: string) => `"${value.replace(/"/g, '""')}"`;

    const headers = [
      t.participants.csvHeaders.email,
      t.participants.csvHeaders.name,
      t.participants.csvHeaders.registrationDate,
      t.participants.csvHeaders.attended,
    ];
    const rows = data.participants.map((p) => [
      p.email,
      p.full_name || '',
      formatDateTime(p.registration_time, language),
      p.attended ? t.participants.csvYes : t.participants.csvNo,
    ]);

    const csv = [headers, ...rows]
      .map((row) => row.map((cell) => escapeCsv(String(cell))).join(','))
      .join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${t.participants.csvFilePrefix}-${data.title.replace(/\s+/g, '-')}.csv`;
    link.click();
  };

  if (isLoading && !data) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Skeleton className="mb-6 h-10 w-48" />

        <Card>
          <CardHeader>
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
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const totalPages = Math.ceil(data.total / pageSize);
  const attendedCount = data.participants.filter((p) => p.attended).length;

  return (
    <div className="container mx-auto px-4 py-8">
      <Button variant="ghost" className="mb-6" onClick={() => navigate('/organizer')}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        {t.participants.backToDashboard}
      </Button>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5" />
                {t.participants.title}
                {isLoading && <LoadingSpinner size="sm" className="ml-2" />}
              </CardTitle>
              <CardDescription className="mt-1">{data.title}</CardDescription>
            </div>
            <div className="flex items-center gap-4">
              <Badge variant="outline">
                {data.seats_taken}
                {data.max_seats && ` / ${data.max_seats}`} {t.participants.registeredSuffix}
              </Badge>
              <Badge variant="secondary">
                {attendedCount} {t.participants.attendedSuffix}
              </Badge>
              <Button variant="outline" onClick={exportToCSV}>
                <Download className="mr-2 h-4 w-4" />
                {t.participants.exportCsv}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {data.participants.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Users className="mb-4 h-12 w-12 text-muted-foreground" />
              <h3 className="text-lg font-semibold">{t.participants.emptyTitle}</h3>
              <p className="mt-2 text-muted-foreground">
                {t.participants.emptyDescription}
              </p>
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="p-0 font-medium"
                        onClick={() => toggleSort('email')}
                      >
                        {t.participants.table.email}
                        <ArrowUpDown className="ml-2 h-4 w-4" />
                      </Button>
                    </TableHead>
                    <TableHead>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="p-0 font-medium"
                        onClick={() => toggleSort('full_name')}
                      >
                        {t.participants.table.name}
                        <ArrowUpDown className="ml-2 h-4 w-4" />
                      </Button>
                    </TableHead>
                    <TableHead>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="p-0 font-medium"
                        onClick={() => toggleSort('registration_time')}
                      >
                        {t.participants.table.registrationDate}
                        <ArrowUpDown className="ml-2 h-4 w-4" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[100px]">{t.participants.table.attended}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading
                    ? Array.from({ length: Math.min(pageSize, 10) }).map((_, index) => (
                        <TableRow key={`skeleton-${index}`}>
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
                      ))
                    : data.participants.map((participant) => (
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
                                onCheckedChange={(checked) =>
                                  handleAttendanceChange(participant, checked === true)
                                }
                              />
                              {updatingAttendance.has(participant.id) && <LoadingSpinner size="sm" />}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="mt-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">{t.participants.perPage}</span>
                    <Select
                      value={String(pageSize)}
                      onValueChange={(value) => {
                        setPageSize(parseInt(value));
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
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="icon"
                      disabled={page === 1}
                      onClick={() => setPage((p) => p - 1)}
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
                      onClick={() => setPage((p) => p + 1)}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
