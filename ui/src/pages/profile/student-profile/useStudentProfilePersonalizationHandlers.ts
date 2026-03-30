import { useCallback, useState } from 'react';
import eventService from '@/services/event.service';
import type { NotificationPreferences, PersonalizationSettings } from '@/types';
import { type ToastFn, type TranslationStrings } from './studentProfileController.shared';

type PersonalizationHandlerArgs = Readonly<{
  currentNotificationPreferences: NotificationPreferences | null;
  currentPersonalization: PersonalizationSettings | null;
  setNotificationPrefs: (value: NotificationPreferences | null) => void;
  setPersonalization: (value: PersonalizationSettings | null) => void;
  t: TranslationStrings;
  toast: ToastFn;
}>;

/** Persist notification and personalization changes exposed in the profile page. */
export function useStudentProfilePersonalizationHandlers({
  currentNotificationPreferences,
  currentPersonalization,
  setNotificationPrefs,
  setPersonalization,
  t,
  toast,
}: PersonalizationHandlerArgs) {
  const [isSavingNotifications, setIsSavingNotifications] = useState<boolean>(false);

  const handleNotificationPreferenceChange = useCallback(async (
    patch: Partial<NotificationPreferences>,
  ) => {
    if (!currentNotificationPreferences) {
      return;
    }

    const previous = currentNotificationPreferences;
    const next = { ...previous, ...patch };
    setNotificationPrefs(next);
    setIsSavingNotifications(true);
    try {
      const saved = await eventService.updateNotificationPreferences(patch);
      setNotificationPrefs(saved);
      toast({ title: t.notifications.savedTitle, description: t.notifications.savedDescription });
    } catch {
      setNotificationPrefs(previous);
      toast({ title: t.common.error, description: t.notifications.saveErrorDescription, variant: 'destructive' });
    } finally {
      setIsSavingNotifications(false);
    }
  }, [currentNotificationPreferences, setNotificationPrefs, t, toast]);

  const handleUnhideTag = useCallback(async (tagId: number) => {
    if (!currentPersonalization) {
      return;
    }

    try {
      await eventService.unhideTag(tagId);
      setPersonalization({
        ...currentPersonalization,
        hidden_tags: currentPersonalization.hidden_tags.filter((tag) => tag.id !== tagId),
      });
      toast({
        title: t.personalization.tagUnhiddenTitle,
        description: t.personalization.tagUnhiddenDescription,
      });
    } catch {
      toast({
        title: t.common.error,
        description: t.personalization.tagUnhiddenErrorFallback,
        variant: 'destructive',
      });
    }
  }, [currentPersonalization, setPersonalization, t, toast]);

  const handleUnblockOrganizer = useCallback(async (organizerId: number) => {
    if (!currentPersonalization) {
      return;
    }

    try {
      await eventService.unblockOrganizer(organizerId);
      setPersonalization({
        ...currentPersonalization,
        blocked_organizers: currentPersonalization.blocked_organizers.filter((org) => org.id !== organizerId),
      });
      toast({
        title: t.personalization.organizerUnblockedTitle,
        description: t.personalization.organizerUnblockedDescription,
      });
    } catch {
      toast({
        title: t.common.error,
        description: t.personalization.organizerUnblockedErrorFallback,
        variant: 'destructive',
      });
    }
  }, [currentPersonalization, setPersonalization, t, toast]);

  return {
    handleNotificationPreferenceChange,
    handleUnblockOrganizer,
    handleUnhideTag,
    isSavingNotifications,
  };
}
