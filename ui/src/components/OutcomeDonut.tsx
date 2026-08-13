import type { LucideIcon } from 'lucide-react'

export interface OutcomeSegment {
  label: string
  value: number
  /** Tailwind text colour; the arc is drawn with `currentColor`. */
  tone: string
  icon: LucideIcon
}

/**
 * Part-to-whole for an outcome split, as a donut with the total in the hole.
 *
 * Pass and fail are the two colours a reader must never confuse, and measured
 * against each other they are the worst pair in the palette: Bud's emerald and
 * red sit at CVD ΔE 2.1 under deuteranopia, which is roughly one in twelve men.
 * So identity here is never carried by colour: every segment is named in the
 * legend beside its own icon and count, and the arcs are separated by a gap in
 * the surface colour rather than meeting edge to edge.
 *
 * Segments are ordered as given and never re-coloured when one drops to zero -
 * a filter that empties "skipped" must not repaint "failed".
 */
export default function OutcomeDonut({
  title,
  caption,
  segments,
  totalLabel,
}: {
  title: string
  caption?: string
  segments: OutcomeSegment[]
  totalLabel: string
}) {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0)
  // 42 is the radius that makes the circumference a round-ish 264; any radius
  // works, but a fixed one keeps the gap arithmetic below readable.
  const radius = 42
  const circumference = 2 * Math.PI * radius
  const GAP = 3

  // Only non-empty segments get an arc: a zero-length arc still draws its two
  // gap ends, which reads as a stray tick on the ring.
  const drawn = segments.filter((segment) => segment.value > 0)
  let offset = 0

  return (
    <div className="bg-card rounded-lg border border-border shadow-elegant p-5">
      <div className="mb-4">
        <h3 className="text-sm font-medium text-foreground">{title}</h3>
        {caption && <p className="text-xs text-muted-foreground mt-0.5">{caption}</p>}
      </div>

      <div className="flex items-center gap-6">
        <div className="relative shrink-0">
          <svg viewBox="0 0 100 100" className="h-32 w-32 -rotate-90" role="img" aria-label={title}>
            <circle
              cx="50"
              cy="50"
              r={radius}
              fill="none"
              className="text-muted"
              stroke="currentColor"
              strokeWidth="10"
            />
            {drawn.map((segment) => {
              const share = segment.value / total
              const length = Math.max(share * circumference - GAP, 0.5)
              const dash = `${length} ${circumference - length}`
              const thisOffset = offset
              offset += share * circumference
              return (
                <circle
                  key={segment.label}
                  cx="50"
                  cy="50"
                  r={radius}
                  fill="none"
                  className={segment.tone}
                  stroke="currentColor"
                  strokeWidth="10"
                  strokeDasharray={dash}
                  strokeDashoffset={-thisOffset}
                  strokeLinecap="butt"
                >
                  <title>{`${segment.label}: ${segment.value} (${percent(segment.value, total)})`}</title>
                </circle>
              )
            })}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-bold text-foreground">{total}</span>
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
              {totalLabel}
            </span>
          </div>
        </div>

        <ul className="min-w-0 flex-1 space-y-2">
          {segments.map((segment) => {
            const Icon = segment.icon
            return (
              <li key={segment.label} className="flex items-center gap-2 text-sm">
                <Icon className={`h-3.5 w-3.5 shrink-0 ${segment.tone}`} aria-hidden="true" />
                <span className="text-muted-foreground truncate">{segment.label}</span>
                <span className="ml-auto shrink-0 font-medium text-foreground tabular-nums">
                  {segment.value}
                </span>
                <span className="w-12 shrink-0 text-right text-xs text-muted-foreground tabular-nums">
                  {percent(segment.value, total)}
                </span>
              </li>
            )
          })}
        </ul>
      </div>
    </div>
  )
}

/** A share of the total, or a dash when there is no total to take a share of. */
function percent(value: number, total: number): string {
  if (total <= 0) return '—'
  return `${Math.round((value / total) * 100)}%`
}
