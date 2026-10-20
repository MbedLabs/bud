import type { ReactNode } from 'react'
import { ArrowUpDown, ChevronDown, ChevronUp, X } from 'lucide-react'

/** The aria-sort value of a column: its direction when it is the sort column, otherwise none. */
function ariaSort(active: boolean, sortDir: 'asc' | 'desc'): 'ascending' | 'descending' | 'none' {
  if (!active) return 'none'
  return sortDir === 'asc' ? 'ascending' : 'descending'
}

/** The sort indicator of a column: its direction when it is the sort column, otherwise a neutral icon. */
function sortIcon(active: boolean, sortDir: 'asc' | 'desc'): ReactNode {
  if (!active) return <ArrowUpDown className="h-3 w-3 opacity-30" />
  return sortDir === 'asc' ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />
}

/** A sortable table column with its current direction. */
export function AccessHeader<F extends string>({ field, sortField, sortDir, onSort, children, className = 'text-left font-medium px-4 py-2' }: Readonly<{
  field: F
  sortField: F | null
  sortDir: 'asc' | 'desc'
  onSort: (field: F) => void
  children: ReactNode
  className?: string
}>) {
  return <th aria-sort={ariaSort(sortField === field, sortDir)} className={className} onClick={() => onSort(field)}>
    <button type="button" className="flex items-center gap-1 hover:text-foreground transition-colors">
      {children}
      {sortIcon(sortField === field, sortDir)}
    </button>
  </th>
}

/** The Access viewer and editor dialog. */
export function AccessModal({ title, onClose, children }: Readonly<{ title: string; onClose: () => void; children: ReactNode }>) {
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
    <button type="button" aria-label={`Close ${title} backdrop`} tabIndex={-1} className="absolute inset-0 h-full w-full cursor-default" onClick={onClose} />
    <dialog open aria-modal="true" aria-label={title} className="relative m-0 bg-card border border-border rounded-xl shadow-elegant p-6 w-full max-w-3xl max-h-[90vh] overflow-y-auto mx-4 text-foreground" onKeyDown={(event) => { if (event.key === 'Escape') onClose() }}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        <button type="button" onClick={onClose} aria-label="Close" className="p-1 rounded text-muted-foreground hover:text-foreground"><X className="h-4 w-4" /></button>
      </div>
      {children}
    </dialog>
  </div>
}
