export type UserRole = 'student' | 'organizator';

export interface User {
  id: number;
  email: string;
  role: UserRole;
  full_name?: string;
}

export interface Tag {
  id: number;
  name: string;
}

export interface Event {
  id: number;
  title: string;
  description?: string;
  category?: string;
  start_time: string;
  end_time?: string;
  location?: string;
  max_seats?: number;
  cover_url?: string;
  owner_id: number;
  owner_name?: string;
  tags: Tag[];
  seats_taken: number;
  recommendation_reason?: string;
  status?: string;
  publish_at?: string;
}

export interface EventDetail extends Event {
  is_registered: boolean;
  is_owner: boolean;
  available_seats?: number | null;
  is_favorite: boolean;
}

export interface PaginatedEvents {
  items: Event[];
  total: number;
  page: number;
  page_size: number;
}

export interface Participant {
  id: number;
  email: string;
  full_name?: string;
  registration_time: string;
  attended: boolean;
}

export interface ParticipantList {
  event_id: number;
  title: string;
  cover_url?: string;
  seats_taken: number;
  max_seats?: number;
  participants: Participant[];
  total: number;
  page: number;
  page_size: number;
}

export interface OrganizerProfile {
  user_id: number;
  email: string;
  full_name?: string;
  org_name?: string;
  org_description?: string;
  org_logo_url?: string;
  org_website?: string;
  events: Event[];
}

export interface StudentProfile {
  user_id: number;
  email: string;
  full_name?: string;
  interest_tags: Tag[];
}

export interface StudentProfileUpdate {
  full_name?: string;
  interest_tag_ids?: number[];
}

export interface AuthToken {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  role: UserRole;
  user_id: number;
}

export interface EventFilters {
  search?: string;
  category?: string;
  start_date?: string;
  end_date?: string;
  tags?: string[];
  location?: string;
  include_past?: boolean;
  page?: number;
  page_size?: number;
}

export interface EventFormData {
  title: string;
  description?: string;
  category?: string;
  start_time: string;
  end_time?: string;
  location?: string;
  max_seats?: number;
  cover_url?: string;
  tags?: string[];
  status?: 'draft' | 'published';
  publish_at?: string;
}
