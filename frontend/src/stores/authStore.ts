import { create } from 'zustand'
import { authApi } from '../lib/api'

interface AuthState {
  isAuthenticated: boolean
  token: string | null
  expiresAt: string | null
  isLoading: boolean
  error: string | null
  
  login: (secretPhrase: string) => Promise<boolean>
  logout: () => void
  checkAuth: () => Promise<boolean>
  clearError: () => void
}

export const useAuthStore = create<AuthState>((set, get) => ({
  isAuthenticated: !!localStorage.getItem('markly_token'),
  token: localStorage.getItem('markly_token'),
  expiresAt: localStorage.getItem('markly_expires'),
  isLoading: false,
  error: null,
  
  login: async (secretPhrase: string) => {
    set({ isLoading: true, error: null })
    
    try {
      const response = await authApi.login(secretPhrase)
      const { token, expires_at } = response.data
      
      localStorage.setItem('markly_token', token)
      localStorage.setItem('markly_expires', expires_at)
      
      set({
        isAuthenticated: true,
        token,
        expiresAt: expires_at,
        isLoading: false,
      })
      
      return true
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Login failed'
      set({
        isLoading: false,
        error: message,
      })
      return false
    }
  },
  
  logout: () => {
    authApi.logout().catch(() => {})
    
    localStorage.removeItem('markly_token')
    localStorage.removeItem('markly_expires')
    
    set({
      isAuthenticated: false,
      token: null,
      expiresAt: null,
    })
  },
  
  checkAuth: async () => {
    const token = localStorage.getItem('markly_token')
    
    if (!token) {
      set({ isAuthenticated: false })
      return false
    }
    
    try {
      set({ isLoading: true })
      const response = await authApi.verify()
      
      if (response.data.valid) {
        set({ isAuthenticated: true, isLoading: false })
        return true
      } else {
        get().logout()
        return false
      }
    } catch {
      get().logout()
      return false
    } finally {
      set({ isLoading: false })
    }
  },
  
  clearError: () => set({ error: null }),
}))
