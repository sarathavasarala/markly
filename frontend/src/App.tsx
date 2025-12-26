import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Search from './pages/Search'
import Import from './pages/Import'
import { useEffect } from 'react'

import { useUIStore } from './stores/uiStore'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, token, checkAuth, isLoading } = useAuthStore((state) => ({
    isAuthenticated: state.isAuthenticated,
    token: state.token,
    checkAuth: state.checkAuth,
    isLoading: state.isLoading,
  }))

  useEffect(() => {
    if (token) {
      checkAuth()
    }
  }, [token, checkAuth])

  if (isLoading && token) {
    return null
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function App() {
  const applyTheme = useUIStore((state) => state.applyTheme)

  useEffect(() => {
    applyTheme()
  }, [applyTheme])

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="search" element={<Search />} />
        <Route path="import" element={<Import />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
