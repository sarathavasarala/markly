import { create } from 'zustand'
import { bookmarksApi, Bookmark } from '../lib/api'

interface BookmarksState {
  bookmarks: Bookmark[]
  total: number
  page: number
  perPage: number
  pages: number
  isLoading: boolean
  error: string | null

  createBookmark: (url: string, notes?: string, description?: string, extraData?: any) => Promise<Bookmark | null>
  deleteBookmark: (id: string) => Promise<void>
  trackAccess: (id: string) => Promise<void>
  retryEnrichment: (id: string) => Promise<void>
  refreshBookmark: (id: string) => Promise<void>
  upsertBookmark: (bookmark: Bookmark) => void
  updateBookmark: (id: string, data: Partial<Bookmark>) => Promise<void>
}

export const useBookmarksStore = create<BookmarksState>((set) => ({
  bookmarks: [],
  total: 0,
  page: 1,
  perPage: 20,
  pages: 0,
  isLoading: false,
  error: null,

  createBookmark: async (url: string, notes?: string, description?: string, extraData?: any) => {
    try {
      const response = await bookmarksApi.create(url, notes, description, extraData)
      const payload = response.data as any
      const newBookmark = payload.bookmark || payload
      const alreadyExists = payload.already_exists === true

      set((state) => ({
        bookmarks: state.bookmarks.some((b) => b.id === newBookmark.id)
          ? state.bookmarks.map((b) => (b.id === newBookmark.id ? newBookmark : b))
          : [newBookmark, ...state.bookmarks],
        total: alreadyExists ? state.total : state.total + 1,
      }))

      return newBookmark
    } catch (error: unknown) {
      set({
        error: error instanceof Error ? error.message : 'Failed to create bookmark',
      })
      return null
    }
  },

  deleteBookmark: async (id: string) => {
    try {
      await bookmarksApi.delete(id)

      set((state) => ({
        bookmarks: state.bookmarks.filter((b) => b.id !== id),
        total: state.total - 1,
      }))
    } catch (error: unknown) {
      set({
        error: error instanceof Error ? error.message : 'Failed to delete bookmark',
      })
    }
  },

  trackAccess: async (id: string) => {
    try {
      await bookmarksApi.trackAccess(id)

      set((state) => ({
        bookmarks: state.bookmarks.map((b) =>
          b.id === id ? { ...b, access_count: (b.access_count || 0) + 1 } : b
        ),
      }))
    } catch {
      // Silently fail
    }
  },

  retryEnrichment: async (id: string) => {
    try {
      await bookmarksApi.retry(id)

      set((state) => ({
        bookmarks: state.bookmarks.map((b) =>
          b.id === id ? { ...b, enrichment_status: 'pending' as const } : b
        ),
      }))
    } catch (error: unknown) {
      set({
        error: error instanceof Error ? error.message : 'Failed to retry enrichment',
      })
    }
  },

  refreshBookmark: async (id: string) => {
    try {
      const response = await bookmarksApi.get(id)
      const bookmark = response.data
      set((state) => ({
        bookmarks: state.bookmarks.some((b) => b.id === id)
          ? state.bookmarks.map((b) => (b.id === id ? bookmark : b))
          : [bookmark, ...state.bookmarks],
      }))
    } catch (error: unknown) {
      set({
        error: error instanceof Error ? error.message : 'Failed to refresh bookmark',
      })
    }
  },

  upsertBookmark: (bookmark: Bookmark) => {
    set((state) => ({
      bookmarks: state.bookmarks.some((b) => b.id === bookmark.id)
        ? state.bookmarks.map((b) => (b.id === bookmark.id ? bookmark : b))
        : [bookmark, ...state.bookmarks],
    }))
  },

  updateBookmark: async (id, data) => {
    try {
      const response = await bookmarksApi.update(id, data)
      const updated = response.data
      set((state) => ({
        bookmarks: state.bookmarks.map((b) => (b.id === id ? updated : b)),
      }))
    } catch (error: unknown) {
      set({
        error: error instanceof Error ? error.message : 'Failed to update bookmark',
      })
    }
  },
}))
