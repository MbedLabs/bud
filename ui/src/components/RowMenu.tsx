import { useEffect, useRef, useState } from 'react'
import { MoreVertical } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export interface RowMenuAction {
  label: string
  icon: LucideIcon
  onSelect: () => void
  destructive?: boolean
}

export default function RowMenu({ label, actions }: { label: string; actions: RowMenuAction[] }) {
  const [open, setOpen] = useState(false)
  const [dropUp, setDropUp] = useState(false)
  const container = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: MouseEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false)
    }
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  return (
    <div ref={container} className="relative shrink-0">
      <button
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={(event) => {
          event.preventDefault()
          event.stopPropagation()
          const below = window.innerHeight - event.currentTarget.getBoundingClientRect().bottom
          setDropUp(below < actions.length * 40 + 16)
          setOpen((current) => !current)
        }}
        className="p-2 -mr-2 -mt-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors"
      >
        <MoreVertical className="h-4 w-4" />
      </button>

      {open && (
        <div
          role="menu"
          className={`absolute right-0 z-20 w-44 overflow-hidden rounded-lg border border-border bg-card shadow-elegant ${
            dropUp ? 'bottom-full mb-1' : 'top-full mt-1'
          }`}
        >
          {actions.map((action) => (
            <button
              key={action.label}
              type="button"
              role="menuitem"
              onClick={(event) => {
                event.preventDefault()
                event.stopPropagation()
                setOpen(false)
                action.onSelect()
              }}
              className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-accent/50 ${
                action.destructive ? 'text-destructive' : 'text-foreground'
              }`}
            >
              <action.icon className="h-4 w-4 shrink-0" />
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
