import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Search from './pages/Search'
import Bookmarks from './pages/Bookmarks'
import Collections from './pages/Collections'
import CollectionDetail from './pages/CollectionDetail'
import { useEffect } from 'react'

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
        <Route path="bookmarks" element={<Bookmarks />} />
        <Route path="collections" element={<Collections />} />
        <Route path="collections/:id" element={<CollectionDetail />} />
      </Route>
    </Routes>
  )
}

export default App
