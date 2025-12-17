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
import { LoadingPage } from '@/components/ui/loading';
import { useToast } from '@/hooks/use-toast';
import {
  ArrowLeft,
  Users,
  Mail,
  Download,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
} from 'lucide-react';
import { format } from 'date-fns';
import { ro } from 'date-fns/locale';

export function ParticipantsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<ParticipantList | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sortBy, setSortBy] = useState('registration_time');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const { toast } = useToast();

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
        title: 'Eroare',
        description: 'Nu am putut încărca participanții',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [id, page, pageSize, sortBy, sortDir, toast]);

  useEffect(() => {
    loadParticipants();
  }, [loadParticipants]);

  const handleAttendanceChange = async (participant: Participant, attended: boolean) => {
    if (!id) return;
    try {
      await eventService.updateParticipantAttendance(parseInt(id), participant.id, attended);
      setData((prev) =>
        prev
          ? {
              ...prev,
              participants: prev.participants.map((p) =>
                p.id === participant.id ? { ...p, attended } : p
              ),
            }
          : null
      );
      toast({
        title: 'Succes',
        description: attended ? 'Participare confirmată' : 'Participare anulată',
      });
    } catch {
      toast({
        title: 'Eroare',
        description: 'Nu am putut actualiza prezența',
        variant: 'destructive',
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

    const headers = ['Email', 'Nume', 'Data înregistrării', 'Prezent'];
    const rows = data.participants.map((p) => [
      p.email,
      p.full_name || '',
      format(new Date(p.registration_time), 'dd.MM.yyyy HH:mm'),
      p.attended ? 'Da' : 'Nu',
    ]);

    const csv = [headers, ...rows].map((row) => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `participanti-${data.title.replace(/\s+/g, '-')}.csv`;
    link.click();
  };

  if (isLoading && !data) {
    return <LoadingPage message="Se încarcă participanții..." />;
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
        Înapoi la dashboard
      </Button>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5" />
                Participanți
              </CardTitle>
              <CardDescription className="mt-1">{data.title}</CardDescription>
            </div>
            <div className="flex items-center gap-4">
              <Badge variant="outline">
                {data.seats_taken}
                {data.max_seats && ` / ${data.max_seats}`} înscriși
              </Badge>
              <Badge variant="secondary">{attendedCount} prezenți</Badge>
              <Button variant="outline" onClick={exportToCSV}>
                <Download className="mr-2 h-4 w-4" />
                Export CSV
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {data.participants.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Users className="mb-4 h-12 w-12 text-muted-foreground" />
              <h3 className="text-lg font-semibold">Nu există participanți</h3>
              <p className="mt-2 text-muted-foreground">
                Nimeni nu s-a înscris încă la acest eveniment
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
                        Email
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
                        Nume
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
                        Data înregistrării
                        <ArrowUpDown className="ml-2 h-4 w-4" />
                      </Button>
                    </TableHead>
                    <TableHead className="w-[100px]">Prezent</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.participants.map((participant) => (
                    <TableRow key={participant.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Mail className="h-4 w-4 text-muted-foreground" />
                          <a
                            href={`mailto:${participant.email}`}
                            className="hover:underline"
                          >
                            {participant.email}
                          </a>
                        </div>
                      </TableCell>
                      <TableCell>{participant.full_name || '-'}</TableCell>
                      <TableCell>
                        {format(new Date(participant.registration_time), 'd MMM yyyy, HH:mm', {
                          locale: ro,
                        })}
                      </TableCell>
                      <TableCell>
                        <Checkbox
                          checked={participant.attended}
                          onCheckedChange={(checked) =>
                            handleAttendanceChange(participant, checked === true)
                          }
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="mt-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Pe pagină:</span>
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
                      Pagina {page} din {totalPages}
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
