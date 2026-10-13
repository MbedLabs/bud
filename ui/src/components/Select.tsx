import { useEffect, useId, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'

/** A themed option picker with keyboard navigation and selection. */
export default function Select<V extends string>({ id, label, value, onChange, options }: {
  id?: string
  label: string
  value: V
  onChange: (value: V) => void
  options: Array<{ value: V; label: string }>
}) {
  const listId = useId()
  const button = useRef<HTMLButtonElement>(null)
  const list = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const selectedIndex = Math.max(0, options.findIndex((option) => option.value === value))
  useEffect(() => {
    if (open) list.current?.children[active]?.scrollIntoView?.({ block: 'nearest' })
  }, [open, active])
  const choose = (index: number) => {
    if (!options[index]) return
    onChange(options[index].value)
    setOpen(false)
    button.current?.focus()
  }
  return <div className="relative" onBlur={(event) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false)
  }}>
    <button ref={button} id={id} type="button" role="combobox" aria-label={label}
      aria-expanded={open} aria-haspopup="listbox" aria-controls={`${listId}-list`}
      aria-activedescendant={open ? `${listId}-${active}` : undefined}
      className="flex w-full items-center justify-between gap-2 rounded-md border border-input bg-background px-3 py-2 text-left text-sm text-foreground focus:ring-2 focus:ring-ring focus:border-ring"
      onClick={() => { setActive(selectedIndex); setOpen(!open) }}
      onKeyDown={(event) => {
        if (event.key === 'Escape') { event.preventDefault(); setOpen(false) }
        else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault()
          const index = open ? active : selectedIndex
          setActive((index + (event.key === 'ArrowDown' ? 1 : options.length - 1)) % options.length)
          setOpen(true)
        } else if (event.key === 'Home' || event.key === 'End') {
          event.preventDefault(); setActive(event.key === 'Home' ? 0 : options.length - 1); setOpen(true)
        } else if ((event.key === 'Enter' || event.key === ' ') && open) {
          event.preventDefault(); choose(active)
        } else if (event.key.length === 1 && event.key !== ' ') {
          const index = options.findIndex((option) => option.label.toLowerCase().startsWith(event.key.toLowerCase()))
          if (index >= 0) { event.preventDefault(); setActive(index); setOpen(true) }
        }
      }}>
      <span>{options[selectedIndex]?.label}</span>
      <ChevronDown className="h-4 w-4 shrink-0" />
    </button>
    {open && <div ref={list} id={`${listId}-list`} role="listbox" aria-label={label} className="absolute z-50 mt-1 max-h-64 w-full overflow-auto rounded-md border border-border bg-card p-1 shadow-elegant">
      {options.map((option, index) => <button type="button" role="option" id={`${listId}-${index}`} key={option.value}
        aria-selected={option.value === value} tabIndex={-1}
        className={`block w-full rounded px-2 py-1.5 text-left text-sm ${index === active ? 'bg-primary/10 text-primary' : 'hover:bg-accent'}`}
        onMouseEnter={() => setActive(index)} onClick={() => choose(index)}>{option.label}</button>)}
    </div>}
  </div>
}
