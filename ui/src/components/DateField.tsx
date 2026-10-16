import { useEffect, useId, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react'
import { createPortal } from 'react-dom'
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react'

/** A local calendar date from its ISO date string. */
function dateFromValue(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null
  const [year, month, day] = value.split('-').map(Number)
  if (year < 1 || year > 9999) return null
  const date = new Date(0)
  date.setFullYear(year, month - 1, day)
  date.setHours(12, 0, 0, 0)
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day ? date : null
}

/** A calendar date's ISO value without a timezone conversion. */
function dateValue(date: Date): string {
  return `${String(date.getFullYear()).padStart(4, '0')}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

/** The same day in another month, limited to that month's last day. */
function moveMonth(date: Date, change: number): Date {
  const next = new Date(date)
  next.setDate(1)
  next.setMonth(next.getMonth() + change)
  const last = new Date(next)
  last.setMonth(last.getMonth() + 1, 0)
  next.setDate(Math.min(date.getDate(), last.getDate()))
  return next
}

/** An editable date filter with an app-themed calendar popup. */
export default function DateField({ label, value, onChange, className = '', placeholder, min, max, disabled = false }: Readonly<{
  label: string
  value: string
  onChange: (value: string) => void
  className?: string
  placeholder?: string
  min?: string
  max?: string
  disabled?: boolean
}>) {
  const id = useId()
  const field = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLInputElement>(null)
  const popup = useRef<HTMLDialogElement>(null)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(value || dateValue(new Date()))
  const [month, setMonth] = useState(() => dateFromValue(value) ?? new Date())
  const [draft, setDraft] = useState<{ source: string; text: string } | null>(null)
  const [error, setError] = useState('')
  const [position, setPosition] = useState<CSSProperties>({ left: 0, top: 0, width: 280 })
  const locale = navigator.language
  const display = new Intl.DateTimeFormat(locale, { year: 'numeric', month: '2-digit', day: '2-digit', calendar: 'gregory', numberingSystem: 'latn' })
  const fullDate = new Intl.DateTimeFormat(locale, { dateStyle: 'full', calendar: 'gregory' })
  const localeInfo = new Intl.Locale(locale) as Intl.Locale & { weekInfo?: { firstDay: number }; getWeekInfo?: () => { firstDay: number } }
  const firstDay = (localeInfo.getWeekInfo?.().firstDay ?? localeInfo.weekInfo?.firstDay ?? 1) % 7
  const parts = display.formatToParts(new Date(2026, 9, 14))
  const order = parts.filter(part => ['year', 'month', 'day'].includes(part.type)).map(part => part.type)
  const empty = placeholder ?? parts.map(part => part.type === 'day' ? 'DD' : part.type === 'month' ? 'MM' : part.type === 'year' ? 'YYYY' : part.value).join('')
  const selected = dateFromValue(value)
  const text = draft?.source === value ? draft.text : selected ? display.format(selected) : ''
  const allowed = (day: string) => !!dateFromValue(day) && (!min || day >= min) && (!max || day <= max)
  const commit = (next: string) => {
    setError('')
    setDraft(null)
    onChange(next)
    setOpen(false)
    input.current?.focus()
  }
  const parse = (next: string) => {
    if (dateFromValue(next)) return next
    const values = next.match(/^(\d{1,4})\D+(\d{1,4})\D+(\d{1,4})$/)?.slice(1)
    if (!values) return null
    const mapped = Object.fromEntries(order.map((part, index) => [part, values[index]]))
    const day = `${mapped.year?.padStart(4, '0')}-${mapped.month?.padStart(2, '0')}-${mapped.day?.padStart(2, '0')}`
    return dateFromValue(day) ? day : null
  }
  const show = () => {
    if (disabled) return
    const rect = field.current?.getBoundingClientRect()
    if (!rect) return
    const width = Math.min(280, window.innerWidth - 16)
    const below = window.innerHeight - rect.bottom - 12
    const above = rect.top - 12
    const upwards = below < 330 && above > below
    setPosition({ left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)), top: upwards ? undefined : rect.bottom + 4, bottom: upwards ? window.innerHeight - rect.top + 4 : undefined, width, maxHeight: Math.max(80, upwards ? above : below) })
    const today = dateValue(new Date())
    const next = selected ? value : min && today < min ? min : max && today > max ? max : today
    setActive(next)
    setMonth(dateFromValue(next) ?? new Date())
    setOpen(true)
  }
  useEffect(() => {
    if (open) popup.current?.querySelector<HTMLButtonElement>(`[data-date="${active}"]`)?.focus()
  }, [open, active, month])
  useEffect(() => {
    if (!open) return
    const closeOutside = (event: MouseEvent) => {
      if (!field.current?.contains(event.target as Node) && !popup.current?.contains(event.target as Node)) setOpen(false)
    }
    const closeOnScroll = (event: Event) => { if (!popup.current?.contains(event.target as Node)) setOpen(false) }
    const closeOnResize = () => setOpen(false)
    document.addEventListener('mousedown', closeOutside)
    document.addEventListener('scroll', closeOnScroll, true)
    window.addEventListener('resize', closeOnResize)
    return () => {
      document.removeEventListener('mousedown', closeOutside)
      document.removeEventListener('scroll', closeOnScroll, true)
      window.removeEventListener('resize', closeOnResize)
    }
  }, [open])
  const navigate = (next: Date) => {
    const day = dateValue(next)
    if (!allowed(day)) return
    setActive(day)
    setMonth(next)
  }
  const navigateMonth = (change: number) => {
    let next = moveMonth(month, change)
    const iso = dateValue(next)
    if (min && iso < min) next = dateFromValue(min) ?? next
    if (max && iso > max) next = dateFromValue(max) ?? next
    navigate(next)
  }
  const dayKeys = (event: KeyboardEvent<HTMLButtonElement>, day: Date) => {
    const next = new Date(day)
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') next.setDate(next.getDate() + (event.key === 'ArrowLeft' ? -1 : 1))
    else if (event.key === 'ArrowUp' || event.key === 'ArrowDown') next.setDate(next.getDate() + (event.key === 'ArrowUp' ? -7 : 7))
    else if (event.key === 'Home' || event.key === 'End') next.setDate(next.getDate() - (next.getDay() - firstDay + 7) % 7 + (event.key === 'End' ? 6 : 0))
    else if (event.key === 'PageUp' || event.key === 'PageDown') { event.preventDefault(); navigateMonth((event.key === 'PageUp' ? -1 : 1) * (event.shiftKey ? 12 : 1)); return }
    else return
    event.preventDefault()
    navigate(next)
  }
  const start = new Date(month)
  start.setDate(1)
  start.setDate(1 - (start.getDay() - firstDay + 7) % 7)
  const days = Array.from({ length: 42 }, (_, index) => {
    const day = new Date(start)
    day.setDate(start.getDate() + index)
    return day
  })
  const previous = moveMonth(month, -1)
  const previousEnd = new Date(previous)
  previousEnd.setMonth(previousEnd.getMonth() + 1, 0)
  const nextStart = moveMonth(month, 1)
  nextStart.setDate(1)
  return <div ref={field} className={`relative min-w-0 ${className.includes('w-full') ? 'w-full' : 'w-40'}`} onBlur={event => {
    if (!field.current?.contains(event.relatedTarget as Node | null) && !popup.current?.contains(event.relatedTarget as Node | null)) setOpen(false)
  }}>
    <div className={`flex items-center gap-2 focus-within:ring-2 focus-within:ring-ring focus-within:border-ring ${className.replace(/\bblock\b/g, '') || 'rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground'}`}>
      <input ref={input} type="text" role="combobox" aria-label={label} aria-invalid={!!error || undefined} aria-describedby={error ? `${id}-error` : undefined} aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? `${id}-calendar` : undefined}
        inputMode="numeric" autoComplete="off" disabled={disabled} value={text} placeholder={empty} className="min-w-0 w-full bg-transparent text-foreground placeholder:text-muted-foreground outline-none disabled:opacity-50"
        onChange={event => {
          const next = event.target.value
          setDraft({ source: value, text: next })
          setError('')
          const parsed = parse(next)
          if (!next || parsed && allowed(parsed)) onChange(parsed ?? '')
        }}
        onBlur={() => { if (text && (!parse(text) || !allowed(parse(text)!))) setError('Enter a valid date within the allowed range.') }}
        onKeyDown={event => { if (event.key === 'ArrowDown') { event.preventDefault(); show() } else if (event.key === 'Escape') setOpen(false) }} />
      <button type="button" aria-label={`Choose date for ${label}`} disabled={disabled} aria-haspopup="dialog" aria-expanded={open} onClick={() => { if (open) setOpen(false); else show() }} className="shrink-0 rounded text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"><Calendar className="h-4 w-4" /></button>
    </div>
    {error && <p id={`${id}-error`} role="alert" className="mt-1 text-xs text-destructive">{error}</p>}
    {open && createPortal(<dialog open ref={popup} id={`${id}-calendar`} aria-label={`${label} calendar`} style={position} className="themed-scrollbar fixed z-[100] m-0 overflow-y-auto rounded-md border border-border bg-card p-3 text-foreground shadow-elegant"
      onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); setOpen(false); input.current?.focus() } }}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <button type="button" aria-label="Previous month" disabled={!!min && dateValue(previousEnd) < min} onClick={() => navigateMonth(-1)} className="rounded p-1 hover:bg-accent disabled:opacity-30"><ChevronLeft className="h-4 w-4" /></button>
        <span id={`${id}-month`} aria-live="polite" className="text-sm font-medium">{new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric', calendar: 'gregory' }).format(month)}</span>
        <button type="button" aria-label="Next month" disabled={!!max && dateValue(nextStart) > max} onClick={() => navigateMonth(1)} className="rounded p-1 hover:bg-accent disabled:opacity-30"><ChevronRight className="h-4 w-4" /></button>
      </div>
      <table role="grid" aria-labelledby={`${id}-month`} className="w-full table-fixed text-center text-sm">
        <thead><tr>{days.slice(0, 7).map(day => <th key={day.getDay()} scope="col" className="h-7 text-xs font-normal text-muted-foreground">{new Intl.DateTimeFormat(locale, { weekday: 'short' }).format(day)}</th>)}</tr></thead>
        <tbody>{Array.from({ length: 6 }, (_, week) => <tr key={week}>{days.slice(week * 7, week * 7 + 7).map(day => {
          const iso = dateValue(day)
          return <td key={iso}><button type="button" data-date={iso} aria-label={fullDate.format(day)} aria-pressed={iso === value} aria-current={iso === dateValue(new Date()) ? 'date' : undefined} tabIndex={iso === active ? 0 : -1} disabled={!allowed(iso)}
            onKeyDown={event => dayKeys(event, day)} onClick={() => commit(iso)} className={`h-8 w-full rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-30 ${iso === value ? 'bg-primary text-primary-foreground' : day.getMonth() !== month.getMonth() ? 'text-muted-foreground hover:bg-accent' : 'hover:bg-accent'}`}>{day.getDate()}</button></td>
        })}</tr>)}</tbody>
      </table>
      <div className="mt-2 flex justify-between border-t border-border pt-2 text-xs">
        <button type="button" onClick={() => commit('')} className="rounded px-2 py-1 hover:bg-accent">Clear</button>
        <button type="button" disabled={!allowed(dateValue(new Date()))} onClick={() => commit(dateValue(new Date()))} className="rounded px-2 py-1 text-primary hover:bg-accent disabled:opacity-30">Today</button>
      </div>
    </dialog>, document.body)}
  </div>
}
