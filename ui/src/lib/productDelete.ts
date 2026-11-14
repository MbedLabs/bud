/** The phrase a user types to confirm deleting the named product. */
export function productDeleteConfirmationPhrase(name: string): string {
  return `Delete ${name.trim()}`
}

/** Whether the typed text is the expected confirmation phrase. */
export function productDeleteConfirmationMatches(input: string, expected: string): boolean {
  return input.trim() === expected.trim()
}
