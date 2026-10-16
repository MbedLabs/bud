import { useEffect, useState } from 'react'
import { authApi, type ProfilePerson } from '../api/client'

/**
 * A person's profile picture, or their initials when none is stored.
 */
export default function ProfilePicture({ user, className = 'w-8 h-8', own = false }: Readonly<{
  user: ProfilePerson | null
  className?: string
  own?: boolean
}>) {
  const [image, setImage] = useState<{ key: string; url: string } | null>(null)
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  const id = user?.id
  const updatedAt = user?.updated_at
  const hasPicture = user?.has_profile_picture
  const suppliedUrl = user?.profile_picture_url
  const key = `${id}:${updatedAt}`

  useEffect(() => {
    if (!own || !hasPicture || suppliedUrl !== undefined) return
    let active = true
    const reader = new FileReader()
    reader.onload = () => {
      if (active && typeof reader.result === 'string') {
        setImage({ key: `${id}:${updatedAt}`, url: reader.result })
      }
    }
    reader.onerror = () => {
      if (active) setImage(null)
    }
    void authApi.fetchProfilePicture().then(blob => {
      if (!active || !blob) return
      reader.readAsDataURL(blob)
    }).catch(() => {
      if (active) setImage(null)
    })
    return () => {
      active = false
      if (reader.readyState === FileReader.LOADING) reader.abort()
    }
  }, [id, updatedAt, hasPicture, own, suppliedUrl])

  const initials = user?.full_name.split(' ').map(part => part[0]).join('').toUpperCase().slice(0, 2) || 'U'
  const url = suppliedUrl ?? (suppliedUrl === undefined && hasPicture && image?.key === key ? image.url : null)
  return (
    <span className={`${className} rounded-full overflow-hidden bg-linear-to-br/srgb from-primary to-bud-orange inline-flex shrink-0 items-center justify-center text-white text-xs font-bold`}>
      {url && failedUrl !== url
        ? <img src={url} alt={own ? 'Your profile picture' : `${user?.full_name}'s profile picture`} className="h-full w-full object-cover" onError={() => setFailedUrl(url)} />
        : initials}
    </span>
  )
}
