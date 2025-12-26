import { create } from 'zustand'
import { supabase } from '../lib/supabase'

interface AuthState {
  isAuthenticated: boolean
  user: any | null
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
  token: null, // We'll sync this to localStorage 'markly_token' for api.ts
  isLoading: true,
  error: null,

  signInWithGoogle: async () => {
    set({ isLoading: true, error: null })
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: window.location.origin,
        },
      })
      if (error) throw error
    } catch (error: any) {
      set({ error: error.message, isLoading: false })
    }
  },

  logout: async () => {
    set({ isLoading: true })
    try {
      await supabase.auth.signOut()
      localStorage.removeItem('markly_token')
      set({
        isAuthenticated: false,
        user: null,
        token: null,
        isLoading: false
      })
    } catch (error: any) {
      set({ error: error.message, isLoading: false })
    }
  },

  initialize: async () => {
    set({ isLoading: true })

    // Use getUser() instead of getSession() for a more robust check against the server
    const { data: { user } } = await supabase.auth.getUser()
    const { data: { session } } = await supabase.auth.getSession()

    // Set initial state
    if (user && session) {
      localStorage.setItem('markly_token', session.access_token)
      set({
        isAuthenticated: true,
        user: user,
        token: session.access_token,
        isLoading: false
      })
    } else {
      localStorage.removeItem('markly_token')
      set({
        isAuthenticated: false,
        user: null,
        token: null,
        isLoading: false
      })
    }

    // Listen for changes
    supabase.auth.onAuthStateChange((_event, session) => {
      if (session) {
        localStorage.setItem('markly_token', session.access_token)
        set({
          isAuthenticated: true,
          user: session.user,
          token: session.access_token,
          isLoading: false
        })
      } else {
        localStorage.removeItem('markly_token')
        set({
          isAuthenticated: false,
          user: null,
          token: null,
          isLoading: false
        })
      }
    })
  },

  clearError: () => set({ error: null }),
}))
