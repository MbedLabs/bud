import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import TestRuns from './pages/TestRuns'
import TestRunDetail from './pages/TestRunDetail'
import Runners from './pages/Runners'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="runs" element={<TestRuns />} />
        <Route path="runs/:id" element={<TestRunDetail />} />
        <Route path="runners" element={<Runners />} />
      </Route>
    </Routes>
  )
}

export default App
