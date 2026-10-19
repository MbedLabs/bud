import type { ReactNode } from 'react'
import { APP_VERSION } from '../api/client'
import { BUD_LOGO_DARK, BUD_LOGO_LIGHT } from '../brandAssets'

/** The card with the logo and the version footer that frames the account pages. */
export default function AuthPageShell({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-auth p-4">
      <div className="w-full max-w-md bg-card rounded-2xl shadow-2xl p-8 border border-border">
        <div className="flex flex-col items-center mb-6">
          <img
            src={BUD_LOGO_DARK}
            alt="Bud TMP by EmbedLabs"
            className="h-16 w-auto max-w-full object-contain mb-3 hidden dark:block"
          />
          <img
            src={BUD_LOGO_LIGHT}
            alt="Bud TMP by EmbedLabs"
            className="h-16 w-auto max-w-full object-contain mb-3 dark:hidden"
          />
        </div>
        {children}
        <div className="text-center mt-6">
          <p className="text-sm text-lime-100/70">Bud TMP</p>
          <p className="text-xs text-lime-200/50 mt-1">v{APP_VERSION}</p>
          <a
            href="https://www.embedlabs.net"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-lime-200/60 mt-1 inline-block hover:text-lime-100 transition-colors"
          >
            Powered by EmbedLabs
          </a>
        </div>
      </div>
    </div>
  )
}
