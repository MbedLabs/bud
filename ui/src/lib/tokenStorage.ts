const TOKEN_KEY = 'bud_token'

function getSessionStorage(): Storage | null {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

export function getAuthToken(): string | null {
  return getSessionStorage()?.getItem(TOKEN_KEY) ?? null
}

export function setAuthToken(token: string): void {
  getSessionStorage()?.setItem(TOKEN_KEY, token)
}

export function clearAuthToken(): void {
  getSessionStorage()?.removeItem(TOKEN_KEY)
}
