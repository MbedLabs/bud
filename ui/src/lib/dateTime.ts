/**
 * Date and time utilities for the Bud TMP.
 */

const DEFAULT_DATE_TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
}

/**
 * Format an ISO date string for display, 
 * respecting the user's preferred timezone setting.
 */
export function formatDateTime(
  dateString: string | null | undefined, 
  options: Intl.DateTimeFormatOptions = DEFAULT_DATE_TIME_OPTIONS
): string {
  if (!dateString) return '-'
  
  try {
    const date = new Date(dateString)
    if (Number.isNaN(date.getTime())) return dateString

    const preferredTz = localStorage.getItem('bud-timezone') || 'auto'
    
    const finalOptions: Intl.DateTimeFormatOptions = { ...options }
    
    if (preferredTz !== 'auto') {
      finalOptions.timeZone = preferredTz
    }
    
    return new Intl.DateTimeFormat(undefined, finalOptions).format(date)
  } catch (e) {
    console.error('Error formatting date:', e)
    try {
        return new Date(dateString).toLocaleString()
    } catch {
        return dateString
    }
  }
}
