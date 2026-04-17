/**
 * Pure utilities extracted from ParticipantsPage.tsx so the page module stays
 * below Lizard's NLOC limit. Covers CSV export, attendance-mutation choreography,
 * email-draft validation, and small helpers for skeleton keys / sort toggles.
 */

import type { Dispatch, SetStateAction } from 'react';
import eventService from '@/services/event.service';
import type { ParticipantList, Participant } from '@/types';
import { formatDateTime } from '@/lib/utils';
import { useI18n } from '@/contexts/LanguageContext';
import { useToast } from '@/hooks/use-toast';

export type ParticipantsTexts = ReturnType<typeof useI18n>['t'];

export type AttendanceMutationArgs = Readonly<{
  attended: boolean;
  currentData: ParticipantList;
  eventId: number;
  participant: Participant;
  setData: Dispatch<SetStateAction<ParticipantList | null>>;
  setUpdatingAttendance: Dispatch<SetStateAction<Set<number>>>;
  t: ParticipantsTexts;
  toast: ReturnType<typeof useToast>['toast'];
}>;

export type EmailSendArgs = Readonly<{
  emailMessage: string;
  emailSubject: string;
  eventId: number;
  onSuccess: () => void;
  setIsEmailing: Dispatch<SetStateAction<boolean>>;
  t: ParticipantsTexts;
  toast: ReturnType<typeof useToast>['toast'];
}>;

/** Generate a bounded list of placeholder-row keys for the loading skeleton. */
export function skeletonKeys(pageSize: number) {
  return Array.from(
    { length: Math.min(pageSize, 10) },
    (_, position) => `skeleton-${position + 1}`,
  );
}

/** Update a single participant's attended flag within the current table rows. */
export function participantRowsWithAttendance(
  participants: Participant[],
  participantId: number,
  attended: boolean,
) {
  return participants.map((entry) =>
    entry.id === participantId ? { ...entry, attended } : entry,
  );
}

/** Add or remove a participant identifier from the in-flight attendance set. */
export function toggledParticipantSet(
  previous: Set<number>,
  participantId: number,
  active: boolean,
) {
  const next = new Set(previous);
  if (active) {
    next.add(participantId);
  } else {
    next.delete(participantId);
  }
  return next;
}

/** Request one page of organizer participants using the active table settings. */
export function loadParticipantsPage(
  eventId: number,
  page: number,
  pageSize: number,
  sortBy: string,
  sortDir: 'asc' | 'desc',
) {
  return eventService.getEventParticipants(eventId, page, pageSize, sortBy, sortDir);
}

/** Optimistically toggle attendee presence and roll back the row on failure. */
export async function mutateAttendance(args: AttendanceMutationArgs) {
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
    participants: participantRowsWithAttendance(
      currentData.participants, participantId, attended,
    ),
  });
  try {
    await eventService.updateParticipantAttendance(eventId, participantId, attended);
    toast({
      title: t.common.success,
      description: attended
        ? t.participants.attendanceConfirmed
        : t.participants.attendanceCleared,
    });
  } catch {
    setData({
      ...currentData,
      participants: participantRowsWithAttendance(
        currentData.participants, participantId, previous,
      ),
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
export function escapeCsv(value: string) {
  return `"${value.split('"').join('""')}"`;
}

/** Build the exported participant CSV filename from the event title. */
export function csvFilename(title: string, t: ParticipantsTexts) {
  return `${t.participants.csvFilePrefix}-${title
    .trim()
    .split(' ')
    .filter(Boolean)
    .join('-')}.csv`;
}

/** Create and trigger the CSV export for the currently loaded participants. */
export function downloadParticipantsCsv(
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
export function validateEmailDraft(
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
export async function sendParticipantsEmail({
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
      description: t.participants.emailSuccess.replace(
        '{count}', String(response.recipients),
      ),
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
