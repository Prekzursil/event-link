export interface Tag {
  id: number;
  name: string;
}

export interface EventItem {
  id: number;
  title: string;
  description?: string;
  category?: string;
  start_time: string;
  end_time?: string;
  location?: string;
  max_seats?: number;
  owner_id: number;
  owner_name?: string;
  cover_url?: string | null;
  tags: Tag[];
  seats_taken: number;
  recommendation_reason?: string;
}

export interface EventDetail extends EventItem {
  is_registered: boolean;
  is_owner: boolean;
  available_seats?: number;
}

export interface PaginatedEvents {
  items: EventItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  role: string;
  user_id: number;
}

export interface Participant {
  id: number;
  email: string;
  full_name?: string;
  registration_time: string;
  attended?: boolean;
}

export interface ParticipantList {
  event_id: number;
  title: string;
  cover_url?: string | null;
  seats_taken: number;
  max_seats?: number;
  participants: Participant[];
  total?: number;
  page?: number;
  page_size?: number;
}

export interface User {
  id: number;
  email: string;
  role: 'student' | 'organizator';
  full_name?: string;
}
