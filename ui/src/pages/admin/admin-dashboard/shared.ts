import type { AdminEvent, UserRole } from '@/types';

export type AdminTab = 'overview' | 'users' | 'events';
type ModerationLabels = { flagged: string; reviewed: string; clean: string };
export type ModerationBadgeVariant = 'destructive' | 'secondary' | 'outline';

/**
 * Test helper: role badge variant.
 */
export function roleBadgeVariant(role: UserRole): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (role === 'admin') {
    return 'destructive';
  }
  if (role === 'organizator') {
    return 'secondary';
  }
  return 'outline';
}

/**
 * Test helper: get moderation presentation.
 */
export function getModerationPresentation(
  status: AdminEvent['moderation_status'],
  labels: ModerationLabels,
): { label: string; variant: ModerationBadgeVariant } {
  if (status === 'flagged') {
    return { label: labels.flagged, variant: 'destructive' };
  }
  if (status === 'reviewed') {
    return { label: labels.reviewed, variant: 'secondary' };
  }
  return { label: labels.clean, variant: 'outline' };
}
