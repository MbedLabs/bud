import { useState, useEffect, useRef } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, PlayCircle, Server, Settings, Sun, Moon, Activity,
  LogOut, ChevronDown, ChevronLeft, ChevronRight, Users, ExternalLink,
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { APP_VERSION } from '../api/client'

const getBloomUrl = () => {
  const runtimeUrl = window.runtimeConfig?.BLOOM_APP_URL
  const buildTimeUrl = import.meta.env.VITE_BLOOM_ALM_URL
  const rawUrl = runtimeUrl || buildTimeUrl || 'http://localhost:3001'
  return rawUrl.replace(/\/api\/?$/, '')
}

const BLOOM_ALM_URL = getBloomUrl()

/** Must match Tailwind w-60 / w-14 and main ml-* — also positions the seam toggle. */
const SIDEBAR_EDGE = { expanded: '15rem', collapsed: '3.5rem' } as const

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Test Runs', href: '/runs', icon: PlayCircle },
  { name: 'Test Stations', href: '/test-stations', icon: Server },
]

function useDarkMode() {
  const [dark, setDark] = useState(() => {
    const stored = localStorage.getItem('bud-theme')
    if (stored) return stored === 'dark'
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })

  useEffect(() => {
    const root = document.documentElement
    if (dark) {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
    localStorage.setItem('bud-theme', dark ? 'dark' : 'light')
  }, [dark])

  return [dark, setDark] as const
}

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [dark, setDark] = useDarkMode()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    const stored = localStorage.getItem('bud-sidebar-collapsed')
    return stored ? stored === 'true' : false
  })
  const userMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    localStorage.setItem('bud-sidebar-collapsed', String(sidebarCollapsed))
  }, [sidebarCollapsed])

  const activeNav = navigation.find(n =>
    n.href === location.pathname ||
    (n.href !== '/' && location.pathname.startsWith(n.href))
  )

  const roleBadgeColor = user?.role === 'admin'
    ? 'bg-red-500/10 text-red-400'
    : 'bg-green-500/10 text-green-400'

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const userInitials = user?.full_name
    ? user.full_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : 'U'

  return (
    <div className="min-h-screen flex">
      <aside className={`${sidebarCollapsed ? 'w-14' : 'w-60'} sidebar-scrollbar bg-gradient-sidebar text-white flex flex-col fixed inset-y-0 left-0 z-30 overflow-y-auto transition-all duration-200`}>
        <div className={`${sidebarCollapsed ? 'px-2 pt-4 pb-2.5' : 'px-3 pt-4 pb-2.5'}`}>
          <div className={`flex items-center ${sidebarCollapsed ? 'justify-center' : 'gap-2.5'}`}>
            <div className="w-9 h-9 rounded-lg bg-white/15 flex items-center justify-center shrink-0">
              <Activity className="h-5 w-5 text-teal-200" />
            </div>
            {!sidebarCollapsed && (
              <div className="min-w-0">
                <h1 className="text-base font-bold text-teal-100 tracking-tight">Bud</h1>
                <p className="text-[10px] text-teal-300/60 font-medium uppercase tracking-wider leading-snug">Test Management Platform</p>
              </div>
            )}
          </div>
        </div>

        <nav className={`flex-1 ${sidebarCollapsed ? 'px-2' : 'px-3'} mt-4 space-y-1`}>
          {navigation.map((item) => {
            const isActive = location.pathname === item.href ||
              (item.href !== '/' && location.pathname.startsWith(item.href))
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`flex items-center ${sidebarCollapsed ? 'justify-center px-2' : 'gap-2.5 px-3'} py-2 rounded-lg text-sm font-medium transition-all duration-200 group ${
                  isActive
                    ? 'bg-[var(--sidebar-active)] text-white shadow-sm'
                    : 'text-teal-100/70 hover:bg-[var(--sidebar-hover)] hover:text-white'
                }`}
                title={sidebarCollapsed ? item.name : undefined}
                onClick={() => {
                  if (sidebarCollapsed && location.pathname !== item.href) {
                    setSidebarCollapsed(false)
                  }
                }}
              >
                <item.icon className={`h-[18px] w-[18px] shrink-0 transition-colors ${
                  isActive ? 'text-teal-300' : 'text-teal-400/50 group-hover:text-teal-300'
                }`} />
                {!sidebarCollapsed && item.name}
                {isActive && !sidebarCollapsed && <div className="ml-auto w-1.5 h-1.5 rounded-full bg-teal-400" />}
              </Link>
            )
          })}
          {user?.role === 'admin' && (
            <Link
              to="/users"
              className={`flex items-center ${sidebarCollapsed ? 'justify-center px-2' : 'gap-2.5 px-3'} py-2 rounded-lg text-sm font-medium transition-all duration-200 group ${
                location.pathname === '/users'
                  ? 'bg-[var(--sidebar-active)] text-white shadow-sm'
                  : 'text-teal-100/70 hover:bg-[var(--sidebar-hover)] hover:text-white'
              }`}
              title={sidebarCollapsed ? 'Users' : undefined}
              onClick={() => {
                if (sidebarCollapsed && location.pathname !== '/users') {
                  setSidebarCollapsed(false)
                }
              }}
            >
              <Users className="h-[18px] w-[18px] shrink-0 text-teal-400/50 group-hover:text-teal-300" />
              {!sidebarCollapsed && 'Users'}
            </Link>
          )}
        </nav>

        <div className={`mt-auto ${sidebarCollapsed ? 'px-2' : 'px-3'} pb-4 pt-2 space-y-1`} style={{ paddingBottom: 'max(1rem, env(safe-area-inset-bottom))' }}>
          <div className="h-px bg-white/10 mx-2 mb-2" />
          <a
            href={BLOOM_ALM_URL}
            target="_blank"
            rel="noopener noreferrer"
            className={`flex items-center ${sidebarCollapsed ? 'justify-center px-2' : 'gap-2.5 px-3'} py-1.5 rounded-lg text-[13px] font-medium text-teal-100/70 hover:bg-[var(--sidebar-hover)] hover:text-white transition-all duration-200 group`}
            title={sidebarCollapsed ? 'Bloom PLM' : undefined}
          >
            <ExternalLink className="h-4 w-4 shrink-0 text-teal-400/50 group-hover:text-teal-300" />
            {!sidebarCollapsed && 'Bloom PLM'}
          </a>
          <Link
            to="/settings"
            className={`flex items-center ${sidebarCollapsed ? 'justify-center px-2' : 'gap-2.5 px-3'} py-1.5 rounded-lg text-[13px] font-medium transition-all duration-200 group ${
              location.pathname === '/settings'
                ? 'bg-[var(--sidebar-active)] text-white'
                : 'text-teal-100/70 hover:bg-[var(--sidebar-hover)] hover:text-white'
            }`}
            title={sidebarCollapsed ? 'Settings' : undefined}
            onClick={() => {
              if (sidebarCollapsed && location.pathname !== '/settings') {
                setSidebarCollapsed(false)
              }
            }}
          >
            <Settings className={`h-4 w-4 shrink-0 ${
              location.pathname === '/settings'
                ? 'text-teal-300'
                : 'text-teal-400/50 group-hover:text-teal-300'
            }`} />
            {!sidebarCollapsed && 'Settings'}
          </Link>
          {!sidebarCollapsed && (
            <div className="pt-2 pb-1 px-3 text-center">
              <a
                href="https://www.embedlabs.net"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[10px] text-teal-300/50 hover:text-teal-200 transition-colors"
              >
                by EmbedLabs
              </a>
              <p className="text-[10px] text-teal-300/30 mt-1">v{APP_VERSION}</p>
            </div>
          )}
        </div>
      </aside>

      <button
        type="button"
        onClick={() => setSidebarCollapsed((c) => !c)}
        className="fixed z-[35] top-4 flex h-8 w-8 -translate-x-1/2 items-center justify-center rounded-full border border-border bg-background text-muted-foreground shadow-md transition-[left,background-color,color,box-shadow] duration-200 hover:bg-accent hover:text-foreground dark:bg-card dark:hover:bg-accent"
        style={{ left: sidebarCollapsed ? SIDEBAR_EDGE.collapsed : SIDEBAR_EDGE.expanded }}
        aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {sidebarCollapsed ? <ChevronRight className="h-4 w-4" strokeWidth={2.25} /> : <ChevronLeft className="h-4 w-4" strokeWidth={2.25} />}
      </button>

      <div className={`flex-1 flex flex-col min-w-0 ${sidebarCollapsed ? 'ml-14' : 'ml-60'} transition-all duration-200`}>
        <header className="glass border-b border-border sticky top-0 z-20">
          <div className="px-6 py-4 flex items-center justify-between">
            <div className="pl-6">
              <h2 className="text-lg font-semibold text-foreground">
                {activeNav?.name || (location.pathname === '/settings' ? 'Settings' : location.pathname === '/users' ? 'Users' : 'Dashboard')}
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                {location.pathname === '/' && 'Overview of your test activity'}
                {location.pathname === '/runs' && 'View and filter all test runs'}
                {location.pathname === '/test-stations' && 'Monitor connected test stations'}
                {location.pathname === '/settings' && 'Manage your preferences'}
                {location.pathname === '/users' && 'Manage users'}
                {location.pathname.startsWith('/runs/') && 'Test run details and results'}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setDark(!dark)}
                className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
              >
                {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </button>
              <div className="relative" ref={userMenuRef}>
                <button
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className="flex items-center gap-2 p-1 rounded-lg hover:bg-accent transition-colors"
                >
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-teal-700 flex items-center justify-center text-white text-xs font-bold">
                    {userInitials}
                  </div>
                  <span className="text-sm text-foreground font-medium hidden sm:block max-w-[120px] truncate">
                    {user?.full_name}
                  </span>
                  <ChevronDown className="h-3 w-3 text-muted-foreground" />
                </button>
                {userMenuOpen && (
                  <div className="absolute right-0 top-full mt-2 w-64 bg-card border border-border rounded-lg shadow-elegant overflow-hidden z-50">
                    <div className="px-4 py-3 border-b border-border">
                      <p className="text-sm font-medium text-foreground">{user?.full_name}</p>
                      <p className="text-xs text-muted-foreground">{user?.email}</p>
                      <span className={`inline-block mt-1.5 px-2 py-0.5 rounded text-[10px] font-semibold uppercase ${roleBadgeColor}`}>
                        {user?.role}
                      </span>
                    </div>
                    <div className="py-1">
                      <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-2 px-4 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                      >
                        <LogOut className="h-4 w-4" />
                        Sign out
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        <main className="flex-1 p-6 bg-background overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
