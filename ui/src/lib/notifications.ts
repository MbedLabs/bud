import type { NotificationFormat, NotificationRunFilter } from '../api/client'

/** The channel formats, as the Settings form and the product rules name them. */
export const FORMAT_OPTIONS: { value: NotificationFormat; label: string }[] = [
  { value: 'teams', label: 'Microsoft Teams' },
  { value: 'slack', label: 'Slack' },
  { value: 'discord', label: 'Discord' },
  { value: 'json', label: 'JSON' },
]

/** The run filters of a channel or a product rule. */
export const FILTER_OPTIONS: { value: NotificationRunFilter; label: string }[] = [
  { value: 'all', label: 'All finished runs' },
  { value: 'failures', label: 'Failures only' },
  { value: 'first_failure', label: 'First failure after a green run' },
]

/** The display name of a channel format. */
export function formatLabel(format: NotificationFormat): string {
  return FORMAT_OPTIONS.find((option) => option.value === format)?.label ?? format
}

/** The display name of a run filter. */
export function filterLabel(filter: NotificationRunFilter): string {
  return FILTER_OPTIONS.find((option) => option.value === filter)?.label ?? filter
}
