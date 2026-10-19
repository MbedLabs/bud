import { lazy } from 'react'
import { Routes, Route, Link, Navigate } from 'react-router'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import AcceptInvite from './pages/AcceptInvite'
import VerifyEmail from './pages/VerifyEmail'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'
import ConfirmEmailChange from './pages/ConfirmEmailChange'
import Setup from './pages/Setup'
import { useAuth } from './contexts/AuthContext'

/* v8 ignore start */
const CustomRun = lazy(() => import('./pages/CustomRun'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Settings = lazy(() => import('./pages/Settings'))
const TestRunDetail = lazy(() => import('./pages/TestRunDetail'))
const TestRuns = lazy(() => import('./pages/TestRuns'))
const TestStations = lazy(() => import('./pages/TestStations'))
const Users = lazy(() => import('./pages/Users'))
const Access = lazy(() => import('./pages/Access'))
const Audit = lazy(() => import('./pages/Audit'))
/* v8 ignore stop */

/** Account-management route for the Admin base role. */
function UsersRoute() {
  const { user } = useAuth()
  return user?.role === 'admin' ? <Users /> : <Navigate to="/" replace />
}

function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center h-64 animate-fade-in">
      <div className="w-20 h-20 rounded-2xl bg-linear-to-br/srgb from-primary/10 to-lime-500/10 flex items-center justify-center mb-5">
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
        <Route path="/setup" element={<Setup />} />
        <Route path="/login" element={<Login />} />
        <Route path="/accept-invite" element={<AcceptInvite />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/confirm-email-change" element={<ConfirmEmailChange />} />
        <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<Dashboard />} />
          <Route path="runs" element={<TestRuns />} />
          <Route path="custom-run" element={<CustomRun />} />
          <Route path="runs/:id" element={<TestRunDetail />} />
          <Route path="test-stations" element={<TestStations />} />
          <Route path="settings" element={<Settings />} />
          <Route path="users" element={<UsersRoute />} />
          <Route path="access" element={<Access />} />
          <Route path="audit" element={<Audit />} />
          <Route path="*" element={<NotFound />} />
        </Route>
    </Routes>
  )
}

export default App
