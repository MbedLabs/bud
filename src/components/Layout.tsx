import { useState, useEffect } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { LayoutDashboard, PlayCircle, Server, Settings, Sun, Moon, Activity } from 'lucide-react'

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
  const [dark, setDark] = useDarkMode()

  const activeNav = navigation.find(n =>
    n.href === location.pathname ||
    (n.href !== '/' && location.pathname.startsWith(n.href))
  )

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 bg-gradient-sidebar text-white flex flex-col fixed inset-y-0 left-0 z-30">
        {/* Logo */}
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

        {/* Navigation */}
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
                {isActive && (
                  <div className="ml-auto w-1.5 h-1.5 rounded-full bg-teal-400" />
                )}
              </Link>
            )
          })}
        </nav>

        {/* Bottom section */}
        <div className="px-3 pb-4 space-y-1">
          <div className="h-px bg-white/10 mx-2 mb-3" />
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
          <button
            onClick={() => setDark(!dark)}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-teal-100/70 hover:bg-[var(--sidebar-hover)] hover:text-white transition-all duration-200 w-full group"
          >
            {dark ? (
              <Sun className="h-[18px] w-[18px] text-teal-400/50 group-hover:text-teal-300" />
            ) : (
              <Moon className="h-[18px] w-[18px] text-teal-400/50 group-hover:text-teal-300" />
            )}
            {dark ? 'Light Mode' : 'Dark Mode'}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col ml-64">
        <header className="glass border-b border-border sticky top-0 z-20">
          <div className="px-6 py-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-foreground">
                {activeNav?.name || (location.pathname === '/settings' ? 'Settings' : 'Dashboard')}
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                {location.pathname === '/' && 'Overview of your test activity'}
                {location.pathname === '/runs' && 'View and filter all test runs'}
                {location.pathname === '/test-stations' && 'Monitor connected test stations'}
                {location.pathname === '/settings' && 'Manage your preferences'}
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
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-teal-700 flex items-center justify-center text-white text-xs font-bold">
                U
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
