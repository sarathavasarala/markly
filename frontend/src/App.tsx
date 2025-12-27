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

function PublicProfileWrapper() {
  const { username } = useParams<{ username: string }>()
  return <PublicProfile username={username} />
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

      {/* 
        Support both /@username and /u/username
      */}
      <Route path="/@:username" element={<PublicProfileWrapper />} />
      <Route path="/u/:username" element={<PublicProfileWrapper />} />

      {/* Protected routes */}
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

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
