import { useState, useEffect, useCallback } from 'react'
import { statsApi, bookmarksApi, Bookmark } from '../lib/api'
import BookmarkCard from '../components/BookmarkCard'
import BookmarkRow from '../components/BookmarkRow'
import FolderCard from '../components/FolderCard'
import MasonryGrid from '../components/MasonryGrid'
import { useUIStore, BookmarkViewMode } from '../stores/uiStore'
import { useBookmarksStore } from '../stores/bookmarksStore'
import { X, Folder as FolderIcon } from 'lucide-react'
import { useFolderStore } from '../stores/folderStore'
import TopicsBox from '../components/TopicsBox'

export default function Dashboard() {
  const [topTags, setTopTags] = useState<{ tag: string; count: number }[]>([])
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [isLoadingTags, setIsLoadingTags] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const { bookmarksViewMode: viewMode, setBookmarksViewMode: setViewMode } = useUIStore()
  const {
    bookmarks,
    total,
    totalCount,
    isLoading,
    fetchBookmarks,
    fetchTotalCount,
    updateBookmark
  } = useBookmarksStore()

  const { selectedFolderId, folders, setSelectedFolderId, fetchFolders } = useFolderStore()

  const currentFolder = selectedFolderId
    ? folders.find(f => f.id === selectedFolderId)
    : null

  const loadTopTags = useCallback(async () => {
    setIsLoadingTags(true)
    try {
      const tagsRes = await statsApi.getTopTags(20, selectedFolderId)
      setTopTags(tagsRes.data.tags)
    } catch (error) {
      console.error('Failed to load tags:', error)
    } finally {
      setIsLoadingTags(false)
    }
  }, [selectedFolderId])

  useEffect(() => {
    loadTopTags()
  }, [loadTopTags, selectedFolderId])

  // Initial load of total count and folders
  useEffect(() => {
    fetchTotalCount()
    fetchFolders()
  }, [fetchTotalCount, fetchFolders])

  // Centralized bookmark loading
  useEffect(() => {
    const params: Parameters<typeof bookmarksApi.list>[0] = {
      tag: selectedTags.length > 0 ? selectedTags : undefined,
      per_page: 40,
    }

    if (viewMode === 'folders' && !selectedFolderId) {
      // In folders view, we want to show 'unfiled' bookmarks in the list below folders
      params.folder_id = 'unfiled'
    } else if (selectedFolderId) {
      params.folder_id = selectedFolderId
    }

    fetchBookmarks(params)
  }, [selectedTags, selectedFolderId, viewMode, fetchBookmarks])

  const toggleTag = useCallback<(tag: string) => void>((tag: string) => {
    setSelectedTags(prev =>
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    )
  }, [])

  const clearFilters = useCallback<() => void>(() => {
    setSelectedTags([])
  }, [])

  const handleBookmarkDeleted = useCallback(() => {
    loadTopTags()
    fetchTotalCount()
  }, [loadTopTags, fetchTotalCount])

  const toggleVisibility = useCallback(async (bookmark: Bookmark) => {
    try {
      await updateBookmark(bookmark.id, { is_public: !bookmark.is_public })
    } catch (err) {
      console.error(err)
    }
  }, [updateBookmark])

  const renderHeader = () => {
    // Show skeleton count during loading to prevent stale data flash
    const countDisplay = isLoading ? (
      <span className="inline-block w-6 h-5 bg-slate-200/70 dark:bg-slate-800/70 rounded animate-pulse align-middle" />
    ) : (
      total
    )

    // Determine if we're inside a folder (not in folders view, but with a folder selected)
    const isInsideFolder = currentFolder && viewMode !== 'folders'

    let titleContent: React.ReactNode = (
      <span className="flex items-center gap-1">Your bookmarks ({isLoading ? <span className="inline-block w-6 h-5 bg-slate-200/70 dark:bg-slate-800/70 rounded animate-pulse align-middle" /> : totalCount})</span>
    )

    if (viewMode === 'folders') {
      titleContent = (
        <span className="flex items-center gap-1">Your bookmarks ({isLoading ? <span className="inline-block w-6 h-5 bg-slate-200/70 dark:bg-slate-800/70 rounded animate-pulse align-middle" /> : totalCount})</span>
      )
    } else if (selectedTags.length > 0) {
      titleContent = (
        <span className="flex items-center gap-2">
          Filtered results ({countDisplay})
          <button onClick={clearFilters} className="text-xs font-medium text-indigo-700 hover:underline flex items-center gap-1 dark:text-indigo-300">
            Clear filters <X className="w-3 h-3" />
          </button>
        </span>
      )
    } else if (isInsideFolder) {
      // Breadcrumb navigation when inside a folder
      titleContent = (
        <span className="flex items-center gap-2">
          <button
            onClick={() => {
              setSelectedFolderId(null)
              setViewMode('folders')
            }}
            className="text-slate-500 transition-colors hover:text-indigo-700 dark:text-slate-400 dark:hover:text-indigo-300"
          >
            Your bookmarks
          </button>
          <span className="text-slate-400 dark:text-slate-500">›</span>
          <span>{currentFolder.name}</span>
        </span>
      )
    }

    return (
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-2xl font-normal text-slate-950 sm:text-3xl dark:text-slate-50">
          {titleContent}
        </h1>
        <div className="flex items-center gap-2">
          <div className="flex rounded-full border border-slate-200 bg-white p-1 dark:border-slate-700 dark:bg-slate-900">
            {!isInsideFolder && (
              <button
                onClick={() => setViewMode('folders' as BookmarkViewMode)}
                className={`rounded-full p-1.5 transition-all ${viewMode === 'folders' ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-950' : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100'}`}
                title="Folders view"
              >
                <FolderIcon className="h-4 w-4" />
              </button>
            )}
            <button
              onClick={() => setViewMode('cards')}
              className={`rounded-full p-1.5 transition-all ${viewMode === 'cards' || (isInsideFolder && viewMode !== 'list') ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-950' : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100'}`}
              title="Grid view"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
            </button>
            <button
              onClick={() => setViewMode('list' as BookmarkViewMode)}
              className={`rounded-full p-1.5 transition-all ${viewMode === 'list' ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-950' : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100'}`}
              title="List view"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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

      <TopicsBox
        tags={topTags}
        selectedTags={selectedTags}
        isLoading={isLoadingTags}
        onTagClick={toggleTag}
        onClearFilters={clearFilters}
      />

      {isLoading && bookmarks.length === 0 ? (
        <MasonryGrid
          items={[1, 2, 3, 4]}
          renderItem={() => <div className="h-64 rounded-card bg-slate-200/70 animate-pulse dark:bg-slate-800/70" />}
        />
      ) : viewMode === 'folders' && !selectedFolderId ? (
        (() => {
          if (folders.length === 0 && bookmarks.length === 0) {
            return (
              <div className="text-center py-20 rounded-card border border-dashed border-slate-300 bg-white/40 dark:border-slate-700 dark:bg-slate-900/40">
                <p className="text-slate-500 dark:text-slate-400">
                  No folders or bookmarks yet. Create a folder from the sidebar.
                </p>
              </div>
            )
          }

          return (
            <div className="space-y-6">
              {folders.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                  {folders.map(f => (
                    <FolderCard
                      key={f.id}
                      folder={f}
                      onClick={() => {
                        setSelectedFolderId(f.id)
                        setViewMode('cards')
                      }}
                    />
                  ))}
                </div>
              )}
              {bookmarks.length > 0 && (
                <MasonryGrid
                  items={bookmarks}
                  renderItem={(b: Bookmark) => (
                    <BookmarkCard
                      key={b.id}
                      bookmark={b}
                      onDeleted={handleBookmarkDeleted}
                      onTagClick={toggleTag}
                      onVisibilityToggle={() => toggleVisibility(b)}
                    />
                  )}
                />
              )}
            </div>
          )
        })()
      ) : bookmarks.length === 0 ? (
        <div className="rounded-card border border-dashed border-slate-300 bg-white/40 py-20 text-center dark:border-slate-700 dark:bg-slate-900/40">
          <p className="text-slate-500 dark:text-slate-400">No bookmarks found here yet.</p>
        </div>
      ) : viewMode === 'cards' ? (
        <MasonryGrid
          items={bookmarks}
          renderItem={(bookmark: Bookmark) => (
            <BookmarkCard
              bookmark={bookmark}
              onDeleted={handleBookmarkDeleted}
              onTagClick={toggleTag}
              onVisibilityToggle={() => toggleVisibility(bookmark)}
            />
          )}
        />
      ) : (
        <div className="overflow-hidden rounded-card bg-surface-light shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5">
          {bookmarks.map((bookmark: Bookmark) => (
            <BookmarkRow
              key={bookmark.id}
              bookmark={bookmark}
              onDeleted={handleBookmarkDeleted}
              onTagClick={toggleTag}
            />
          ))}
        </div>
      )}

      {/* Delete Modal Placeholder */}
      {deletingId && <div className="fixed inset-0 z-50 flex items-center justify-center p-4"><div className="absolute inset-0 bg-black/50" onClick={() => setDeletingId(null)} /></div>}
    </div>
  )
}

