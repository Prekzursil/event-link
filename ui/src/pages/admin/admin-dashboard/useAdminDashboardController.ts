import { useCallback, useEffect, useMemo, useState } from 'react';
import adminService from '@/services/admin.service';
import eventService from '@/services/event.service';
import { useToast } from '@/hooks/use-toast';
import { useI18n } from '@/contexts/LanguageContext';
import type { AdminEvent, AdminStats, AdminUser, PersonalizationMetricsResponse, UserRole } from '@/types';
import type { AdminTab } from './shared';

const USERS_PAGE_SIZE = 20;
const EVENTS_PAGE_SIZE = 20;

function buildUsersFilters(
  page: number,
  search: string,
  role: 'all' | UserRole,
  active: 'all' | 'active' | 'inactive',
) {
  return {
    search: search || undefined,
    role: role === 'all' ? undefined : role,
    is_active: active === 'all' ? undefined : active === 'active',
    page,
    page_size: USERS_PAGE_SIZE,
  };
}

function buildEventsFilters(
  page: number,
  search: string,
  status: 'all' | 'draft' | 'published',
  includeDeleted: boolean,
  flaggedOnly: boolean,
) {
  return {
    search: search || undefined,
    status: status === 'all' ? undefined : status,
    include_deleted: includeDeleted || undefined,
    flagged_only: flaggedOnly || undefined,
    page,
    page_size: EVENTS_PAGE_SIZE,
  };
}

