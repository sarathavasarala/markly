import { create } from 'zustand'
import { authApi, AuthUser } from '../lib/api'

function formatAuthError(error: any): string | null {
  if (!error) return null

  // 401 Unauthorized is a normal state indicating "not logged in" rather than a system failure,
  // so we return null to avoid flashing red error alerts on initial load.
  if (error.response?.status === 401) {
    return null
  }

  // Network offline / DNS / server unreachable
  if (error.message === 'Network Error' || error.code === 'ERR_NETWORK') {
    return 'Our servers are experiencing issues. Please check your internet connection and try again.'
  }

  // Server-side crash / internal error
  if (error.response?.status === 500) {
    return 'Our servers are experiencing issues. Please try again in a few moments.'
  }

  return error.response?.data?.error || error.message || 'An unexpected error occurred.'
}

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
      set({ error: formatAuthError(error), isLoading: false })
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
        error: formatAuthError(error),
        isLoading: false,
      })
    }
  },

  clearError: () => set({ error: null }),
}))
