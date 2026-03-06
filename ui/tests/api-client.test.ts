import axios, { AxiosError } from 'axios';
import { beforeEach, describe, expect, it, vi } from 'vitest';

type RequestConfigLike = {
  headers?: Record<string, string>;
  _retry?: boolean;
} & Record<string, unknown>;

type RequestInterceptorHandler = {
  fulfilled: (config: RequestConfigLike) => RequestConfigLike | Promise<RequestConfigLike>;
  rejected: (error: Error) => Promise<never>;
};

type ResponseInterceptorHandler = {
  fulfilled: <T>(value: T) => T;
  rejected: (error: AxiosError) => unknown;
};

function getRequestHandlers(api: { interceptors: { request: { handlers: unknown[] } } }): RequestInterceptorHandler {
  const handlers = (api.interceptors.request as unknown as { handlers: RequestInterceptorHandler[] }).handlers;
  return handlers.at(-1)!;
}

function getResponseHandlers(api: { interceptors: { response: { handlers: unknown[] } } }): ResponseInterceptorHandler {
  const handlers = (api.interceptors.response as unknown as { handlers: ResponseInterceptorHandler[] }).handlers;
  return handlers.at(-1)!;
}

describe('api client interceptors', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
    localStorage.clear();
  });

  it('adds auth and language headers in request interceptor', async () => {
    localStorage.setItem('access_token', 'tok');
    localStorage.setItem('language_preference', 'ro');

    const module = await import('@/services/api');
    const handler = getRequestHandlers(module.api);

    const config: RequestConfigLike = { headers: {} };
    const result = await handler.fulfilled(config);
    const headers = result.headers as Record<string, string>;

    expect(headers.Authorization).toBe('Bearer tok');
    expect(headers['Accept-Language']).toBe('ro');
  }, 15000);

  it('passes through response success and request rejection', async () => {
    const module = await import('@/services/api');
    const reqHandler = getRequestHandlers(module.api);
    const respHandler = getResponseHandlers(module.api);

    const reqError = new Error('req-fail');
    await expect(reqHandler.rejected(reqError)).rejects.toThrow('req-fail');

    const payload = { data: { ok: true } };
    expect(respHandler.fulfilled(payload)).toEqual(payload);
  });

  it('refreshes token on 401 and retries original request', async () => {
    localStorage.setItem('refresh_token', 'refresh-token');

    const module = await import('@/services/api');
    const respHandler = getResponseHandlers(module.api);

    const postSpy = vi.spyOn(axios, 'post').mockResolvedValue({
      data: { access_token: 'new-access', refresh_token: 'new-refresh' },
    });

    const adapterSpy = vi.fn().mockResolvedValue({
      data: { ok: true },
      status: 200,
      statusText: 'OK',
      headers: {},
      config: {},
    });
    module.api.defaults.adapter = adapterSpy as typeof module.api.defaults.adapter;

    const error = {
      config: { headers: {} },
      response: { status: 401 },
    } as unknown as AxiosError;

    const result = await respHandler.rejected(error);

    expect(postSpy).toHaveBeenCalled();
    expect(adapterSpy).toHaveBeenCalled();
    expect(localStorage.getItem('access_token')).toBe('new-access');
    expect(localStorage.getItem('refresh_token')).toBe('new-refresh');
    expect((result as { data: { ok: boolean } }).data).toEqual({ ok: true });
  });

  it('fails closed on refresh failure and clears session', async () => {
    localStorage.setItem('access_token', 'stale-access');
    localStorage.setItem('refresh_token', 'stale-refresh');
    localStorage.setItem('user', '{"id":1}');

    const module = await import('@/services/api');
    const respHandler = getResponseHandlers(module.api);

    vi.spyOn(axios, 'post').mockRejectedValue(new Error('refresh failed'));

    const error = {
      config: { headers: {} },
      response: { status: 401 },
    } as unknown as AxiosError;

    await expect(respHandler.rejected(error)).rejects.toThrow('refresh failed');

    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
    expect(localStorage.getItem('user')).toBeNull();
  });

  it('propagates non-refreshable errors', async () => {
    const module = await import('@/services/api');
    const respHandler = getResponseHandlers(module.api);

    const error = {
      config: { headers: {} },
      response: { status: 500 },
    } as unknown as AxiosError;

    await expect(respHandler.rejected(error)).rejects.toEqual(error);
  });
});
