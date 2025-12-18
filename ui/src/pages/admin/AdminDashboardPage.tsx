import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import adminService from '@/services/admin.service';
import eventService from '@/services/event.service';
import { useToast } from '@/hooks/use-toast';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { LoadingPage } from '@/components/ui/loading';
import type { AdminEvent, AdminStats, AdminUser, UserRole } from '@/types';
import { formatDateTime } from '@/lib/utils';
import { Edit, RefreshCw, RotateCcw, Trash2 } from 'lucide-react';

type AdminTab = 'overview' | 'users' | 'events';

function roleBadgeVariant(role: UserRole): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (role === 'admin') return 'destructive';
  if (role === 'organizator') return 'secondary';
  return 'outline';
}

export function AdminDashboardPage() {
  const { toast } = useToast();
  const [tab, setTab] = useState<AdminTab>('overview');

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [isLoadingStats, setIsLoadingStats] = useState(false);

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [usersPage, setUsersPage] = useState(1);
  const [usersPageSize] = useState(20);
  const [usersSearch, setUsersSearch] = useState('');
  const [usersRole, setUsersRole] = useState<'all' | UserRole>('all');
  const [usersActive, setUsersActive] = useState<'all' | 'active' | 'inactive'>('all');
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);

  const [events, setEvents] = useState<AdminEvent[]>([]);
  const [eventsTotal, setEventsTotal] = useState(0);
  const [eventsPage, setEventsPage] = useState(1);
  const [eventsPageSize] = useState(20);
  const [eventsSearch, setEventsSearch] = useState('');
  const [eventsStatus, setEventsStatus] = useState<'all' | 'draft' | 'published'>('all');
  const [eventsIncludeDeleted, setEventsIncludeDeleted] = useState(false);
  const [isLoadingEvents, setIsLoadingEvents] = useState(false);

  const loadStats = useCallback(async () => {
    setIsLoadingStats(true);
    try {
      const data = await adminService.getStats();
      setStats(data);
    } catch {
      toast({
        title: 'Eroare',
        description: 'Nu am putut încărca statisticile admin.',
        variant: 'destructive',
      });
    } finally {
      setIsLoadingStats(false);
    }
  }, [toast]);

  const loadUsers = useCallback(
    async (page = usersPage) => {
      setIsLoadingUsers(true);
      try {
        const data = await adminService.getUsers({
          search: usersSearch || undefined,
          role: usersRole === 'all' ? undefined : usersRole,
          is_active:
            usersActive === 'all' ? undefined : usersActive === 'active',
          page,
          page_size: usersPageSize,
        });
        setUsers(data.items);
        setUsersTotal(data.total);
        setUsersPage(data.page);
      } catch {
        toast({
          title: 'Eroare',
          description: 'Nu am putut încărca utilizatorii.',
          variant: 'destructive',
        });
      } finally {
        setIsLoadingUsers(false);
      }
    },
    [toast, usersActive, usersPage, usersPageSize, usersRole, usersSearch],
  );

  const loadEvents = useCallback(
    async (page = eventsPage) => {
      setIsLoadingEvents(true);
      try {
        const data = await adminService.getEvents({
          search: eventsSearch || undefined,
          status: eventsStatus === 'all' ? undefined : eventsStatus,
          include_deleted: eventsIncludeDeleted || undefined,
          page,
          page_size: eventsPageSize,
        });
        setEvents(data.items);
        setEventsTotal(data.total);
        setEventsPage(data.page);
      } catch {
        toast({
          title: 'Eroare',
          description: 'Nu am putut încărca evenimentele.',
          variant: 'destructive',
        });
      } finally {
        setIsLoadingEvents(false);
      }
    },
    [eventsIncludeDeleted, eventsPage, eventsPageSize, eventsSearch, eventsStatus, toast],
  );

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    if (tab === 'users') {
      loadUsers(1);
    }
    if (tab === 'events') {
      loadEvents(1);
    }
  }, [tab, loadEvents, loadUsers]);

  const totalUserPages = useMemo(
    () => Math.max(1, Math.ceil(usersTotal / usersPageSize)),
    [usersPageSize, usersTotal],
  );
  const totalEventPages = useMemo(
    () => Math.max(1, Math.ceil(eventsTotal / eventsPageSize)),
    [eventsPageSize, eventsTotal],
  );

  const handleUpdateUser = async (userId: number, patch: Partial<Pick<AdminUser, 'role' | 'is_active'>>) => {
    const prev = users;
    setUsers((current) =>
      current.map((u) => (u.id === userId ? { ...u, ...patch } : u)),
    );
    try {
      const updated = await adminService.updateUser(userId, patch);
      setUsers((current) => current.map((u) => (u.id === userId ? updated : u)));
      toast({ title: 'Salvat', description: 'Utilizator actualizat.' });
    } catch {
      setUsers(prev);
      toast({
        title: 'Eroare',
        description: 'Nu am putut actualiza utilizatorul.',
        variant: 'destructive',
      });
    }
  };

  const handleDeleteEvent = async (eventId: number) => {
    if (!confirm('Ștergi acest eveniment?')) return;
    try {
      await eventService.deleteEvent(eventId);
      toast({ title: 'Succes', description: 'Eveniment șters.' });
      await loadEvents(eventsPage);
    } catch {
      toast({
        title: 'Eroare',
        description: 'Nu am putut șterge evenimentul.',
        variant: 'destructive',
      });
    }
  };

  const handleRestoreEvent = async (eventId: number) => {
    try {
      await eventService.restoreEvent(eventId);
      toast({ title: 'Succes', description: 'Eveniment restaurat.' });
      await loadEvents(eventsPage);
    } catch {
      toast({
        title: 'Eroare',
        description: 'Nu am putut restaura evenimentul.',
        variant: 'destructive',
      });
    }
  };

  if (!stats && isLoadingStats) {
    return <LoadingPage message="Se încarcă dashboard-ul admin..." />;
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Admin Dashboard</h1>
          <p className="mt-2 text-muted-foreground">Monitorizare și management platformă</p>
        </div>
        <Button variant="outline" onClick={() => loadStats()} disabled={isLoadingStats}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Reîncarcă
        </Button>
      </div>

      <Tabs value={tab} onValueChange={(value) => setTab(value as AdminTab)}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="users">Utilizatori</TabsTrigger>
          <TabsTrigger value="events">Evenimente</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6 space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Total utilizatori</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.total_users ?? 0}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Total evenimente</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.total_events ?? 0}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Total înscrieri</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.total_registrations ?? 0}</div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Înscrieri pe zile</CardTitle>
              </CardHeader>
              <CardContent>
                {!stats?.registrations_by_day?.length ? (
                  <p className="text-sm text-muted-foreground">Nu există date încă.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Zi</TableHead>
                        <TableHead className="text-right">Înscrieri</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {stats.registrations_by_day.slice(-14).map((row) => (
                        <TableRow key={row.date}>
                          <TableCell>{row.date}</TableCell>
                          <TableCell className="text-right">{row.registrations}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Top taguri</CardTitle>
              </CardHeader>
              <CardContent>
                {!stats?.top_tags?.length ? (
                  <p className="text-sm text-muted-foreground">Nu există date încă.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Tag</TableHead>
                        <TableHead className="text-right">Înscrieri</TableHead>
                        <TableHead className="text-right">Evenimente</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {stats.top_tags.map((row) => (
                        <TableRow key={row.name}>
                          <TableCell>{row.name}</TableCell>
                          <TableCell className="text-right">{row.registrations}</TableCell>
                          <TableCell className="text-right">{row.events}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="users" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Utilizatori</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end">
                <div className="flex-1">
                  <label className="mb-1 block text-sm font-medium">Caută</label>
                  <Input value={usersSearch} onChange={(e) => setUsersSearch(e.target.value)} placeholder="email / nume" />
                </div>
                <div className="w-full md:w-56">
                  <label className="mb-1 block text-sm font-medium">Rol</label>
                  <Select value={usersRole} onValueChange={(v) => setUsersRole(v as 'all' | UserRole)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Toate" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Toate</SelectItem>
                      <SelectItem value="student">Student</SelectItem>
                      <SelectItem value="organizator">Organizator</SelectItem>
                      <SelectItem value="admin">Admin</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="w-full md:w-56">
                  <label className="mb-1 block text-sm font-medium">Status</label>
                  <Select value={usersActive} onValueChange={(v) => setUsersActive(v as 'all' | 'active' | 'inactive')}>
                    <SelectTrigger>
                      <SelectValue placeholder="Toate" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Toate</SelectItem>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="inactive">Dezactivate</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Button onClick={() => loadUsers(1)} disabled={isLoadingUsers}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Aplică
                </Button>
              </div>

              {isLoadingUsers ? (
                <LoadingPage message="Se încarcă utilizatorii..." />
              ) : users.length === 0 ? (
                <p className="text-sm text-muted-foreground">Niciun utilizator găsit.</p>
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Email</TableHead>
                        <TableHead>Rol</TableHead>
                        <TableHead>Activ</TableHead>
                        <TableHead>Creat</TableHead>
                        <TableHead>Ultima activitate</TableHead>
                        <TableHead className="text-right">Înscrieri</TableHead>
                        <TableHead className="text-right">Prezențe</TableHead>
                        <TableHead className="text-right">Evenimente</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {users.map((u) => (
                        <TableRow key={u.id}>
                          <TableCell>
                            <div className="font-medium">{u.email}</div>
                            {u.full_name && <div className="text-xs text-muted-foreground">{u.full_name}</div>}
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Badge variant={roleBadgeVariant(u.role)}>{u.role}</Badge>
                              <Select
                                value={u.role}
                                onValueChange={(value) =>
                                  handleUpdateUser(u.id, { role: value as UserRole })
                                }
                              >
                                <SelectTrigger className="h-8 w-[150px]">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="student">Student</SelectItem>
                                  <SelectItem value="organizator">Organizator</SelectItem>
                                  <SelectItem value="admin">Admin</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Checkbox
                              checked={u.is_active}
                              onCheckedChange={(checked) =>
                                handleUpdateUser(u.id, { is_active: Boolean(checked) })
                              }
                            />
                          </TableCell>
                          <TableCell>{formatDateTime(u.created_at)}</TableCell>
                          <TableCell>{u.last_seen_at ? formatDateTime(u.last_seen_at) : '-'}</TableCell>
                          <TableCell className="text-right">{u.registrations_count}</TableCell>
                          <TableCell className="text-right">{u.attended_count}</TableCell>
                          <TableCell className="text-right">{u.events_created_count}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>

                  <div className="mt-4 flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">
                      Pagina {usersPage} / {totalUserPages} • Total {usersTotal}
                    </p>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={usersPage <= 1}
                        onClick={() => loadUsers(usersPage - 1)}
                      >
                        Înapoi
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={usersPage >= totalUserPages}
                        onClick={() => loadUsers(usersPage + 1)}
                      >
                        Înainte
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="events" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Evenimente</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end">
                <div className="flex-1">
                  <label className="mb-1 block text-sm font-medium">Caută</label>
                  <Input value={eventsSearch} onChange={(e) => setEventsSearch(e.target.value)} placeholder="titlu / owner" />
                </div>
                <div className="w-full md:w-56">
                  <label className="mb-1 block text-sm font-medium">Status</label>
                  <Select value={eventsStatus} onValueChange={(v) => setEventsStatus(v as 'all' | 'draft' | 'published')}>
                    <SelectTrigger>
                      <SelectValue placeholder="Toate" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Toate</SelectItem>
                      <SelectItem value="published">Published</SelectItem>
                      <SelectItem value="draft">Draft</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    checked={eventsIncludeDeleted}
                    onCheckedChange={(checked) => setEventsIncludeDeleted(Boolean(checked))}
                  />
                  <span className="text-sm">Include șterse</span>
                </div>
                <Button onClick={() => loadEvents(1)} disabled={isLoadingEvents}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Aplică
                </Button>
              </div>

              {isLoadingEvents ? (
                <LoadingPage message="Se încarcă evenimentele..." />
              ) : events.length === 0 ? (
                <p className="text-sm text-muted-foreground">Niciun eveniment găsit.</p>
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Titlu</TableHead>
                        <TableHead>Oraș</TableHead>
                        <TableHead>Dată</TableHead>
                        <TableHead>Owner</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="text-right">Locuri</TableHead>
                        <TableHead className="w-[160px]"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {events.map((e) => {
                        const deleted = Boolean(e.deleted_at);
                        return (
                          <TableRow key={e.id} className={deleted ? 'opacity-70' : undefined}>
                            <TableCell>
                              <Link to={`/events/${e.id}`} className="font-medium hover:underline">
                                {e.title}
                              </Link>
                              {deleted && (
                                <Badge className="ml-2" variant="destructive">
                                  deleted
                                </Badge>
                              )}
                            </TableCell>
                            <TableCell>{e.city || '-'}</TableCell>
                            <TableCell>{formatDateTime(e.start_time)}</TableCell>
                            <TableCell>
                              <div className="text-sm">{e.owner_email}</div>
                              {e.owner_name && (
                                <div className="text-xs text-muted-foreground">{e.owner_name}</div>
                              )}
                            </TableCell>
                            <TableCell>
                              <Badge variant={e.status === 'draft' ? 'secondary' : 'default'}>
                                {e.status || 'published'}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right">
                              {e.seats_taken}/{e.max_seats ?? '-'}
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex justify-end gap-2">
                                <Button asChild variant="outline" size="sm" disabled={deleted}>
                                  <Link to={`/organizer/events/${e.id}/edit`}>
                                    <Edit className="mr-2 h-4 w-4" />
                                    Edit
                                  </Link>
                                </Button>
                                {deleted ? (
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleRestoreEvent(e.id)}
                                  >
                                    <RotateCcw className="mr-2 h-4 w-4" />
                                    Restore
                                  </Button>
                                ) : (
                                  <Button
                                    variant="destructive"
                                    size="sm"
                                    onClick={() => handleDeleteEvent(e.id)}
                                  >
                                    <Trash2 className="mr-2 h-4 w-4" />
                                    Delete
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
                      Pagina {eventsPage} / {totalEventPages} • Total {eventsTotal}
                    </p>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={eventsPage <= 1}
                        onClick={() => loadEvents(eventsPage - 1)}
                      >
                        Înapoi
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={eventsPage >= totalEventPages}
                        onClick={() => loadEvents(eventsPage + 1)}
                      >
                        Înainte
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

