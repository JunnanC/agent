import type { paths } from './generated/schema'

export type HealthResponse =
  paths['/api/v2/health']['get']['responses'][200]['content']['application/json']

export interface ApiFailure {
  error: {
    code: string
    message: string
    detail: unknown
    trace_id: string
    retryable: boolean
  }
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly payload: ApiFailure,
  ) {
    super(payload.error.message)
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: { Accept: 'application/json', ...init?.headers },
  })
  const payload = (await response.json()) as T | ApiFailure
  if (!response.ok) {
    throw new ApiError(response.status, payload as ApiFailure)
  }
  return payload as T
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/api/v2/health', { signal })
}
