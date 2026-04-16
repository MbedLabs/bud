import { useState, useEffect, useRef } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { LayoutDashboard, PlayCircle, Server, Settings, Sun, Moon, Activity, LogOut, ChevronDown, Users, ExternalLink } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { APP_VERSION } from '../api/client'

const BLOOM_ALM_URL = import.meta.env.VITE_BLOOM_ALM_URL || 'http://localhost:3001'

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
      <aside className="w-64 bg-gradient-sidebar text-white flex flex-col fixed inset-y-0 left-0 z-30">
        <div className="px-5 pt-6 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-white/15 flex items-center justify-center">
              <Activity className="h-5 w-5 text-teal-200" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-teal-100 tracking-tight">Bud</h1>
              <p className="text-[11px] text-teal-300/60 font-medium uppercase tracking-wider">Test Platform</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 mt-4 space-y-1 sidebar-scrollbar overflow-y-auto">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href ||
              (item.href !== '/' && location.pathname.startsWith(item.href))
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 group ${
                  isActive
                    ? 'bg-[var(--sidebar-active)] text-white shadow-sm'
                    : 'text-teal-100/70 hover:bg-[var(--sidebar-hover)] hover:text-white'
                }`}
              >
                <item.icon className={`h-[18px] w-[18px] transition-colors ${
                  isActive ? 'text-teal-300' : 'text-teal-400/50 group-hover:text-teal-300'
                }`} />
                {item.name}
                {isActive && <div className="ml-auto w-1.5 h-1.5 rounded-full bg-teal-400" />}
              </Link>
            )
          })}
          {user?.role === 'admin' && (
            <Link
              to="/users"
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 group ${
                location.pathname === '/users'
                  ? 'bg-[var(--sidebar-active)] text-white shadow-sm'
                  : 'text-teal-100/70 hover:bg-[var(--sidebar-hover)] hover:text-white'
              }`}
            >
              <Users className="h-[18px] text-teal-400/50 group-hover:text-teal-300" />
              Users
            </Link>
          )}
        </nav>

        <div className="px-3 pb-4 space-y-1">
          <div className="h-px bg-white/10 mx-2 mb-3" />
          <a
            href={BLOOM_ALM_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-teal-100/70 hover:bg-[var(--sidebar-hover)] hover:text-white transition-all duration-200 group"
          >
            <ExternalLink className="h-[18px] w-[18px] text-teal-400/50 group-hover:text-teal-300" />
            Bloom ALM
          </a>
          <Link
            to="/settings"
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 group ${
              location.pathname === '/settings'
                ? 'bg-[var(--sidebar-active)] text-white'
                : 'text-teal-100/70 hover:bg-[var(--sidebar-hover)] hover:text-white'
            }`}
          >
            <Settings className={`h-[18px] w-[18px] ${
              location.pathname === '/settings'
                ? 'text-teal-300'
                : 'text-teal-400/50 group-hover:text-teal-300'
            }`} />
            Settings
          </Link>
          <div className="pt-2 pb-1 px-3 text-center">
            <a
              href="https://www.embedlabs.de/en"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[10px] text-teal-300/50 hover:text-teal-200 transition-colors"
            >
              by EmbedLabs
            </a>
            <p className="text-[10px] text-teal-300/30 mt-1">v{APP_VERSION}</p>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col ml-64">
        <header className="glass border-b border-border sticky top-0 z-20">
          <div className="px-6 py-4 flex items-center justify-between">
            <div>
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
