import { useEffect, useState, useRef, useCallback } from 'react'
import {
  BookMarked,
  Loader2,
  Sparkles,
  LayoutGrid,
  List,
  Trash2
} from 'lucide-react'
import { statsApi, bookmarksApi, Bookmark, ResurfaceSuggestion } from '../lib/api'
import BookmarkCard from '../components/BookmarkCard'
import { useUIStore } from '../stores/uiStore'
import { useBookmarksStore } from '../stores/bookmarksStore'
import { X } from 'lucide-react'

export default function Dashboard() {
  const [recentBookmarks, setRecentBookmarks] = useState<Bookmark[]>([])
  const [resurfaceItems, setResurfaceItems] = useState<ResurfaceSuggestion[]>([])
  const [topTags, setTopTags] = useState<{ tag: string; count: number }[]>([])
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isFiltering, setIsFiltering] = useState(false)
  const [showAllTags, setShowAllTags] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const { bookmarksViewMode: viewMode, setBookmarksViewMode: setViewMode } = useUIStore()
  const { trackAccess, deleteBookmark } = useBookmarksStore()

  // Use ref to track enriching state without causing re-renders
  const enrichingCountRef = useRef(0)
  const pollingRef = useRef<NodeJS.Timeout | null>(null)

  const loadDashboardData = useCallback(async () => {
    setIsLoading(true)
    try {
      const [tagsRes, resurfaceRes] = await Promise.all([
        statsApi.getTopTags(20),
        statsApi.getResurface().catch(() => ({ data: { suggestions: [] } })),
      ])
      setTopTags(tagsRes.data.tags)
      setResurfaceItems(resurfaceRes.data.suggestions)
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const loadBookmarks = useCallback(async (tags: string[] = [], showLoader = false) => {
    if (showLoader) setIsFiltering(true)
    try {
      const res = await bookmarksApi.list({
        tag: tags.length > 0 ? tags : undefined,
        per_page: 40,
      })

      const bookmarks = res.data.bookmarks
      setRecentBookmarks(bookmarks)

      // Track how many are still enriching
      const enrichingCount = bookmarks.filter(
        (b: Bookmark) => b.enrichment_status === 'pending' || b.enrichment_status === 'processing'
      ).length

      // If we had enriching bookmarks and now we don't, stop polling
      if (enrichingCountRef.current > 0 && enrichingCount === 0) {
        if (pollingRef.current) {
          clearInterval(pollingRef.current)
          pollingRef.current = null
        }
      }

      // If we have enriching bookmarks, start polling (if not already)
      if (enrichingCount > 0 && !pollingRef.current) {
        pollingRef.current = setInterval(() => {
          loadBookmarks(tags, false)
        }, 5000)
      }

      enrichingCountRef.current = enrichingCount
    } catch (error) {
      console.error('Failed to load bookmarks:', error)
    } finally {
      setIsFiltering(false)
    }
  }, [])

  useEffect(() => {
    loadDashboardData()
  }, [loadDashboardData])

  useEffect(() => {
    loadBookmarks(selectedTags, true)

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
        pollingRef.current = null
      }
    }
  }, [selectedTags, loadBookmarks])

  const toggleTag = (tag: string) => {
    setSelectedTags(prev =>
      prev.includes(tag)
        ? prev.filter(t => t !== tag)
        : [...prev, tag]
    )
  }

  const clearFilters = () => {
    setSelectedTags([])
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3 mt-[-6px]">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
            {selectedTags.length > 0 ? (
              <span className="flex items-center gap-2">
                Filtered results ({recentBookmarks.length})
                <button
                  onClick={clearFilters}
                  className="text-xs font-normal text-primary-600 hover:underline flex items-center gap-1"
                >
                  Clear filters <X className="w-3 h-3" />
                </button>
              </span>
            ) : (
              `Your bookmarks (${recentBookmarks.length})`
            )}
          </h1>
        </div>

        <div className="inline-flex rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <button
            type="button"
            onClick={() => setViewMode('cards')}
            className={`flex items-center gap-1 px-3 py-2 text-sm ${viewMode === 'cards'
              ? 'bg-primary-600 text-white'
              : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
              }`}
          >
            <LayoutGrid className="w-4 h-4" /> Cards
          </button>
          <button
            type="button"
            onClick={() => setViewMode('list')}
            className={`flex items-center gap-1 px-3 py-2 text-sm ${viewMode === 'list'
              ? 'bg-primary-600 text-white'
              : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
              }`}
          >
            <List className="w-4 h-4" /> List
          </button>
        </div>
      </div>

      {/* Topics row */}
      {topTags.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between gap-2 mb-3">
            <h2 className="text-sm font-medium text-gray-700 dark:text-gray-200">Topics</h2>
            <button
              type="button"
              onClick={() => setShowAllTags((v) => !v)}
              className="text-xs text-primary-600 dark:text-primary-400 hover:underline"
            >
              {showAllTags ? 'Show less' : 'View more'}
            </button>
          </div>
          <div className={`flex flex-wrap gap-2 transition-all duration-300 ${showAllTags ? 'max-h-[1000px]' : 'max-h-9 overflow-hidden'}`}>
            {topTags.map(({ tag, count }) => {
              const isSelected = selectedTags.includes(tag)
              return (
                <button
                  key={tag}
                  type="button"
                  onClick={() => toggleTag(tag)}
                  className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm transition-all ${isSelected
                    ? 'bg-primary-600 text-white shadow-sm ring-2 ring-primary-500 ring-offset-1 dark:ring-offset-gray-800'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600'
                    }`}
                >
                  <span>{tag}</span>
                  <span className={`text-xs ${isSelected ? 'text-primary-100' : 'text-gray-500'}`}>
                    ({count})
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Main Content - Bookmarks */}
      <div className={`space-y-6 transition-opacity duration-200 ${isFiltering ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
        {/* Resurface */}
        {resurfaceItems.length > 0 && (
          <section className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="w-4 h-4 text-amber-500" />
              <h2 className="text-sm font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                Rediscover
              </h2>
            </div>

            <div className="flex gap-3 overflow-x-auto pb-2">
              {resurfaceItems.map((item) => (
                <a
                  key={item.id}
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-shrink-0 w-64 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3 hover:shadow-md transition-shadow"
                >
                  <p className="font-medium text-gray-900 dark:text-white text-sm line-clamp-1">
                    {item.clean_title || item.url}
                  </p>
                  <p className="text-xs text-amber-600 dark:text-amber-400 mt-1 line-clamp-2">
                    {item.resurface_reason}
                  </p>
                </a>
              ))}
            </div>
          </section>
        )}

        {/* Bookmarks Grid */}
        {recentBookmarks.length === 0 ? (
          <div className="bg-white dark:bg-gray-800 rounded-xl p-12 text-center">
            <BookMarked className="w-16 h-16 mx-auto text-gray-300 dark:text-gray-600 mb-4" />
            <h2 className="text-xl font-medium text-gray-900 dark:text-white mb-2">
              No bookmarks yet
            </h2>
            <p className="text-gray-500 dark:text-gray-400">
              Paste a link in the bar above to save your first bookmark
            </p>
          </div>
        ) : (
          viewMode === 'cards' ? (
            <div className="columns-1 sm:columns-2 xl:columns-3 2xl:columns-4 gap-4 space-y-4">
              {recentBookmarks.map((bookmark) => (
                <div key={bookmark.id} className="mb-4 break-inside-avoid">
                  <BookmarkCard
                    bookmark={bookmark}
                    onDeleted={(id) => setRecentBookmarks((prev) => prev.filter((b) => b.id !== id))}
                    onTagClick={toggleTag}
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
              <div className="grid grid-cols-12 px-4 py-2 text-xs font-semibold text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                <div className="col-span-6">Title</div>
                <div className="col-span-4">Site</div>
                <div className="col-span-1 text-right">Added</div>
                <div className="col-span-1 text-right">Actions</div>
              </div>
              <div className="divide-y divide-gray-200 dark:divide-gray-700">
                {recentBookmarks.map((bookmark) => {
                  const title = bookmark.clean_title || bookmark.original_title || bookmark.url
                  const createdAt = bookmark.created_at ? new Date(bookmark.created_at) : null
                  const createdAtLabel = createdAt && !Number.isNaN(createdAt.getTime())
                    ? createdAt.toLocaleDateString()
                    : '—'

                  return (
                    <div
                      key={bookmark.id}
                      className="grid grid-cols-12 px-4 py-3 text-sm items-center hover:bg-gray-50 dark:hover:bg-gray-750"
                    >
                      <div className="col-span-6 pr-3 min-w-0">
                        <a
                          href={bookmark.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={() => trackAccess(bookmark.id)}
                          className="text-gray-900 dark:text-white font-medium hover:text-primary-600 dark:hover:text-primary-400 truncate block"
                          title={title}
                        >
                          {title}
                        </a>
                        <div className="text-xs text-gray-500 dark:text-gray-400 truncate">{bookmark.url}</div>
                      </div>
                      <div className="col-span-4 text-gray-700 dark:text-gray-300 truncate">
                        {bookmark.domain}
                      </div>
                      <div className="col-span-1 text-right text-xs text-gray-500 dark:text-gray-400">
                        {createdAtLabel}
                      </div>
                      <div className="col-span-1 text-right">
                        <button
                          type="button"
                          onClick={async () => {
                            if (deletingId) return
                            if (!window.confirm('Delete this bookmark?')) return
                            try {
                              setDeletingId(bookmark.id)
                              await deleteBookmark(bookmark.id)
                              setRecentBookmarks((prev) => prev.filter((b) => b.id !== bookmark.id))
                            } finally {
                              setDeletingId(null)
                            }
                          }}
                          className="inline-flex items-center justify-center p-2 text-gray-400 hover:text-red-600 dark:hover:text-red-400"
                          aria-label="Delete bookmark"
                          disabled={deletingId === bookmark.id}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        )}
      </div>
    </div>
  )
}
