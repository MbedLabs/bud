import { useEffect, useId, useRef, useState, type CSSProperties } from 'react'
import { createPortal } from 'react-dom'
import { ChevronDown } from 'lucide-react'

/** A themed option picker with keyboard navigation and selection. */
export default function Select<V extends string>({ id, label, title, value, onChange, options, disabled = false, required = false, className = '', wrapperClassName = '', autoFocus = false, labelledBy, invalid = false, describedBy }: {
  id?: string
  label?: string
  title?: string
  value: V
  onChange: (value: V) => void
  options: Array<{ value: V; label: string; disabled?: boolean }>
  disabled?: boolean
  required?: boolean
  className?: string
  wrapperClassName?: string
  autoFocus?: boolean
  labelledBy?: string
  invalid?: boolean
  describedBy?: string
}) {
  const listId = useId()
  const button = useRef<HTMLButtonElement>(null)
  const list = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [position, setPosition] = useState<CSSProperties>({ left: 0, top: 0, width: 0, maxHeight: 256 })
  const selectedIndex = Math.max(0, options.findIndex((option) => option.value === value))
  const showMenu = (index: number) => {
    if (disabled || !options.some((option) => !option.disabled)) return
    const rect = button.current?.getBoundingClientRect()
    if (!rect) return
    const width = Math.min(Math.max(rect.width, 192), window.innerWidth - 16)
    const below = window.innerHeight - rect.bottom - 12
    const above = rect.top - 12
    const upwards = below < 160 && above > below
    const maxHeight = Math.max(40, Math.min(256, upwards ? above : below))
    setPosition({ left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)), top: upwards ? undefined : rect.bottom + 4, bottom: upwards ? window.innerHeight - rect.top + 4 : undefined, width, maxHeight })
    setActive(index)
    setOpen(true)
  }
  useEffect(() => {
    if (!open) return
    list.current?.children[active]?.scrollIntoView?.({ block: 'nearest' })
  }, [open, active])
  useEffect(() => {
    if (!open) return
    const closeOutside = (event: MouseEvent) => {
      if (!button.current?.contains(event.target as Node) && !list.current?.contains(event.target as Node)) setOpen(false)
    }
    const closeOnScroll = (event: Event) => {
      if (!list.current?.contains(event.target as Node)) setOpen(false)
    }
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
  const choose = (index: number) => {
    if (!options[index] || options[index].disabled || disabled) return
    onChange(options[index].value)
    setOpen(false)
    button.current?.focus()
  }
  const nextEnabled = (start: number, direction: number) => {
    for (let step = 1; step <= options.length; step++) {
      const index = (start + step * direction + options.length) % options.length
      if (!options[index].disabled) return index
    }
    return start
  }
  return <div className={`min-w-0 ${wrapperClassName}`}>
    <button ref={button} id={id} value={value} type="button" role="combobox" aria-label={label} aria-labelledby={labelledBy} title={title ?? label}
      aria-expanded={open} aria-haspopup="listbox" aria-controls={open ? `${listId}-list` : undefined}
      aria-required={required || undefined} aria-invalid={invalid || undefined} aria-describedby={describedBy} disabled={disabled} autoFocus={autoFocus}
      aria-activedescendant={open ? `${listId}-${active}` : undefined}
      className={`flex w-full items-center justify-between gap-2 text-left focus:ring-2 focus:ring-ring focus:border-ring disabled:cursor-not-allowed disabled:opacity-50 ${className || 'rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground'}`}
      onBlur={(event) => { if (!list.current?.contains(event.relatedTarget as Node | null)) setOpen(false) }}
      onClick={() => { if (open) setOpen(false); else showMenu(options[selectedIndex]?.disabled ? nextEnabled(selectedIndex, 1) : selectedIndex) }}
      onKeyDown={(event) => {
        if (event.key === 'Escape') { event.preventDefault(); setOpen(false) }
        else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault()
          showMenu(nextEnabled(open ? active : selectedIndex, event.key === 'ArrowDown' ? 1 : -1))
        } else if (event.key === 'Home' || event.key === 'End') {
          event.preventDefault(); showMenu(nextEnabled(event.key === 'Home' ? options.length - 1 : 0, event.key === 'Home' ? 1 : -1))
        } else if ((event.key === 'Enter' || event.key === ' ') && open) {
          event.preventDefault(); choose(active)
        } else if (event.key.length === 1 && event.key !== ' ') {
          const index = options.findIndex((option) => !option.disabled && option.label.toLowerCase().startsWith(event.key.toLowerCase()))
          if (index >= 0) { event.preventDefault(); showMenu(index) }
        }
      }}>
      <span className="min-w-0 whitespace-normal break-words">{options[selectedIndex]?.label}</span>
      <ChevronDown className="h-4 w-4 shrink-0" />
    </button>
    {open && createPortal(<div ref={list} id={`${listId}-list`} role="listbox" aria-label={label} aria-labelledby={labelledBy} style={position} className="themed-scrollbar fixed z-[100] overflow-y-auto rounded-md border border-border bg-card p-1 text-foreground shadow-elegant">
      {options.map((option, index) => <button type="button" role="option" id={`${listId}-${index}`} key={`${option.value}-${index}`} data-value={option.value}
        aria-selected={option.value === value} aria-disabled={option.disabled || undefined} disabled={option.disabled} tabIndex={-1}
        className={`block w-full whitespace-normal break-words rounded px-2 py-1.5 text-left text-sm disabled:opacity-50 ${index === active ? 'bg-primary/10 text-primary' : 'hover:bg-accent'}`}
        onMouseDown={(event) => event.preventDefault()} onMouseEnter={() => { if (!option.disabled) setActive(index) }} onClick={() => choose(index)}>{option.label}</button>)}
    </div>, document.body)}
  </div>
}
