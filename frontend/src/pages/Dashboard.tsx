import { useState, useEffect, useCallback, useRef } from 'react'
import { statsApi, bookmarksApi, Bookmark, ResurfaceSuggestion } from '../lib/api'
import BookmarkCard from '../components/BookmarkCard'
import BookmarkRow from '../components/BookmarkRow'
import { useUIStore, BookmarkViewMode } from '../stores/uiStore'
import { useBookmarksStore } from '../stores/bookmarksStore'
import { X, Folder as FolderIcon } from 'lucide-react'
import { useFolderStore } from '../stores/folderStore'

export default function Dashboard() {
  const [recentBookmarks, setRecentBookmarks] = useState<Bookmark[]>([])
  const [resurfaceItems, setResurfaceItems] = useState<ResurfaceSuggestion[]>([])
  const [topTags, setTopTags] = useState<{ tag: string; count: number }[]>([])
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [isFiltering, setIsFiltering] = useState(false)
  const [isLoadingTags, setIsLoadingTags] = useState(false)
  const [showAllTags, setShowAllTags] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const { bookmarksViewMode: viewMode, setBookmarksViewMode: setViewMode } = useUIStore()
  const { updateBookmark, bookmarks: storeBookmarks } = useBookmarksStore()
  const { selectedFolderId, folders } = useFolderStore()

  const currentFolder = selectedFolderId
    ? folders.find(f => f.id === selectedFolderId)
    : null

  const pollingRef = useRef<NodeJS.Timeout | null>(null)
  const enrichingCountRef = useRef(0)


  const loadBookmarks = useCallback(async (tags: string[] = [], showLoader = false) => {
    if (showLoader) setIsFiltering(true)
    try {
      const res = await bookmarksApi.list({
        tag: tags.length > 0 ? tags : undefined,
        folder_id: selectedFolderId || undefined,
        per_page: 40,
      })

      const bookmarks = res.data.bookmarks
      setRecentBookmarks(bookmarks)

      const enrichingCount = bookmarks.filter(
        (b: Bookmark) => b.enrichment_status === 'pending' || b.enrichment_status === 'processing'
      ).length

      if (enrichingCountRef.current > 0 && enrichingCount === 0) {
        if (pollingRef.current) {
          clearInterval(pollingRef.current)
          pollingRef.current = null
        }
      }

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
  }, [selectedFolderId])

  const loadDashboardData = useCallback(async () => {
    setIsLoadingTags(true)
    try {
      const [resurfaceRes, tagsRes] = await Promise.all([
        statsApi.getResurface(),
        statsApi.getTopTags(20, selectedFolderId)
      ])
      setResurfaceItems(resurfaceRes.data.suggestions)
      setTopTags(tagsRes.data.tags)
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
    } finally {
      setIsLoadingTags(false)
    }
  }, [selectedFolderId])

  useEffect(() => {
    loadDashboardData()
  }, [loadDashboardData, selectedFolderId])

  useEffect(() => {
    loadBookmarks(selectedTags, true)
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
        pollingRef.current = null
      }
    }
  }, [selectedTags, selectedFolderId, loadBookmarks])

  // Sync newly created bookmarks from store into local state (replaces page reload)
  useEffect(() => {
    if (storeBookmarks.length > 0) {
      setRecentBookmarks(prev => {
        const existingIds = new Set(prev.map(b => b.id))
        const newBookmarks = storeBookmarks.filter(b => !existingIds.has(b.id))
        if (newBookmarks.length > 0) {
          // Prepend new bookmarks to the list
          return [...newBookmarks, ...prev]
        }
        return prev
      })
    }
  }, [storeBookmarks])

  const toggleTag = useCallback<(tag: string) => void>((tag: string) => {
    setSelectedTags(prev =>
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    )
  }, [])

  const clearFilters = useCallback<() => void>(() => {
    setSelectedTags([])
  }, [])

  const handleBookmarkDeleted = useCallback<(id: string) => void>((id: string) => {
    setRecentBookmarks(prev => prev.filter(b => b.id !== id))
    setResurfaceItems(prev => prev.filter(b => b.id !== id))
    loadDashboardData()
  }, [loadDashboardData])

  const toggleVisibility = useCallback(async (bookmark: Bookmark) => {
    try {
      const newStatus = !bookmark.is_public
      await updateBookmark(bookmark.id, { is_public: newStatus })
      setRecentBookmarks(prev => prev.map(b => b.id === bookmark.id ? { ...b, is_public: newStatus } : b))
    } catch (err) {
      console.error(err)
    }
  }, [updateBookmark])

  if (!recentBookmarks) return null

  const renderHeader = () => {
    // Show skeleton count during loading to prevent stale data flash
    const countDisplay = isFiltering ? (
      <span className="inline-block w-6 h-5 bg-gray-200 dark:bg-gray-700 rounded animate-pulse align-middle" />
    ) : (
      recentBookmarks.length
    )

    let titleContent: React.ReactNode = (
      <span className="flex items-center gap-1">Your bookmarks ({countDisplay})</span>
    )

    if (selectedTags.length > 0) {
      titleContent = (
        <span className="flex items-center gap-2">
          Filtered results ({countDisplay})
          <button onClick={clearFilters} className="text-xs font-normal text-primary-600 hover:underline flex items-center gap-1">
            Clear filters <X className="w-3 h-3" />
          </button>
        </span>
      )
    } else if (currentFolder) {
      titleContent = (
        <span className="flex items-center gap-2">
          <FolderIcon className="w-5 h-5 text-primary-600" /> {currentFolder.name} ({countDisplay})
        </span>
      )
    }

    return (
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
          {titleContent}
        </h1>
        <div className="flex items-center gap-2">
          <div className="flex bg-gray-100 dark:bg-gray-800 p-1 rounded-lg">
            <button
              onClick={() => setViewMode('cards')}
              className={`p-1.5 rounded-md transition-all ${viewMode === 'cards' ? 'bg-white dark:bg-gray-700 shadow-sm text-primary-600' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}`}
              title="Grid view"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
            </button>
            <button
              onClick={() => setViewMode('list' as BookmarkViewMode)}
              className={`p-1.5 rounded-md transition-all ${viewMode === 'list' ? 'bg-white dark:bg-gray-700 shadow-sm text-primary-600' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}`}
              title="List view"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {renderHeader()}

      {/* Topics Box */}
      <div className="bg-white dark:bg-gray-900 p-6 rounded-2xl border border-gray-100 dark:border-gray-800 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold tracking-wider text-gray-400">Topics</h2>
          {!isLoadingTags && topTags.length > 8 && (
            <button onClick={() => setShowAllTags(!showAllTags)} className="text-xs font-medium text-primary-600 hover:text-primary-700">
              {showAllTags ? 'Show less' : `Show all ${topTags.length}`}
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {isLoadingTags ? (
            // Skeleton loader for topics
            [1, 2, 3, 4, 5, 6].map(i => (
              <div key={i} className="w-20 h-8 bg-gray-100 dark:bg-gray-800 rounded-full animate-pulse" />
            ))
          ) : topTags.length === 0 ? (
            <p className="text-sm text-gray-400">No topics yet</p>
          ) : (
            topTags.slice(0, showAllTags ? undefined : 8).map(({ tag, count }) => (
              <button
                key={tag}
                onClick={() => toggleTag(tag)}
                className={`px-3 py-1.5 rounded-full text-xs font-bold border transition-all ${selectedTags.includes(tag)
                  ? 'bg-primary-600 border-primary-600 text-white shadow-md'
                  : 'bg-primary-50 dark:bg-primary-900/10 border-primary-100 dark:border-primary-900/30 text-primary-700 dark:text-primary-400 hover:border-primary-300 dark:hover:border-primary-800'
                  }`}
              >
                #{tag} <span className={`ml-1 ${selectedTags.includes(tag) ? 'text-primary-200' : 'text-primary-400'}`}>{count}</span>
              </button>
            ))
          )}
        </div>
      </div>

      {isFiltering ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-6">
          {[1, 2, 3, 4].map(i => <div key={i} className="h-64 bg-gray-100 dark:bg-gray-800 rounded-2xl animate-pulse" />)}
        </div>
      ) : (
        <div className="space-y-8">
          {/* Spotlight section (only on default view) */}
          {resurfaceItems.length > 0 && selectedTags.length === 0 && !selectedFolderId && (
            <div className="space-y-4">
              <h2 className="text-sm font-bold uppercase tracking-wider text-gray-400 flex items-center gap-2">
                <span className="w-1.5 h-1.5 bg-primary-600 rounded-full animate-pulse" /> Resurfacing
              </h2>
              <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-6">
                {resurfaceItems.map(item => (
                  <div key={item.id}>
                    <BookmarkCard
                      bookmark={item}
                      onDeleted={() => handleBookmarkDeleted(item.id)}
                      onTagClick={toggleTag}
                      onVisibilityToggle={() => toggleVisibility(item)}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Main List */}
          <div className="space-y-4">
            {recentBookmarks.length === 0 ? (
              <div className="text-center py-20 bg-gray-50 dark:bg-gray-800/50 rounded-2xl border-2 border-dashed border-gray-200 dark:border-gray-800">
                <p className="text-gray-500">No bookmarks found here yet.</p>
              </div>
            ) : (
              <div className={viewMode === 'cards' ? "grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-6" : "bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800 overflow-hidden"}>
                {recentBookmarks.map(bookmark => (
                  <div key={bookmark.id}>
                    {viewMode === 'cards' ? (
                      <BookmarkCard
                        bookmark={bookmark}
                        onDeleted={() => handleBookmarkDeleted(bookmark.id)}
                        onTagClick={toggleTag}
                        onVisibilityToggle={() => toggleVisibility(bookmark)}
                      />
                    ) : (
                      <BookmarkRow
                        bookmark={bookmark}
                        onDeleted={() => handleBookmarkDeleted(bookmark.id)}
                        onTagClick={toggleTag}
                      />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Delete Modal Placeholder */}
      {deletingId && <div className="fixed inset-0 z-50 flex items-center justify-center p-4"><div className="absolute inset-0 bg-black/50" onClick={() => setDeletingId(null)} /></div>}
    </div>
  )
}
