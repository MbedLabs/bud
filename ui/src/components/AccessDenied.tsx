import { ShieldAlert } from 'lucide-react'

interface AccessDeniedProps {
  what: string
}

/**
 * The page shown to a user who is not an Admin when the server refuses a resource (403). It
 * names the resource as the page does and offers no request.
 */
export default function AccessDenied({ what }: Readonly<AccessDeniedProps>) {
  return (
    <div className="max-w-lg mx-auto mt-16 bg-card border border-border rounded-xl p-8 text-center">
      <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-destructive/10 flex items-center justify-center">
        <ShieldAlert className="h-6 w-6 text-destructive" />
      </div>
      <h2 className="text-lg font-semibold text-foreground">You don&apos;t have access to {what}</h2>
      <p className="text-sm text-muted-foreground mt-2">An administrator can tell you which group gives it.</p>
    </div>
  )
}
