import { Routes, Route, Navigate, useParams } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Search from './pages/Search'
import PublicProfile from './pages/PublicProfile'
import { useEffect } from 'react'

import { useUIStore } from './stores/uiStore'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuthStore()

  if (isLoading) {
    return <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
    </div>
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

// Handle /@username by catching :path and checking if it starts with @
function ProfileOrRedirect() {
  const { path } = useParams<{ path: string }>()

  // Check if this looks like a profile route (starts with @)
  if (path?.startsWith('@')) {
    const username = path.slice(1) // Remove the @
    return <PublicProfile username={username} />
  }

  // Not a profile route, redirect to home (which will handle auth)
  return <Navigate to="/" replace />
}

function App() {
  const applyTheme = useUIStore((state) => state.applyTheme)
  const initializeAuth = useAuthStore((state) => state.initialize)

  useEffect(() => {
    applyTheme()
    initializeAuth()
  }, [applyTheme, initializeAuth])

  return (
    <Routes>
      {/* Public routes - no auth required */}
      <Route path="/login" element={<Login />} />

      {/* Protected routes - must come before the catch-all */}
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
      </Route>

      {/* Catch-all: handles /@username and redirects unknown paths */}
      <Route path="/:path" element={<ProfileOrRedirect />} />
    </Routes>
  )
}

export default App
