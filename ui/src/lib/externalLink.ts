/**
 * A URL supplied by a paired service, reduced to one that is safe to render.
 *
 * Returns the URL when it is http or https, and null for everything else -
 * `javascript:` and `data:` among them.
 */
export function safeExternalUrl(url: string | null | undefined): string | null {
  if (!url) return null
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? url : null
  } catch {
    return null
  }
}
