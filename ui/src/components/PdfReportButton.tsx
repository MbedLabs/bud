import { useState } from 'react'
import { FileDown } from 'lucide-react'
import { extractApiErrorMessage, saveBlob } from '../api/client'

interface PdfReportButtonProps {
  fetchReport: () => Promise<{ blob: Blob; filename: string }>
  title: string
  onError: (message: string | null) => void
}

/** A button that downloads a PDF report and hands a failure to the page. */
export default function PdfReportButton({ fetchReport, title, onError }: PdfReportButtonProps) {
  const [pending, setPending] = useState(false)
  return (
    <button
      type="button"
      onClick={async () => {
        onError(null)
        setPending(true)
        try {
          const { blob, filename } = await fetchReport()
          saveBlob(blob, filename)
        } catch (error) {
          onError(extractApiErrorMessage(error, 'Could not generate the report'))
        } finally {
          setPending(false)
        }
      }}
      disabled={pending}
      title={title}
      className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background px-2.5 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
    >
      <FileDown className="h-4 w-4" />
      {pending ? 'Preparing…' : 'PDF report'}
    </button>
  )
}
