import axios from 'axios'

/** Whether a failed request means this user may not see the resource (403 or 404). */
export function isAccessDenied(error: unknown): boolean {
  if (!axios.isAxiosError(error)) return false
  const status = error.response?.status
  return status === 403 || status === 404
}
