import { apiRequest } from '@edu/api-client'

export interface LoginInput {
  email: string
  password: string
}

export function login(input: LoginInput): Promise<unknown> {
  return apiRequest('/api/v2/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

