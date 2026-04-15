import { Routes, Route, Link } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import TestRuns from './pages/TestRuns'
import TestRunDetail from './pages/TestRunDetail'
import TestStations from './pages/TestStations'
import Users from './pages/Users'
import Settings from './pages/Settings'

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-64 animate-fade-in">
      <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary/10 to-cyan-500/10 flex items-center justify-center mb-5">
        <span className="text-3xl font-bold text-primary/40">404</span>
      </div>
      <h2 className="text-xl font-bold text-foreground mb-2">Page Not Found</h2>
      <p className="text-sm text-muted-foreground mb-4">The page you are looking for does not exist.</p>
      <Link to="/" className="text-sm font-medium text-primary hover:text-primary/80 transition-colors">
        &larr; Back to Dashboard
      </Link>
    </div>
  )
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route index element={<Dashboard />} />
        <Route path="runs" element={<TestRuns />} />
        <Route path="runs/:id" element={<TestRunDetail />} />
        <Route path="test-stations" element={<TestStations />} />
        <Route path="settings" element={<Settings />} />
        <Route path="users" element={<Users />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}

export default App