export function useAdminDashboardController() {
  const { toast } = useToast();
  const { language, t } = useI18n();
  const [tab, setTab] = useState<AdminTab>('overview');

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [isLoadingStats, setIsLoadingStats] = useState(false);

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersTotal, setUsersTotal] = useState(0);
  const [usersPage, setUsersPage] = useState(1);
  const [usersSearch, setUsersSearch] = useState('');
  const [usersRole, setUsersRole] = useState<'all' | UserRole>('all');
  const [usersActive, setUsersActive] = useState<'all' | 'active' | 'inactive'>('all');
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);

  const [events, setEvents] = useState<AdminEvent[]>([]);
  const [eventsTotal, setEventsTotal] = useState(0);
  const [eventsPage, setEventsPage] = useState(1);
  const [eventsSearch, setEventsSearch] = useState('');
  const [eventsStatus, setEventsStatus] = useState<'all' | 'draft' | 'published'>('all');
  const [eventsIncludeDeleted, setEventsIncludeDeleted] = useState(false);
  const [eventsFlaggedOnly, setEventsFlaggedOnly] = useState(false);
  const [isLoadingEvents, setIsLoadingEvents] = useState(false);
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

  const loadUsers = useCallback(async (page = usersPage) => {
    setIsLoadingUsers(true);
    try {
      const data = await adminService.getUsers(
        buildUsersFilters(page, usersSearch, usersRole, usersActive),
      );
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
  }, [t, toast, usersActive, usersPage, usersRole, usersSearch]);

  const loadEvents = useCallback(async (page = eventsPage) => {
    setIsLoadingEvents(true);
    try {
      const data = await adminService.getEvents(
        buildEventsFilters(
          page,
          eventsSearch,
          eventsStatus,
          eventsIncludeDeleted,
          eventsFlaggedOnly,
        ),
      );
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
  }, [
    eventsFlaggedOnly,
    eventsIncludeDeleted,
    eventsPage,
    eventsSearch,
    eventsStatus,
    t,
    toast,
  ]);

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
    () => Math.max(1, Math.ceil(usersTotal / USERS_PAGE_SIZE)),
    [usersTotal],
  );
  const totalEventPages = useMemo(
    () => Math.max(1, Math.ceil(eventsTotal / EVENTS_PAGE_SIZE)),
    [eventsTotal],
  );

  const roleLabels = useMemo<Record<UserRole, string>>(() => ({
    student: t.adminDashboard.roles.student,
    organizator: t.adminDashboard.roles.organizer,
    admin: t.adminDashboard.roles.admin,
  }), [t]);

  const registrationsByDay = stats?.registrations_by_day?.slice(-14) ?? [];
  const topTags = stats?.top_tags ?? [];
  const personalizationRows = personalizationMetrics?.items?.slice(-14) ?? [];

  const handleUpdateUser = useCallback(async (
    userId: number,
    patch: Partial<Pick<AdminUser, 'role' | 'is_active'>>,
  ) => {
    const previousUsers = users;
    setUsers((current) => current.map((user) => (user.id === userId ? { ...user, ...patch } : user)));
    try {
      const updated = await adminService.updateUser(userId, patch);
      setUsers((current) => current.map((user) => (user.id === userId ? updated : user)));
      toast({
        title: t.adminDashboard.userUpdatedTitle,
        description: t.adminDashboard.userUpdatedDescription,
      });
    } catch {
      setUsers(previousUsers);
      toast({
        title: t.common.error,
        description: t.adminDashboard.userUpdateErrorDescription,
        variant: 'destructive',
      });
    }
  }, [t, toast, users]);

  const handleDeleteEvent = useCallback(async (eventId: number) => {
    if (!confirm(t.adminDashboard.deleteConfirm)) {
      return;
    }
    try {
      await eventService.deleteEvent(eventId);
      toast({
        title: t.common.success,
        description: t.adminDashboard.eventDeletedDescription,
      });
      await loadEvents(eventsPage);
    } catch {
      toast({
        title: t.common.error,
        description: t.adminDashboard.eventDeleteErrorDescription,
        variant: 'destructive',
      });
    }
  }, [eventsPage, loadEvents, t, toast]);

  const handleRestoreEvent = useCallback(async (eventId: number) => {
    try {
      await eventService.restoreEvent(eventId);
      toast({
        title: t.common.success,
        description: t.adminDashboard.eventRestoredDescription,
      });
      await loadEvents(eventsPage);
    } catch {
      toast({
        title: t.common.error,
        description: t.adminDashboard.eventRestoreErrorDescription,
        variant: 'destructive',
      });
    }
  }, [eventsPage, loadEvents, t, toast]);

  const handleReviewEvent = useCallback(async (eventId: number) => {
    setReviewingEventId(eventId);
    try {
      await adminService.reviewEventModeration(eventId);
      setEvents((current) =>
        current.map((event) => (
          event.id === eventId ? { ...event, moderation_status: 'reviewed' } : event
        )),
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
  }, [t, toast]);

  const handleEnqueueRetrain = useCallback(async () => {
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
  }, [loadPersonalizationMetrics, t, toast]);

  const handleEnqueueDigest = useCallback(async () => {
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
  }, [t, toast]);

  const handleEnqueueFillingFast = useCallback(async () => {
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
  }, [t, toast]);

  return {
    events,
    eventsFlaggedOnly,
    eventsIncludeDeleted,
    eventsPage,
    eventsSearch,
    eventsStatus,
    eventsTotal,
    handleDeleteEvent,
    handleEnqueueDigest,
    handleEnqueueFillingFast,
    handleEnqueueRetrain,
    handleRestoreEvent,
    handleReviewEvent,
    handleUpdateUser,
    isEnqueueingDigest,
    isEnqueueingFillingFast,
    isEnqueueingRetrain,
    isLoadingEvents,
    isLoadingPersonalizationMetrics,
    isLoadingStats,
    isLoadingUsers,
    language,
    loadEvents,
    loadPersonalizationMetrics,
    loadStats,
    loadUsers,
    personalizationMetrics,
    personalizationRows,
    registrationsByDay,
    reviewingEventId,
    roleLabels,
    setEventsFlaggedOnly,
    setEventsIncludeDeleted,
    setEventsSearch,
    setEventsStatus,
    setTab,
    setUsersActive,
    setUsersRole,
    setUsersSearch,
    stats,
    t,
    tab,
    topTags,
    totalEventPages,
    totalUserPages,
    users,
    usersActive,
    usersPage,
    usersRole,
    usersSearch,
    usersTotal,
  };
}

export type AdminDashboardController = ReturnType<typeof useAdminDashboardController>;
