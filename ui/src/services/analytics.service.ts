import api from './api';

export type InteractionType =
  | 'impression'
  | 'click'
  | 'view'
  | 'dwell'
  | 'share'
  | 'search'
  | 'filter'
  | 'favorite'
  | 'register'
  | 'unregister';

export interface InteractionEventIn {
  interaction_type: InteractionType;
  event_id?: number;
  occurred_at?: string;
  meta?: Record<string, unknown>;
}

export async function recordInteractions(events: InteractionEventIn[]): Promise<void> {
  if (!events.length) return;
  try {
    await api.post('/api/analytics/interactions', { events });
  } catch {
    // best-effort only
  }
}

