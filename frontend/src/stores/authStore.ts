import { create } from 'zustand'
import { authApi, AuthUser } from '../lib/api'

interface AuthState {
  isAuthenticated: boolean
  user: AuthUser | null
  token: string | null
  isLoading: boolean
  error: string | null

  signInWithGoogle: () => Promise<void>
  logout: () => Promise<void>
  initialize: () => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  user: null,
  token: null,
  isLoading: true,
  error: null,

  signInWithGoogle: async () => {
    set({ isLoading: true, error: null })
    authApi.loginWithGoogle()
  },

  logout: async () => {
    set({ isLoading: true })
    try {
      await authApi.logout()
      set({
        isAuthenticated: false,
        user: null,
        token: null,
        isLoading: false
      })
    } catch (error: any) {
      set({ error: error.response?.data?.error || error.message, isLoading: false })
    }
  },

  initialize: async () => {
    set({ isLoading: true })
    try {
      const { data } = await authApi.me()
      set({
        isAuthenticated: data.is_authenticated,
        user: data.user,
        token: null,
        isLoading: false,
      })
    } catch (error: any) {
      set({
        isAuthenticated: false,
        user: null,
        token: null,
        error: error.response?.data?.error || error.message,
        isLoading: false,
      })
    }
  },

  clearError: () => set({ error: null }),
}))
