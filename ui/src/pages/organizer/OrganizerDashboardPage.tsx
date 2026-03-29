import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import eventService from '@/services/event.service';
import type { Event } from '@/types';
import { Button } from '@/components/ui/button';
import { LoadingPage } from '@/components/ui/loading';
import { useToast } from '@/hooks/use-toast';
import { useI18n } from '@/contexts/LanguageContext';
import { OrganizerBulkTagsDialog } from './organizer-dashboard/OrganizerBulkTagsDialog';
import { OrganizerEventsTable } from './organizer-dashboard/OrganizerEventsTable';
import { OrganizerStatsGrid } from './organizer-dashboard/OrganizerStatsGrid';
import { Plus } from 'lucide-react';

/** Render the organizer dashboard with stats, bulk actions, and event management. */
export function OrganizerDashboardPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedEventIds, setSelectedEventIds] = useState<Set<number>>(() => new Set());
  const [isBulkUpdating, setIsBulkUpdating] = useState(false);
  const [isBulkDraftConfirmationPending, setIsBulkDraftConfirmationPending] = useState(false);
  const [bulkTagsOpen, setBulkTagsOpen] = useState(false);
  const [bulkTagInput, setBulkTagInput] = useState('');
  const [bulkTags, setBulkTags] = useState<string[]>([]);
  const [pendingDeleteEventId, setPendingDeleteEventId] = useState<number | null>(null);
  const { toast } = useToast();
  const { language, t } = useI18n();

  const loadEvents = useCallback(async () => {
    setIsLoading(true);
    try {
      const events = await eventService.getOrganizerEvents();
      setEvents(events);
    } catch {
      toast({
        title: t.organizerDashboard.loadErrorTitle,
        description: t.organizerDashboard.loadErrorDescription,
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [t, toast]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  const selectedCount = selectedEventIds.size;
  const isAllSelected = events.length > 0 && selectedEventIds.size === events.length;
  const isSomeSelected = selectedEventIds.size > 0 && selectedEventIds.size < events.length;
  let selectAllState: boolean | 'indeterminate' = false;
  if (isAllSelected) {
    selectAllState = true;
  } else if (isSomeSelected) {
    selectAllState = 'indeterminate';
  }

  /** Toggle the selection state for one organizer-owned event. */
  const toggleSelected = (eventId: number, checked: boolean) => {
    setSelectedEventIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(eventId);
      } else {
        next.delete(eventId);
      }
      return next;
    });
  };

  /** Toggle the selection state for all currently visible organizer events. */
  const toggleSelectAll = (checked: boolean) => {
    setIsBulkDraftConfirmationPending(false);
    if (!checked) {
      setSelectedEventIds(new Set());
      return;
    }
    setSelectedEventIds(new Set(events.map((event) => event.id)));
  };

  /** Apply a bulk status change to the currently selected organizer events. */
  const handleBulkStatusUpdate = async (status: 'draft' | 'published') => {
    if (status === 'draft' && !isBulkDraftConfirmationPending) {
      setIsBulkDraftConfirmationPending(true);
      toast({
        title: t.organizerDashboard.bulk.confirmDraft,
      });
      return;
    }

    setIsBulkDraftConfirmationPending(false);
    setIsBulkUpdating(true);
    try {
      await eventService.bulkUpdateEventStatus(Array.from(selectedEventIds), status);
      setEvents((prev) =>
        prev.map((event) => (
          selectedEventIds.has(event.id) ? { ...event, status } : event
        ))
      );
      setSelectedEventIds(new Set());
      toast({
        title: t.common.success,
        description:
          status === 'published'
            ? t.organizerDashboard.bulk.statusPublished
            : t.organizerDashboard.bulk.statusDraft,
      });
    } catch {
      toast({
        title: t.common.error,
        description: t.organizerDashboard.bulk.statusError,
        variant: 'destructive',
      });
    } finally {
      setIsBulkUpdating(false);
    }
  };

  /** Open the bulk-tag dialog with a clean input state. */
  const openBulkTags = () => {
    setIsBulkDraftConfirmationPending(false);
    setBulkTags([]);
    setBulkTagInput('');
    setBulkTagsOpen(true);
  };

  /** Add the current bulk-tag input value to the pending tag list. */
  const addBulkTag = () => {
    const tag = bulkTagInput.trim();
    if (!tag) return;
    if (tag.length > 100) {
      toast({
        title: t.common.error,
        description: t.organizerDashboard.bulk.tagTooLong,
        variant: 'destructive',
      });
      return;
    }
    setBulkTags((prev) => (prev.includes(tag) ? prev : [...prev, tag]));
    setBulkTagInput('');
  };

  /** Remove one pending bulk tag before submitting the bulk update. */
  const removeBulkTag = (tagToRemove: string) => {
    setBulkTags((prev) => prev.filter((tag) => tag !== tagToRemove));
  };

  /** Apply the pending bulk tags to the currently selected organizer events. */
  const applyBulkTags = async () => {
    setIsBulkUpdating(true);
    try {
      await eventService.bulkUpdateEventTags(Array.from(selectedEventIds), bulkTags);
      setBulkTagsOpen(false);
      setSelectedEventIds(new Set());
      toast({
        title: t.common.success,
        description: t.organizerDashboard.bulk.tagsSuccess,
      });
    } catch {
      toast({
        title: t.common.error,
        description: t.organizerDashboard.bulk.tagsError,
        variant: 'destructive',
      });
    } finally {
      setIsBulkUpdating(false);
    }
  };

  /** Delete one organizer-owned event after the in-app confirmation toast handshake. */
  const handleDelete = async (eventId: number) => {
    if (pendingDeleteEventId !== eventId) {
      setPendingDeleteEventId(eventId);
      toast({
        title: t.organizerDashboard.deleteConfirm,
      });
      return;
    }

    setPendingDeleteEventId(null);
    try {
      await eventService.deleteEvent(eventId);
      setEvents((prev) => prev.filter((event) => event.id !== eventId));
      toast({
        title: t.organizerDashboard.deleteSuccessTitle,
        description: t.organizerDashboard.deleteSuccessDescription,
      });
    } catch {
      toast({
        title: t.organizerDashboard.deleteErrorTitle,
        description: t.organizerDashboard.deleteErrorDescription,
        variant: 'destructive',
      });
    }
  };

  if (isLoading) {
    return <LoadingPage message={t.organizerDashboard.loading} />;
  }

  const now = new Date();
  const upcomingEvents = events.filter((e) => new Date(e.start_time) >= now);
  const totalParticipants = events.reduce((acc, e) => acc + e.seats_taken, 0);
  const draftEvents = events.filter((e) => e.status === 'draft');

  return (
    <div className="container mx-auto px-4 py-8">
      <OrganizerBulkTagsDialog
        open={bulkTagsOpen}
        onOpenChange={setBulkTagsOpen}
        inputValue={bulkTagInput}
        onInputChange={setBulkTagInput}
        tags={bulkTags}
        onAddTag={addBulkTag}
        onRemoveTag={removeBulkTag}
        onApply={applyBulkTags}
        isBusy={isBulkUpdating}
        texts={t.organizerDashboard}
        cancelText={t.common.cancel}
      />

      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t.organizerDashboard.title}</h1>
          <p className="mt-2 text-muted-foreground">{t.organizerDashboard.subtitle}</p>
        </div>
        <Button asChild>
          <Link to="/organizer/events/new">
            <Plus className="mr-2 h-4 w-4" />
            {t.organizerDashboard.newEvent}
          </Link>
        </Button>
      </div>

      <OrganizerStatsGrid
        texts={t.organizerDashboard}
        totalEvents={events.length}
        upcomingEvents={upcomingEvents.length}
        totalParticipants={totalParticipants}
        draftEvents={draftEvents.length}
      />

      <OrganizerEventsTable
        events={events}
        language={language}
        now={now}
        texts={t.organizerDashboard}
        selectedEventIds={selectedEventIds}
        selectedCount={selectedCount}
        selectAllState={selectAllState}
        isBulkUpdating={isBulkUpdating}
        onSelectAll={toggleSelectAll}
        onToggleSelected={toggleSelected}
        onBulkStatusUpdate={handleBulkStatusUpdate}
        onOpenBulkTags={openBulkTags}
        onClearSelection={() => setSelectedEventIds(new Set())}
        onDelete={handleDelete}
      />
    </div>
  );
}
