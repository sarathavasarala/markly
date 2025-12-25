import { create } from 'zustand'
import { bookmarksApi, Bookmark, BookmarkListResponse } from '../lib/api'

interface BookmarksState {
  bookmarks: Bookmark[]
  total: number
  page: number
  perPage: number
  pages: number
  isLoading: boolean
  error: string | null
  
  // Filters
  filters: {
    domain?: string
    content_type?: string
    tag?: string
    collection_id?: string
    status?: string
    sort: string
    order: 'asc' | 'desc'
  }
  
  // Actions
  fetchBookmarks: (page?: number) => Promise<void>
  createBookmark: (url: string, notes?: string, description?: string) => Promise<Bookmark | null>
  deleteBookmark: (id: string) => Promise<void>
  setFilters: (filters: Partial<BookmarksState['filters']>) => void
  clearFilters: () => void
  trackAccess: (id: string) => Promise<void>
  retryEnrichment: (id: string) => Promise<void>
  refreshBookmark: (id: string) => Promise<void>
  upsertBookmark: (bookmark: Bookmark) => void
}

export const useBookmarksStore = create<BookmarksState>((set, get) => ({
  bookmarks: [],
  total: 0,
  page: 1,
  perPage: 20,
  pages: 0,
  isLoading: false,
  error: null,
  
  filters: {
    sort: 'created_at',
    order: 'desc',
  },
  
  fetchBookmarks: async (page = 1) => {
    set({ isLoading: true, error: null })
    
    try {
      const { filters, perPage } = get()
      const response = await bookmarksApi.list({
        page,
        per_page: perPage,
        ...filters,
      })
      
      const data: BookmarkListResponse = response.data
      
      set({
        bookmarks: data.bookmarks,
        total: data.total,
        page: data.page,
        pages: data.pages,
        isLoading: false,
      })
    } catch (error: unknown) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to fetch bookmarks',
      })
    }
  },
  
  createBookmark: async (url: string, notes?: string, description?: string) => {
    try {
      const response = await bookmarksApi.create(url, notes, description)
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
  
  setFilters: (newFilters) => {
    set((state) => ({
      filters: { ...state.filters, ...newFilters },
    }))
  },
  
  clearFilters: () => {
    set({
      filters: {
        sort: 'created_at',
        order: 'desc',
      },
    })
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
}))
