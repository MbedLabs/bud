const STATUS_CLASSES: Record<string, string> = {
  Pending: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400',
  Running: 'bg-amber-500/10 text-amber-800 dark:text-amber-300',
  Completed: 'bg-amber-500/10 text-amber-800 dark:text-amber-300',
  Failed: 'bg-red-500/10 text-red-700 dark:text-red-400',
  Cancelled: 'bg-muted text-muted-foreground',
}

/** A test run's status as a coloured badge; ``large`` is the size used on the run page. */
export default function RunStatusBadge({ status, large = false }: Readonly<{ status: string; large?: boolean }>) {
  return (
    <span
      className={`${large ? 'px-3 py-1.5 rounded-md text-xs' : 'px-2 py-0.5 rounded-md text-[11px]'} font-semibold ${STATUS_CLASSES[status] || STATUS_CLASSES.Pending}`}
    >
      {status}
    </span>
  )
}
