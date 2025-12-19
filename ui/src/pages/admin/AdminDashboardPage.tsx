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
import { useI18n } from '@/contexts/LanguageContext';
import type { AdminEvent, AdminStats, AdminUser, PersonalizationMetricsResponse, UserRole } from '@/types';
import { formatDateTime } from '@/lib/utils';
import { Bell, Edit, Mail, RefreshCw, RotateCcw, ShieldCheck, Sparkles, Trash2 } from 'lucide-react';

type AdminTab = 'overview' | 'users' | 'events';

function roleBadgeVariant(role: UserRole): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (role === 'admin') return 'destructive';
  if (role === 'organizator') return 'secondary';
  return 'outline';
}

export function AdminDashboardPage() {
  const { toast } = useToast();
  const { language, t } = useI18n();
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
  const [eventsFlaggedOnly, setEventsFlaggedOnly] = useState(false);
  const [reviewingEventId, setReviewingEventId] = useState<number | null>(null);

  const [personalizationMetrics, setPersonalizationMetrics] =
    useState<PersonalizationMetricsResponse | null>(null);
  const [isLoadingPersonalizationMetrics, setIsLoadingPersonalizationMetrics] = useState(false);
  const [isEnqueueingRetrain, setIsEnqueueingRetrain] = useState(false);
  const [isEnqueueingDigest, setIsEnqueueingDigest] = useState(false);
  const [isEnqueueingFillingFast, setIsEnqueueingFillingFast] = useState(false);

  const loadStats = useCallback(async () => {
    setIsLoadingStats(true);
    try {
      const data = await adminService.getStats();
      setStats(data);
    } catch {
      toast({
        title: t.common.error,
        description: t.adminDashboard.loadStatsErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsLoadingStats(false);
    }
  }, [t, toast]);

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
          title: t.common.error,
          description: t.adminDashboard.loadUsersErrorDescription,
          variant: 'destructive',
        });
      } finally {
        setIsLoadingUsers(false);
      }
    },
    [t, toast, usersActive, usersPage, usersPageSize, usersRole, usersSearch],
  );

  const loadEvents = useCallback(
    async (page = eventsPage) => {
      setIsLoadingEvents(true);
      try {
        const data = await adminService.getEvents({
          search: eventsSearch || undefined,
          status: eventsStatus === 'all' ? undefined : eventsStatus,
          include_deleted: eventsIncludeDeleted || undefined,
          flagged_only: eventsFlaggedOnly || undefined,
          page,
          page_size: eventsPageSize,
        });
        setEvents(data.items);
        setEventsTotal(data.total);
        setEventsPage(data.page);
      } catch {
        toast({
          title: t.common.error,
          description: t.adminDashboard.loadEventsErrorDescription,
          variant: 'destructive',
        });
      } finally {
        setIsLoadingEvents(false);
      }
    },
    [eventsFlaggedOnly, eventsIncludeDeleted, eventsPage, eventsPageSize, eventsSearch, eventsStatus, t, toast],
  );

  const loadPersonalizationMetrics = useCallback(async () => {
    setIsLoadingPersonalizationMetrics(true);
    try {
      const data = await adminService.getPersonalizationMetrics(30);
      setPersonalizationMetrics(data);
    } catch {
      toast({
        title: t.common.error,
        description: t.adminDashboard.personalizationMetrics.loadErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsLoadingPersonalizationMetrics(false);
    }
  }, [t, toast]);

  useEffect(() => {
    loadStats();
    loadPersonalizationMetrics();
  }, [loadPersonalizationMetrics, loadStats]);

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
      toast({ title: t.adminDashboard.userUpdatedTitle, description: t.adminDashboard.userUpdatedDescription });
    } catch {
      setUsers(prev);
      toast({
        title: t.common.error,
        description: t.adminDashboard.userUpdateErrorDescription,
        variant: 'destructive',
      });
    }
  };

  const handleDeleteEvent = async (eventId: number) => {
    if (!confirm(t.adminDashboard.deleteConfirm)) return;
    try {
      await eventService.deleteEvent(eventId);
      toast({ title: t.common.success, description: t.adminDashboard.eventDeletedDescription });
      await loadEvents(eventsPage);
    } catch {
      toast({
        title: t.common.error,
        description: t.adminDashboard.eventDeleteErrorDescription,
        variant: 'destructive',
      });
    }
  };

  const handleRestoreEvent = async (eventId: number) => {
    try {
      await eventService.restoreEvent(eventId);
      toast({ title: t.common.success, description: t.adminDashboard.eventRestoredDescription });
      await loadEvents(eventsPage);
    } catch {
      toast({
        title: t.common.error,
        description: t.adminDashboard.eventRestoreErrorDescription,
        variant: 'destructive',
      });
    }
  };

  const handleEnqueueRetrain = async () => {
    setIsEnqueueingRetrain(true);
    try {
      const job = await adminService.enqueueRecommendationsRetrain();
      toast({
        title: t.adminDashboard.personalizationMetrics.retrainQueuedTitle,
        description: t.adminDashboard.personalizationMetrics.retrainQueuedDescription.replace('{jobId}', String(job.job_id)),
      });
      await loadPersonalizationMetrics();
    } catch {
      toast({
        title: t.common.error,
        description: t.adminDashboard.personalizationMetrics.retrainQueuedErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsEnqueueingRetrain(false);
    }
  };

  const handleEnqueueDigest = async () => {
    setIsEnqueueingDigest(true);
    try {
      const job = await adminService.enqueueWeeklyDigest();
      toast({
        title: t.adminDashboard.notifications.digestQueuedTitle,
        description: t.adminDashboard.notifications.digestQueuedDescription.replace('{jobId}', String(job.job_id)),
      });
    } catch {
      toast({
        title: t.common.error,
        description: t.adminDashboard.notifications.digestQueuedErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsEnqueueingDigest(false);
    }
  };

  const handleEnqueueFillingFast = async () => {
    setIsEnqueueingFillingFast(true);
    try {
      const job = await adminService.enqueueFillingFast();
      toast({
        title: t.adminDashboard.notifications.fillingFastQueuedTitle,
        description: t.adminDashboard.notifications.fillingFastQueuedDescription.replace('{jobId}', String(job.job_id)),
      });
    } catch {
      toast({
        title: t.common.error,
        description: t.adminDashboard.notifications.fillingFastQueuedErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsEnqueueingFillingFast(false);
    }
  };

  if (!stats && isLoadingStats) {
    return <LoadingPage message={t.adminDashboard.loading} />;
  }

  const roleLabel: Record<UserRole, string> = {
    student: t.adminDashboard.roles.student,
    organizator: t.adminDashboard.roles.organizer,
    admin: t.adminDashboard.roles.admin,
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t.adminDashboard.title}</h1>
          <p className="mt-2 text-muted-foreground">{t.adminDashboard.subtitle}</p>
        </div>
        <Button variant="outline" onClick={() => loadStats()} disabled={isLoadingStats}>
          <RefreshCw className="mr-2 h-4 w-4" />
          {t.adminDashboard.reload}
        </Button>
      </div>

      <Tabs value={tab} onValueChange={(value) => setTab(value as AdminTab)}>
        <TabsList className="h-auto w-full flex flex-wrap justify-start">
          <TabsTrigger value="overview">{t.adminDashboard.tabs.overview}</TabsTrigger>
          <TabsTrigger value="users">{t.adminDashboard.tabs.users}</TabsTrigger>
          <TabsTrigger value="events">{t.adminDashboard.tabs.events}</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6 space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">{t.adminDashboard.stats.totalUsers}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.total_users ?? 0}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">{t.adminDashboard.stats.totalEvents}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.total_events ?? 0}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">{t.adminDashboard.stats.totalRegistrations}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats?.total_registrations ?? 0}</div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>{t.adminDashboard.registrationsByDay.title}</CardTitle>
              </CardHeader>
              <CardContent>
                {!stats?.registrations_by_day?.length ? (
                  <p className="text-sm text-muted-foreground">{t.adminDashboard.noData}</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t.adminDashboard.registrationsByDay.day}</TableHead>
                        <TableHead className="text-right">{t.adminDashboard.registrationsByDay.registrations}</TableHead>
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
                <CardTitle>{t.adminDashboard.topTags.title}</CardTitle>
              </CardHeader>
              <CardContent>
                {!stats?.top_tags?.length ? (
                  <p className="text-sm text-muted-foreground">{t.adminDashboard.noData}</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t.adminDashboard.topTags.tag}</TableHead>
                        <TableHead className="text-right">{t.adminDashboard.topTags.registrations}</TableHead>
                        <TableHead className="text-right">{t.adminDashboard.topTags.events}</TableHead>
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

          <Card>
            <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <CardTitle>{t.adminDashboard.personalizationMetrics.title}</CardTitle>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={handleEnqueueRetrain} disabled={isEnqueueingRetrain}>
                  <Sparkles className="mr-2 h-4 w-4" />
                  {isEnqueueingRetrain
                    ? t.adminDashboard.personalizationMetrics.queueing
                    : t.adminDashboard.personalizationMetrics.retrainNow}
                </Button>
                <Button variant="outline" size="sm" onClick={handleEnqueueDigest} disabled={isEnqueueingDigest}>
                  <Mail className="mr-2 h-4 w-4" />
                  {isEnqueueingDigest ? t.adminDashboard.notifications.queueing : t.adminDashboard.notifications.enqueueDigest}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleEnqueueFillingFast}
                  disabled={isEnqueueingFillingFast}
                >
                  <Bell className="mr-2 h-4 w-4" />
                  {isEnqueueingFillingFast
                    ? t.adminDashboard.notifications.queueing
                    : t.adminDashboard.notifications.enqueueFillingFast}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {isLoadingPersonalizationMetrics ? (
                <LoadingPage message={t.adminDashboard.personalizationMetrics.loading} />
              ) : !personalizationMetrics?.items?.length ? (
                <p className="text-sm text-muted-foreground">{t.adminDashboard.noData}</p>
              ) : (
                <div className="space-y-4">
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                    <div className="rounded-lg border p-3">
                      <div className="text-xs font-medium text-muted-foreground">
                        {t.adminDashboard.personalizationMetrics.totals.impressions}
                      </div>
                      <div className="text-lg font-bold">{personalizationMetrics.totals.impressions}</div>
                    </div>
                    <div className="rounded-lg border p-3">
                      <div className="text-xs font-medium text-muted-foreground">
                        {t.adminDashboard.personalizationMetrics.totals.clicks}
                      </div>
                      <div className="text-lg font-bold">{personalizationMetrics.totals.clicks}</div>
                    </div>
                    <div className="rounded-lg border p-3">
                      <div className="text-xs font-medium text-muted-foreground">
                        {t.adminDashboard.personalizationMetrics.totals.registrations}
                      </div>
                      <div className="text-lg font-bold">{personalizationMetrics.totals.registrations}</div>
                    </div>
                    <div className="rounded-lg border p-3">
                      <div className="text-xs font-medium text-muted-foreground">
                        {t.adminDashboard.personalizationMetrics.totals.ctr}
                      </div>
                      <div className="text-lg font-bold">{Math.round(personalizationMetrics.totals.ctr * 100)}%</div>
                    </div>
                    <div className="rounded-lg border p-3">
                      <div className="text-xs font-medium text-muted-foreground">
                        {t.adminDashboard.personalizationMetrics.totals.conversion}
                      </div>
                      <div className="text-lg font-bold">
                        {Math.round(personalizationMetrics.totals.registration_conversion * 100)}%
                      </div>
                    </div>
                  </div>

                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t.adminDashboard.personalizationMetrics.table.day}</TableHead>
                        <TableHead className="text-right">{t.adminDashboard.personalizationMetrics.table.impressions}</TableHead>
                        <TableHead className="text-right">{t.adminDashboard.personalizationMetrics.table.clicks}</TableHead>
                        <TableHead className="text-right">{t.adminDashboard.personalizationMetrics.table.registrations}</TableHead>
                        <TableHead className="text-right">{t.adminDashboard.personalizationMetrics.table.ctr}</TableHead>
                        <TableHead className="text-right">{t.adminDashboard.personalizationMetrics.table.conversion}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {personalizationMetrics.items.slice(-14).map((row) => (
                        <TableRow key={row.date}>
                          <TableCell>{row.date}</TableCell>
                          <TableCell className="text-right">{row.impressions}</TableCell>
                          <TableCell className="text-right">{row.clicks}</TableCell>
                          <TableCell className="text-right">{row.registrations}</TableCell>
                          <TableCell className="text-right">{Math.round(row.ctr * 100)}%</TableCell>
                          <TableCell className="text-right">{Math.round(row.registration_conversion * 100)}%</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t.adminDashboard.users.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end">
                <div className="flex-1">
                  <label className="mb-1 block text-sm font-medium">{t.adminDashboard.users.searchLabel}</label>
                  <Input
                    value={usersSearch}
                    onChange={(e) => setUsersSearch(e.target.value)}
                    placeholder={t.adminDashboard.users.searchPlaceholder}
                  />
                </div>
                <div className="w-full md:w-56">
                  <label className="mb-1 block text-sm font-medium">{t.adminDashboard.users.roleLabel}</label>
                  <Select value={usersRole} onValueChange={(v) => setUsersRole(v as 'all' | UserRole)}>
                    <SelectTrigger>
                      <SelectValue placeholder={t.adminDashboard.users.all} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t.adminDashboard.users.all}</SelectItem>
                      <SelectItem value="student">{t.adminDashboard.roles.student}</SelectItem>
                      <SelectItem value="organizator">{t.adminDashboard.roles.organizer}</SelectItem>
                      <SelectItem value="admin">{t.adminDashboard.roles.admin}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="w-full md:w-56">
                  <label className="mb-1 block text-sm font-medium">{t.adminDashboard.users.statusLabel}</label>
                  <Select value={usersActive} onValueChange={(v) => setUsersActive(v as 'all' | 'active' | 'inactive')}>
                    <SelectTrigger>
                      <SelectValue placeholder={t.adminDashboard.users.all} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t.adminDashboard.users.all}</SelectItem>
                      <SelectItem value="active">{t.adminDashboard.users.statusActive}</SelectItem>
                      <SelectItem value="inactive">{t.adminDashboard.users.statusInactive}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <Button onClick={() => loadUsers(1)} disabled={isLoadingUsers}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  {t.adminDashboard.users.apply}
                </Button>
              </div>

              {isLoadingUsers ? (
                <LoadingPage message={t.adminDashboard.users.loading} />
              ) : users.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t.adminDashboard.users.empty}</p>
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t.adminDashboard.users.table.email}</TableHead>
                        <TableHead>{t.adminDashboard.users.table.role}</TableHead>
                        <TableHead>{t.adminDashboard.users.table.active}</TableHead>
                        <TableHead>{t.adminDashboard.users.table.created}</TableHead>
                        <TableHead>{t.adminDashboard.users.table.lastSeen}</TableHead>
                        <TableHead className="text-right">{t.adminDashboard.users.table.registrations}</TableHead>
                        <TableHead className="text-right">{t.adminDashboard.users.table.attendances}</TableHead>
                        <TableHead className="text-right">{t.adminDashboard.users.table.events}</TableHead>
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
                              <Badge variant={roleBadgeVariant(u.role)}>{roleLabel[u.role]}</Badge>
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
                                  <SelectItem value="student">{t.adminDashboard.roles.student}</SelectItem>
                                  <SelectItem value="organizator">{t.adminDashboard.roles.organizer}</SelectItem>
                                  <SelectItem value="admin">{t.adminDashboard.roles.admin}</SelectItem>
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
                          <TableCell>{formatDateTime(u.created_at, language)}</TableCell>
                          <TableCell>{u.last_seen_at ? formatDateTime(u.last_seen_at, language) : '-'}</TableCell>
                          <TableCell className="text-right">{u.registrations_count}</TableCell>
                          <TableCell className="text-right">{u.attended_count}</TableCell>
                          <TableCell className="text-right">{u.events_created_count}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>

                  <div className="mt-4 flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">
                      {t.adminDashboard.pagination.page} {usersPage} / {totalUserPages} • {t.adminDashboard.pagination.total} {usersTotal}
                    </p>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={usersPage <= 1}
                        onClick={() => loadUsers(usersPage - 1)}
                      >
                        {t.adminDashboard.pagination.prev}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={usersPage >= totalUserPages}
                        onClick={() => loadUsers(usersPage + 1)}
                      >
                        {t.adminDashboard.pagination.next}
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
              <CardTitle>{t.adminDashboard.events.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end">
                <div className="flex-1">
                  <label className="mb-1 block text-sm font-medium">{t.adminDashboard.events.searchLabel}</label>
                  <Input
                    value={eventsSearch}
                    onChange={(e) => setEventsSearch(e.target.value)}
                    placeholder={t.adminDashboard.events.searchPlaceholder}
                  />
                </div>
                <div className="w-full md:w-56">
                  <label className="mb-1 block text-sm font-medium">{t.adminDashboard.events.statusLabel}</label>
                  <Select value={eventsStatus} onValueChange={(v) => setEventsStatus(v as 'all' | 'draft' | 'published')}>
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
                      {events.map((e) => {
                        const deleted = Boolean(e.deleted_at);
                        const statusLabel =
                          e.status === 'draft' ? t.adminDashboard.events.statusDraft : t.adminDashboard.events.statusPublished;
                        const moderationStatus = e.moderation_status || 'clean';
                        const moderationLabel =
                          moderationStatus === 'flagged'
                            ? t.adminDashboard.events.moderation.flagged
                            : moderationStatus === 'reviewed'
                              ? t.adminDashboard.events.moderation.reviewed
                              : t.adminDashboard.events.moderation.clean;
                        const moderationVariant =
                          moderationStatus === 'flagged'
                            ? 'destructive'
                            : moderationStatus === 'reviewed'
                              ? 'secondary'
                              : 'outline';
                        return (
                          <TableRow key={e.id} className={deleted ? 'opacity-70' : undefined}>
                            <TableCell>
                              <Link to={`/events/${e.id}`} className="font-medium hover:underline">
                                {e.title}
                              </Link>
                              {deleted && (
                                <Badge className="ml-2" variant="destructive">
                                  {t.adminDashboard.events.deletedBadge}
                                </Badge>
                              )}
                            </TableCell>
                            <TableCell>{e.city || '-'}</TableCell>
                            <TableCell>{formatDateTime(e.start_time, language)}</TableCell>
                            <TableCell>
                              <div className="text-sm">{e.owner_email}</div>
                              {e.owner_name && (
                                <div className="text-xs text-muted-foreground">{e.owner_name}</div>
                              )}
                            </TableCell>
                            <TableCell>
                              <Badge variant={e.status === 'draft' ? 'secondary' : 'default'}>
                                {statusLabel}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <div className="space-y-1">
                                <Badge variant={moderationVariant}>{moderationLabel}</Badge>
                                {typeof e.moderation_score === 'number' && (
                                  <div className="text-xs text-muted-foreground">
                                    {t.adminDashboard.events.moderation.scoreLabel} {e.moderation_score.toFixed(2)}
                                  </div>
                                )}
                                {e.moderation_flags?.length ? (
                                  <div className="text-xs text-muted-foreground">
                                    {e.moderation_flags.slice(0, 3).join(', ')}
                                    {e.moderation_flags.length > 3 ? '…' : ''}
                                  </div>
                                ) : null}
                              </div>
                            </TableCell>
                            <TableCell className="text-right">
                              {e.seats_taken}/{e.max_seats ?? '-'}
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex justify-end gap-2">
                                <Button asChild variant="outline" size="sm" disabled={deleted}>
                                  <Link to={`/organizer/events/${e.id}/edit`}>
                                    <Edit className="mr-2 h-4 w-4" />
                                    {t.adminDashboard.events.actions.edit}
                                  </Link>
                                </Button>
                                {moderationStatus === 'flagged' && !deleted && (
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    disabled={reviewingEventId === e.id}
                                    onClick={async () => {
                                      setReviewingEventId(e.id);
                                      try {
                                        await adminService.reviewEventModeration(e.id);
                                        setEvents((prev) =>
                                          prev.map((row) =>
                                            row.id === e.id ? { ...row, moderation_status: 'reviewed' } : row,
                                          ),
                                        );
                                        toast({
                                          title: t.adminDashboard.events.moderation.reviewedTitle,
                                          description: t.adminDashboard.events.moderation.reviewedDescription,
                                        });
                                      } catch {
                                        toast({
                                          title: t.common.error,
                                          description: t.adminDashboard.events.moderation.reviewErrorDescription,
                                          variant: 'destructive',
                                        });
                                      } finally {
                                        setReviewingEventId(null);
                                      }
                                    }}
                                  >
                                    <ShieldCheck className="mr-2 h-4 w-4" />
                                    {reviewingEventId === e.id
                                      ? t.adminDashboard.events.moderation.reviewing
                                      : t.adminDashboard.events.moderation.markReviewed}
                                  </Button>
                                )}
                                {deleted ? (
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleRestoreEvent(e.id)}
                                  >
                                    <RotateCcw className="mr-2 h-4 w-4" />
                                    {t.adminDashboard.events.actions.restore}
                                  </Button>
                                ) : (
                                  <Button
                                    variant="destructive"
                                    size="sm"
                                    onClick={() => handleDeleteEvent(e.id)}
                                  >
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
        </TabsContent>
      </Tabs>
    </div>
  );
}
