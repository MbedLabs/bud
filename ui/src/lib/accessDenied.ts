import axios from 'axios'

/** Whether a failed request was refused to this user (403). */
export function isAccessDenied(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 403
}

/** Whether a failed request names something that does not exist (404). */
export function isNotFound(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 404
}
