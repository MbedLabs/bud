// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { accessRequestsApi, auditApi, authApi, groupsApi, usersApi, type User } from '../api/client'
import Layout from '../components/Layout'
import ProfilePicture from '../components/ProfilePicture'
import AccessRequestsPanel from '../components/AccessRequestsPanel'
import Audit from '../pages/Audit'
import Users from '../pages/Users'

const account = vi.hoisted(() => ({
  id: 1, full_name: 'Ada Admin', email: 'ada@example.com', role: 'admin',
  is_active: true, created_at: '', updated_at: '', has_profile_picture: true,
  profile_picture_url: 'data:image/png;base64,YWRh',
}))
const member = { ...account, id: 2, full_name: 'Mira Member', email: 'mira@example.com',
  role: 'viewer', profile_picture_url: 'data:image/png;base64,bWlyYQ==' } as User

vi.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ user: account, logout: vi.fn() }) }))
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return {
    ...actual,
    usersApi: { ...actual.usersApi, list: vi.fn() },
    auditApi: { ...actual.auditApi, list: vi.fn() },
    accessRequestsApi: { ...actual.accessRequestsApi, list: vi.fn() },
    groupsApi: { ...actual.groupsApi, list: vi.fn() },
    authApi: { ...actual.authApi, fetchProfilePicture: vi.fn() },
  }
})

function mount(element: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return render(<QueryClientProvider client={client}><MemoryRouter>{element}</MemoryRouter></QueryClientProvider>)
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.setItem('bud-theme', 'dark')
  vi.mocked(usersApi.list).mockResolvedValue([account as User, member,
    { ...member, id: 3, full_name: 'Nora None', profile_picture_url: null, has_profile_picture: false }])
  vi.mocked(groupsApi.list).mockResolvedValue([])
})
afterEach(cleanup)

describe('saved pictures beside existing Bud identities', () => {
  it('shows each Users row picture and initials only for the person without one', async () => {
    mount(<Users />)
    const row = (name: string) => within(screen.getByText(name).closest('tr')!)
    await screen.findByText(member.full_name)
    expect(row(account.full_name).getByRole('img')).toHaveAttribute('src', account.profile_picture_url)
    expect(row(member.full_name).getByRole('img')).toHaveAttribute('src', member.profile_picture_url)
    expect(row('Nora None').queryByRole('img')).not.toBeInTheDocument()
    expect(row('Nora None').getByText('NN')).toBeInTheDocument()
    expect(authApi.fetchProfilePicture).not.toHaveBeenCalled()
  })

  it('uses the signed-in person picture in the account menu', () => {
    mount(<Layout />)
    expect(screen.getByAltText('Your profile picture')).toHaveAttribute('src', account.profile_picture_url)
  })

  it('uses the audit actor picture and keeps unidentified actors as text', async () => {
    vi.mocked(auditApi.list).mockResolvedValue({ total: 2, items: [
      { id: 1, occurred_at: '', actor_user_id: member.id, actor_name: member.full_name,
        actor_profile_picture_url: member.profile_picture_url, actor_type: 'user', action: 'auth.login', outcome: 'success' },
      { id: 2, occurred_at: '', actor_user_id: null, actor_name: null,
        actor_profile_picture_url: null, actor_type: 'anonymous', action: 'auth.login', outcome: 'failure' },
    ] } as never)
    mount(<Audit />)
    expect(await screen.findByAltText("Mira Member's profile picture")).toHaveAttribute('src', member.profile_picture_url)
    expect(within(screen.getByText('anonymous').closest('tr')!).queryByRole('img')).not.toBeInTheDocument()
  })

  it('uses the access requester picture rather than the viewing administrator picture', async () => {
    vi.mocked(accessRequestsApi.list).mockResolvedValue([{
      id: 1, requester_name: member.full_name, requester_email: member.email,
      requester_profile_picture_url: member.profile_picture_url, resource_type: 'test-run', resource_ref: '42',
    }] as never)
    mount(<AccessRequestsPanel />)
    expect(await screen.findByAltText("Mira Member's profile picture")).toHaveAttribute('src', member.profile_picture_url)
    expect(screen.getByText(/asks for test run 42/)).toBeInTheDocument()
    expect(authApi.fetchProfilePicture).not.toHaveBeenCalled()
  })

  it('replaces a displayed picture, handles a broken image and returns to initials after removal', () => {
    const { rerender } = render(<ProfilePicture user={member} />)
    expect(screen.getByRole('img')).toHaveAttribute('src', member.profile_picture_url)
    fireEvent.error(screen.getByRole('img'))
    expect(screen.getByText('MM')).toBeInTheDocument()
    const replacement = 'data:image/png;base64,bmV3'
    rerender(<ProfilePicture user={{ ...member, profile_picture_url: replacement }} />)
    expect(screen.getByRole('img')).toHaveAttribute('src', replacement)
    rerender(<ProfilePicture user={{ ...member, has_profile_picture: false, profile_picture_url: null }} />)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByText('MM')).toBeInTheDocument()
  })
})
