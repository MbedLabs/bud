// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const auth = vi.hoisted(() => ({
  user: { role: 'admin', full_name: 'Admin', email: 'admin@example.com', permissions: [] as string[] },
}))
vi.mock('../contexts/AuthContext', () => ({ useAuth: () => ({ user: auth.user, isAuthenticated: true, isLoading: false, logout: vi.fn() }) }))
vi.mock('../pages/Dashboard', () => ({ default: () => <h1>Dashboard view</h1> }))
vi.mock('../hooks/useDarkMode', () => ({ useDarkMode: () => [false, vi.fn()] }))
vi.mock('../components/UserGroups', () => ({ default: () => <h2>Groups control</h2> }))
vi.mock('../components/AccessRequestsPanel', () => ({ default: () => <h2>Access requests control</h2> }))
vi.mock('../components/AccessPolicies', () => ({
  default: ({ canEdit }: { canEdit: boolean }) => <h2>Policies control {canEdit ? 'editable' : 'read-only'}</h2>,
}))
vi.mock('../components/AccessUsers', () => ({ default: () => <h2>Groups per user control</h2> }))
vi.mock('../api/client', () => ({
  APP_VERSION: 'test',
  usersApi: { list: vi.fn().mockResolvedValue([]) },
  accessApi: { users: vi.fn().mockResolvedValue([]) },
  accessRequestsApi: { list: vi.fn().mockResolvedValue([{ id: 1 }]) },
  extractApiErrorMessage: vi.fn(),
}))

const Layout = (await import('../components/Layout')).default
const Access = (await import('../pages/Access')).default
const App = (await import('../App')).default

function renderPage(page: React.ReactNode, entry = '/access') {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[entry]}>{page}</MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  auth.user.role = 'admin'
  auth.user.permissions = []
  localStorage.clear()
})
afterEach(cleanup)

describe('Access page', () => {
  it('keeps separate Users and Access sidebar links', () => {
    renderPage(<Layout />)
    expect(screen.getByRole('link', { name: 'Access' }).getAttribute('href')).toBe('/access')
    expect(screen.getByRole('link', { name: 'Users' }).getAttribute('href')).toBe('/users')
  })

  it('marks the Access link with the shield check icon', () => {
    renderPage(<Layout />)
    expect(screen.getByRole('link', { name: 'Access' }).querySelector('svg')?.getAttribute('class')).toContain('lucide-shield-check')
  })

  it('has assignments, Groups, Policies and Requests without account administration', async () => {
    renderPage(<Access />)
    expect(screen.getAllByRole('tab').map((tab) => tab.textContent?.replace(/\d+$/, ''))).toEqual([
      'Assignments',
      'Groups',
      'Policies',
      'Requests',
    ])
    expect(screen.queryByRole('button', { name: 'Invite User' })).toBeNull()
    expect(screen.getByText('Groups per user control')).toBeTruthy()
    fireEvent.click(screen.getByRole('tab', { name: 'Groups' }))
    expect(screen.getByText('Groups control')).toBeTruthy()
    fireEvent.click(screen.getByRole('tab', { name: 'Policies' }))
    expect(screen.getByText('Policies control editable')).toBeTruthy()
    fireEvent.click(screen.getByRole('tab', { name: /Requests/ }))
    expect(screen.getByText('Access requests control')).toBeTruthy()
    expect(await screen.findByText('1')).toBeTruthy()
  })

  it('opens the existing Users route and switches to Access without mixing the views', async () => {
    renderPage(<App />, '/users')
    expect(await screen.findByRole('button', { name: 'Invite User' })).toBeTruthy()
    expect(screen.queryByText('Groups per user control')).toBeNull()
    expect(screen.queryByRole('tab')).toBeNull()
    fireEvent.click(screen.getByRole('link', { name: 'Access' }))
    expect(await screen.findByText('Groups per user control')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Invite User' })).toBeNull()
    fireEvent.click(screen.getByRole('link', { name: 'Users' }))
    expect(await screen.findByRole('button', { name: 'Invite User' })).toBeTruthy()
    expect(screen.queryByText('Groups per user control')).toBeNull()
  })

  it('does not give an Access Manager the account-management route', async () => {
    auth.user.role = 'developer'
    auth.user.permissions = ['access.manage']
    renderPage(<App />, '/users')
    expect(await screen.findByRole('heading', { name: 'Dashboard view' })).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Users' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Invite User' })).toBeNull()
  })

  it('opens an access manager without account administration or policy editing', () => {
    auth.user.role = 'developer'
    auth.user.permissions = ['access.manage']
    renderPage(<><Layout /><Access /></>)
    expect(screen.getByRole('link', { name: 'Access' })).toBeTruthy()
    expect(screen.queryByRole('link', { name: 'Users' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Invite User' })).toBeNull()
    expect(screen.getByText('Groups per user control')).toBeTruthy()
    fireEvent.click(screen.getByRole('tab', { name: 'Policies' }))
    expect(screen.getByText('Policies control read-only')).toBeTruthy()
  })

  it('stays closed to users without access management', () => {
    auth.user.role = 'developer'
    auth.user.permissions = ['custom_runs.create', 'bloom_publish.execute']
    renderPage(<><Layout /><Access /></>)
    expect(screen.queryByRole('link', { name: 'Access' })).toBeNull()
    expect(screen.queryByRole('link', { name: 'Audit log' })).toBeNull()
    expect(screen.queryByRole('tab')).toBeNull()
    expect(screen.getByText('Access management is required.')).toBeTruthy()
  })
})
