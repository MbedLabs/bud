/** Return a password validation message, or null for a valid password and confirmation. */
export function newPasswordProblem(password: string, confirmation: string): string | null {
  if (password.length < 12) return 'Password must be at least 12 characters long'
  if (password !== confirmation) return 'Passwords do not match'
  return null
}
