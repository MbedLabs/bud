/**
 * Date and time utilities for the Bud Test Platform.
 */

/**
 * Format an ISO date string to a human-readable format, 
 * respecting the user's preferred timezone setting.
 */
export function formatDateTime(
  dateString: string | null | undefined, 
  options: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }
): string {
  if (!dateString) return '-'
  
  try {
    // Ensure the date is parsed correctly
    const date = new Date(dateString)
    if (isNaN(date.getTime())) return dateString

    const preferredTz = localStorage.getItem('bud-timezone') || 'auto'
    
    const finalOptions: Intl.DateTimeFormatOptions = { ...options }
    
    // If not auto, apply the specific timezone (e.g., 'UTC', 'Europe/Berlin')
    if (preferredTz !== 'auto') {
      finalOptions.timeZone = preferredTz
    }
    
    // Always use a specific locale or undefined for browser default
    // to ensure we get a human-readable string like "19. Apr. 2026"
    return new Intl.DateTimeFormat(undefined, finalOptions).format(date)
  } catch (e) {
    console.error('Error formatting date:', e)
    // Even if it fails, try a basic locale string instead of raw ISO
    try {
        return new Date(dateString).toLocaleString()
    } catch {
        return dateString
    }
  }
}
