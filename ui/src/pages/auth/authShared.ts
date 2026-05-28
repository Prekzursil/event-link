import type { AxiosError } from 'axios';

/** Shape of the API-shaped error payload returned by the auth endpoints. */
export interface ApiError {
  detail?: string;
  error?: {
    message?: string;
  };
}

/** A single password-strength requirement and whether the input satisfies it. */
export type PasswordRequirement = Readonly<{
  label: string;
  met: boolean;
}>;

/** Extract the most useful message from an API-shaped auth error. */
export function describeApiError(error: unknown, fallback: string): string {
  const axiosError = error as AxiosError<ApiError>;
  return axiosError.response?.data?.detail || axiosError.response?.data?.error?.message || fallback;
}
