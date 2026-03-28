import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import eventService from '@/services/event.service';
import type { OrganizerProfile } from '@/types';
import { useI18n } from '@/contexts/LanguageContext';

function splitEvents(profile: OrganizerProfile | null) {
  const now = new Date();
  const events = profile?.events ?? [];
  return {
    upcomingEvents: events.filter((event) => new Date(event.start_time) >= now),
    pastEvents: events.filter((event) => new Date(event.start_time) < now),
  };
}

function displayName(profile: OrganizerProfile | null, fallback: string) {
  return profile?.org_name || profile?.full_name || fallback;
}

function initialsFromName(name: string) {
  return name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

export function useOrganizerProfileController() {
  const { id } = useParams<{ id: string }>();
  const { t } = useI18n();
  const [profile, setProfile] = useState<OrganizerProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  const loadProfile = useCallback(async (organizerId: number) => {
    setIsLoading(true);
    setHasError(false);
    try {
      const data = await eventService.getOrganizerProfile(organizerId);
      setProfile(data);
    } catch (error) {
      console.error('Failed to load organizer profile:', error);
      setHasError(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const organizerId = Number(id);
    if (!Number.isFinite(organizerId) || organizerId <= 0) {
      setProfile(null);
      setHasError(false);
      setIsLoading(false);
      return;
    }
    void loadProfile(organizerId);
  }, [id, loadProfile]);

  const { upcomingEvents, pastEvents } = useMemo(() => splitEvents(profile), [profile]);
  const organizerDisplayName = useMemo(
    () => displayName(profile, t.organizerProfile.organizerFallback),
    [profile, t],
  );
  const initials = useMemo(
    () => initialsFromName(organizerDisplayName),
    [organizerDisplayName],
  );

  return {
    hasError,
    initials,
    isLoading,
    organizerDisplayName,
    pastEvents,
    profile,
    t,
    upcomingEvents,
  };
}

export type OrganizerProfileController = ReturnType<typeof useOrganizerProfileController>;
