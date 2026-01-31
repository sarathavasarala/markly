import { create } from 'zustand'
import { Bookmark } from '../lib/api'

export type BookmarkViewMode = 'cards' | 'list' | 'folders'
export type Theme = 'light' | 'dark'

const VIEW_STORAGE_KEY = 'markly_bookmarks_view_mode'
const THEME_STORAGE_KEY = 'markly_theme'

const readInitialViewMode = (): BookmarkViewMode => {
  const raw = localStorage.getItem(VIEW_STORAGE_KEY)
  return raw === 'list' || raw === 'cards' || raw === 'folders' ? raw : 'folders'
}

const readInitialTheme = (): Theme => {
  const raw = localStorage.getItem(THEME_STORAGE_KEY)
  if (raw === 'light' || raw === 'dark') return raw
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

interface UIState {
  bookmarksViewMode: BookmarkViewMode
  setBookmarksViewMode: (mode: BookmarkViewMode) => void
  theme: Theme
  toggleTheme: () => void
  applyTheme: (themeOverride?: Theme) => void
  editingBookmark: Bookmark | null
  setEditingBookmark: (bookmark: Bookmark | null) => void
  isAddModalOpen: boolean
  setIsAddModalOpen: (isOpen: boolean) => void
  isSidebarOpen: boolean
  setIsSidebarOpen: (isOpen: boolean) => void
  toggleSidebar: () => void
}

export const useUIStore = create<UIState>((set, get) => ({
  bookmarksViewMode: readInitialViewMode(),
  setBookmarksViewMode: (mode) => {
    localStorage.setItem(VIEW_STORAGE_KEY, mode)
    set({ bookmarksViewMode: mode })
  },
  theme: readInitialTheme(),
  toggleTheme: () => {
    const newTheme = get().theme === 'light' ? 'dark' : 'light'
    localStorage.setItem(THEME_STORAGE_KEY, newTheme)
    set({ theme: newTheme })
    get().applyTheme(newTheme)
  },
  applyTheme: (themeOverride?: Theme) => {
    const theme = themeOverride || get().theme
    if (theme === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  },
  editingBookmark: null,
  setEditingBookmark: (bookmark) => set({ editingBookmark: bookmark }),
  isAddModalOpen: false,
  setIsAddModalOpen: (isOpen) => set({ isAddModalOpen: isOpen }),
  isSidebarOpen: false, // Hidden by default as requested
  setIsSidebarOpen: (isOpen) => set({ isSidebarOpen: isOpen }),
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen }))
}))
