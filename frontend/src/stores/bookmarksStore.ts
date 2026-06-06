import { create } from 'zustand'
import { bookmarksApi, Bookmark } from '../lib/api'

interface BookmarksState {
  bookmarks: Bookmark[]
  total: number
  totalCount: number // Global total across all folders
  page: number
  perPage: number
  pages: number
  isLoading: boolean
  error: string | null
  pollingInterval: NodeJS.Timeout | null
  lastParams: Parameters<typeof bookmarksApi.list>[0] | null

  fetchBookmarks: (params?: Parameters<typeof bookmarksApi.list>[0]) => Promise<void>
  fetchTotalCount: () => Promise<void>
  createBookmark: (url: string, notes?: string, description?: string, extraData?: any) => Promise<Bookmark | null>
  deleteBookmark: (id: string) => Promise<void>
  trackAccess: (id: string) => Promise<void>
  retryEnrichment: (id: string) => Promise<void>
  refreshBookmark: (id: string) => Promise<void>
  upsertBookmark: (bookmark: Bookmark) => void
  updateBookmark: (id: string, data: Partial<Bookmark>) => Promise<void>
  startPolling: (params: Parameters<typeof bookmarksApi.list>[0]) => void
  stopPolling: () => void
}


export const useBookmarksStore = create<BookmarksState>((set, get) => ({
  bookmarks: [],
  total: 0,
  totalCount: 0,
  page: 1,
  perPage: 20,
  pages: 0,
  isLoading: false,
  error: null,
  pollingInterval: null,
  lastParams: null,

  fetchBookmarks: async (params) => {
    set({ isLoading: true, error: null, lastParams: params || {} })
    try {
      const res = await bookmarksApi.list(params)
      const { bookmarks, total, page, per_page, pages } = res.data

      // When the request has no folder/tag filters the total IS the
      // global bookmark count — update totalCount as a side-effect to
      // avoid a separate API round-trip (was fetchTotalCount).
      const isUnfiltered = !params?.folder_id && (!params?.tag || params.tag.length === 0)
      const extra: Partial<BookmarksState> = isUnfiltered ? { totalCount: total } : {}

      set({ bookmarks, total, page, perPage: per_page, pages, ...extra })

      // Check if we need to start/stop polling based on enrichment/archive status
      const hasPendingOrProcessing = bookmarks.some(
        (b) =>
          b.enrichment_status === 'pending' ||
          b.enrichment_status === 'processing' ||
          b.archive_status === 'pending' ||
          b.archive_status === 'processing'
      )
      if (hasPendingOrProcessing) {
        get().startPolling(params)
      } else {
        get().stopPolling()
      }
    } catch (err: any) {
      set({ error: err.response?.data?.error || 'Failed to fetch bookmarks' })
    } finally {
      set({ isLoading: false })
    }
  },

  // Only fires a lightweight API call when totalCount hasn't already
  // been populated by an unfiltered fetchBookmarks call.
  fetchTotalCount: async () => {
    if (get().totalCount > 0) return
    try {
      const res = await bookmarksApi.list({ per_page: 1 })
      set({ totalCount: res.data.total })
    } catch (err) {
      console.error('Failed to fetch total count:', err)
    }
  },

  startPolling: (params) => {
    if (params) {
      set({ lastParams: params })
    }
    if (get().pollingInterval) return
    const interval = setInterval(() => {
      const currentParams = get().lastParams || {}
      // Background fetch without setting isLoading: true
      bookmarksApi.list(currentParams).then(res => {
        const { bookmarks } = res.data
        set({ bookmarks })
        const hasPendingOrProcessing = bookmarks.some(
          (b) =>
            b.enrichment_status === 'pending' ||
            b.enrichment_status === 'processing' ||
            b.archive_status === 'pending' ||
            b.archive_status === 'processing'
        )
        if (!hasPendingOrProcessing) {
          get().stopPolling()
        }
      }).catch(err => console.error('Polling failed:', err))
    }, 5000)
    set({ pollingInterval: interval })
  },

  stopPolling: () => {
    const interval = get().pollingInterval
    if (interval) {
      clearInterval(interval)
      set({ pollingInterval: null })
    }
  },

  createBookmark: async (url: string, notes?: string, description?: string, extraData?: any) => {
    try {
      const response = await bookmarksApi.create(url, notes, description, extraData)
      const payload = response.data as any
      const newBookmark = payload.bookmark || payload

      // Optimistic update: prepend new bookmark to the list
      set((state) => ({
        bookmarks: [newBookmark, ...state.bookmarks],
        total: state.total + 1,
        totalCount: state.totalCount + 1,
      }))

      // Start polling if new bookmark is pending/processing
      const hasPendingOrProcessing = newBookmark.enrichment_status === 'pending' ||
        newBookmark.enrichment_status === 'processing' ||
        newBookmark.archive_status === 'pending' ||
        newBookmark.archive_status === 'processing'
      if (hasPendingOrProcessing) {
        get().startPolling(get().lastParams || {})
      }

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
        totalCount: state.totalCount - 1,
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
      get().startPolling(get().lastParams || {})
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

      const hasPendingOrProcessing = updated.enrichment_status === 'pending' ||
        updated.enrichment_status === 'processing' ||
        updated.archive_status === 'pending' ||
        updated.archive_status === 'processing'
      if (hasPendingOrProcessing) {
        get().startPolling(get().lastParams || {})
      }
    } catch (error: unknown) {
      set({
        error: error instanceof Error ? error.message : 'Failed to update bookmark',
      })
    }
  },
}))
