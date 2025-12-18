import api from './api';
import type {
  AdminStats,
  AdminUser,
  AdminUserUpdate,
  EnqueuedJobResponse,
  PaginatedAdminEvents,
  PaginatedAdminUsers,
  PersonalizationMetricsResponse,
  UserRole,
} from '../types';

export interface AdminUsersFilters {
  search?: string;
  role?: UserRole;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}

export interface AdminEventsFilters {
  search?: string;
  category?: string;
  city?: string;
  status?: 'draft' | 'published';
  include_deleted?: boolean;
  flagged_only?: boolean;
  page?: number;
  page_size?: number;
}

export const adminService = {
  async getStats(days = 30, topTagsLimit = 10): Promise<AdminStats> {
    const params = new URLSearchParams();
    params.append('days', days.toString());
    params.append('top_tags_limit', topTagsLimit.toString());
    const response = await api.get<AdminStats>(`/api/admin/stats?${params.toString()}`);
    return response.data;
  },

  async getUsers(filters: AdminUsersFilters = {}): Promise<PaginatedAdminUsers> {
    const params = new URLSearchParams();
    if (filters.search) params.append('search', filters.search);
    if (filters.role) params.append('role', filters.role);
    if (filters.is_active !== undefined) params.append('is_active', String(filters.is_active));
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    const response = await api.get<PaginatedAdminUsers>(`/api/admin/users?${params.toString()}`);
    return response.data;
  },

  async updateUser(userId: number, payload: AdminUserUpdate): Promise<AdminUser> {
    const response = await api.patch<AdminUser>(`/api/admin/users/${userId}`, payload);
    return response.data;
  },

  async getEvents(filters: AdminEventsFilters = {}): Promise<PaginatedAdminEvents> {
    const params = new URLSearchParams();
    if (filters.search) params.append('search', filters.search);
    if (filters.category) params.append('category', filters.category);
    if (filters.city) params.append('city', filters.city);
    if (filters.status) params.append('status', filters.status);
    if (filters.include_deleted) params.append('include_deleted', 'true');
    if (filters.flagged_only) params.append('flagged_only', 'true');
    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    const response = await api.get<PaginatedAdminEvents>(`/api/admin/events?${params.toString()}`);
    return response.data;
  },

  async reviewEventModeration(eventId: number): Promise<{ status: string }> {
    const response = await api.post<{ status: string }>(`/api/admin/events/${eventId}/moderation/review`);
    return response.data;
  },

  async getPersonalizationMetrics(days = 30): Promise<PersonalizationMetricsResponse> {
    const params = new URLSearchParams();
    params.append('days', days.toString());
    const response = await api.get<PersonalizationMetricsResponse>(`/api/admin/personalization/metrics?${params.toString()}`);
    return response.data;
  },

  async enqueueRecommendationsRetrain(payload?: Record<string, unknown>): Promise<EnqueuedJobResponse> {
    const response = await api.post<EnqueuedJobResponse>('/api/admin/personalization/retrain', payload ?? {});
    return response.data;
  },

  async enqueueWeeklyDigest(payload?: Record<string, unknown>): Promise<EnqueuedJobResponse> {
    const response = await api.post<EnqueuedJobResponse>('/api/admin/notifications/weekly-digest', payload ?? {});
    return response.data;
  },

  async enqueueFillingFast(payload?: Record<string, unknown>): Promise<EnqueuedJobResponse> {
    const response = await api.post<EnqueuedJobResponse>('/api/admin/notifications/filling-fast', payload ?? {});
    return response.data;
  },
};

export default adminService;
