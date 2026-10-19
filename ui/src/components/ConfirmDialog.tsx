import { useEscapeKey } from '../hooks/useEscapeKey'

interface ConfirmDialogProps {
  title: string
  body: string
  confirmLabel: string
  pendingLabel: string
  isPending?: boolean
  error?: string
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmDialog({
  title,
  body,
  confirmLabel,
  pendingLabel,
  isPending = false,
  error = '',
  onConfirm,
  onCancel,
}: Readonly<ConfirmDialogProps>) {
  useEscapeKey(onCancel)

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center z-50">
      <button
        type="button"
        aria-label={`Close ${title} backdrop`}
        tabIndex={-1}
        className="absolute inset-0 h-full w-full cursor-default"
        onClick={onCancel}
      />
      <dialog
        open
        aria-modal="true"
        aria-label={title}
        className="relative m-0 bg-card rounded-lg shadow-elegant p-6 max-w-sm w-full mx-4 text-foreground"
      >
        <h3 className="text-lg font-semibold text-foreground mb-2">{title}</h3>
        <p className="text-sm text-muted-foreground mb-4">{body}</p>
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-sm text-destructive">
            {error}
          </div>
        )}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 border border-input rounded-md text-foreground hover:bg-accent/50 text-sm"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isPending}
            className="px-4 py-2 bg-destructive text-white rounded-md hover:bg-destructive/90 disabled:opacity-50 text-sm"
          >
            {isPending ? pendingLabel : confirmLabel}
          </button>
        </div>
      </dialog>
    </div>
  )
}
