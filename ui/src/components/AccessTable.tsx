import type { ReactNode } from 'react'
import { ArrowUpDown, ChevronDown, ChevronUp, X } from 'lucide-react'

/** A sortable table column with its current direction. */
export function AccessHeader<F extends string>({ field, sortField, sortDir, onSort, children }: {
  field: F
  sortField: F
  sortDir: 'asc' | 'desc'
  onSort: (field: F) => void
  children: ReactNode
}) {
  return <th aria-sort={sortField === field ? sortDir === 'asc' ? 'ascending' : 'descending' : 'none'} className="text-left font-medium px-4 py-2">
    <button type="button" onClick={() => onSort(field)} className="flex items-center gap-1 hover:text-foreground transition-colors">
      {children}
      {sortField === field ? sortDir === 'asc' ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" /> : <ArrowUpDown className="h-3 w-3 opacity-30" />}
    </button>
  </th>
}

/** The Access viewer and editor dialog. */
export function AccessModal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
    <div role="dialog" aria-modal="true" aria-label={title} className="bg-card border border-border rounded-xl shadow-elegant p-6 w-full max-w-3xl max-h-[90vh] overflow-y-auto mx-4" onClick={(event) => event.stopPropagation()}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        <button type="button" onClick={onClose} aria-label="Close" className="p-1 rounded text-muted-foreground hover:text-foreground"><X className="h-4 w-4" /></button>
      </div>
      {children}
    </div>
  </div>
}
