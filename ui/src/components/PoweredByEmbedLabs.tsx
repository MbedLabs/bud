interface PoweredByEmbedLabsProps {
  collapsed: boolean
  version: string
}

export default function PoweredByEmbedLabs({
  collapsed,
  version,
}: PoweredByEmbedLabsProps) {
  if (collapsed) {
    return (
      <a
        data-testid="sidebar-attribution"
        data-state="collapsed"
        href="https://www.embedlabs.net"
        target="_blank"
        rel="noopener noreferrer"
        className="fixed bottom-3 left-[4.25rem] z-20 whitespace-nowrap text-xs font-medium text-gray-500 transition-colors hover:text-gray-700 dark:text-white dark:hover:text-gray-200"
      >
        Powered by EmbedLabs © 2026
      </a>
    )
  }

  return (
    <div
      data-testid="sidebar-attribution"
      data-state="expanded"
      className="mt-2 w-full max-w-full shrink-0 overflow-hidden border-t border-white/10 px-1 pt-2 text-center"
    >
      <a
        href="https://www.embedlabs.net"
        target="_blank"
        rel="noopener noreferrer"
        className="block w-full max-w-full overflow-hidden whitespace-nowrap text-[10px] text-lime-200/50 hover:text-lime-50 transition-colors"
      >
        Powered by EmbedLabs
      </a>
      <p className="text-[10px] text-lime-200/30 mt-1">
        v{version}
      </p>
    </div>
  )
}
