/**
 * Date and time utilities for the Bud Test Platform.
 */

/**
 * Format an ISO date string to a human-readable format, 
 * respecting the user's preferred timezone setting.
 * 
 * @param dateString ISO date string from the backend (with Z suffix).
 * @param options Intl.DateTimeFormatOptions for customization.
 * @returns Formatted date/time string.
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
    const date = new Date(dateString)
    let preferredTz = localStorage.getItem('bud-timezone') || 'auto'
    
    // Normalize UTC selection to avoid raw ISO fallback in some environments
    if (preferredTz.toLowerCase() === 'utc') {
      preferredTz = 'UTC'
    }

    const finalOptions: Intl.DateTimeFormatOptions = { ...options }
    if (preferredTz !== 'auto') {
      finalOptions.timeZone = preferredTz
    }
    
    return new Intl.DateTimeFormat(undefined, finalOptions).format(date)
  } catch (e) {
    console.error('Error formatting date:', e)
    return dateString
  }
}
