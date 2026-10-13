// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { authApi, companyLogoApi } from '../api/client'
import Settings from '../pages/Settings'

const refreshUser = vi.hoisted(() => vi.fn(async () => undefined))
const account = vi.hoisted(() => ({
  id: 7, email: 'picture@example.com', full_name: 'Picture User', role: 'viewer',
  is_active: true, has_profile_picture: false, created_at: '', updated_at: '',
}))

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: account, refreshUser }),
}))
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return { ...actual, authApi: { ...actual.authApi,
    setProfilePicture: vi.fn(), fetchProfilePicture: vi.fn(), deleteProfilePicture: vi.fn(),
  }, companyLogoApi: { ...actual.companyLogoApi, fetchLogo: vi.fn(), deleteLogo: vi.fn() },
  settingsApi: { ...actual.settingsApi, getPLM: vi.fn().mockResolvedValue({
    bloom_url: '', has_bloom_token: false, bloom_token_prefix: null, bloom_token_rotated_at: null,
  }) },
  }
})

function renderSettings() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <Settings />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  account.has_profile_picture = false
  vi.mocked(companyLogoApi.fetchLogo).mockResolvedValue(null)
  window.localStorage.clear()
  window.matchMedia = vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })) as unknown as typeof window.matchMedia
})
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('own-account profile picture', () => {
  it('uploads the chosen file and displays the saved authenticated image', async () => {
    vi.mocked(authApi.setProfilePicture).mockResolvedValue({ ...account, role: 'viewer', has_profile_picture: true, updated_at: 'new' })
    vi.mocked(authApi.fetchProfilePicture).mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
    renderSettings()
    const button = screen.getByRole('button', { name: 'Upload' })
    expect(button).toBeDisabled()
    const file = new File(['png'], 'profile.png', { type: 'image/png' })
    fireEvent.change(screen.getByLabelText('Profile picture'), { target: { files: [file] } })
    fireEvent.click(button)
    await waitFor(() => expect(authApi.setProfilePicture).toHaveBeenCalledWith(file))
    expect(await screen.findByText('Profile picture updated.')).toBeInTheDocument()
    expect(await screen.findByAltText('Your profile picture')).toHaveAttribute('src', 'data:image/png;base64,cG5n')
    expect(refreshUser).toHaveBeenCalled()
  })

  it('shows a rejected upload without claiming that it was saved', async () => {
    vi.mocked(authApi.setProfilePicture).mockRejectedValue({ isAxiosError: true, response: { data: { detail: 'The picture is invalid or too large.' } } })
    renderSettings()
    fireEvent.change(screen.getByLabelText('Profile picture'), { target: { files: [new File(['bad'], 'bad.png', { type: 'image/png' })] } })
    fireEvent.click(screen.getByRole('button', { name: 'Upload' }))
    expect(await screen.findByText('The picture is invalid or too large.')).toBeInTheDocument()
    expect(screen.queryByText('Profile picture updated.')).not.toBeInTheDocument()
    expect(refreshUser).not.toHaveBeenCalled()
  })

  it('removes a saved own picture and returns to initials', async () => {
    account.has_profile_picture = true
    vi.mocked(authApi.fetchProfilePicture).mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
    vi.mocked(authApi.deleteProfilePicture).mockResolvedValue({ ...account, role: 'viewer', has_profile_picture: false, updated_at: 'removed' })
    renderSettings()
    expect(await screen.findByAltText('Your profile picture')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Remove profile picture' }))
    expect(await screen.findByText('Profile picture removed.')).toBeInTheDocument()
    expect(authApi.deleteProfilePicture).toHaveBeenCalledOnce()
    expect(refreshUser).toHaveBeenCalledOnce()
    expect(screen.queryByAltText('Your profile picture')).not.toBeInTheDocument()
    expect(screen.getByText('PU')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remove profile picture' })).not.toBeInTheDocument()
  })

  it('keeps a saved own picture when removal fails', async () => {
    account.has_profile_picture = true
    vi.mocked(authApi.fetchProfilePicture).mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
    vi.mocked(authApi.deleteProfilePicture).mockRejectedValue({ isAxiosError: true, response: { data: { detail: 'Could not remove the picture.' } } })
    renderSettings()
    expect(await screen.findByAltText('Your profile picture')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Remove profile picture' }))
    expect(await screen.findByText('Could not remove the picture.')).toBeInTheDocument()
    expect(screen.getByAltText('Your profile picture')).toBeInTheDocument()
    expect(screen.queryByText('Profile picture removed.')).not.toBeInTheDocument()
    expect(refreshUser).not.toHaveBeenCalled()
  })

  it('has no picture removal control without a saved picture', () => {
    renderSettings()
    expect(screen.queryByRole('button', { name: 'Remove profile picture' })).not.toBeInTheDocument()
  })
})
