import { useState, useEffect, useCallback } from 'react'
import { statsApi, bookmarksApi, Bookmark } from '../lib/api'
import BookmarkCard from '../components/BookmarkCard'
import BookmarkRow from '../components/BookmarkRow'
import FolderCard from '../components/FolderCard'
import MasonryGrid from '../components/MasonryGrid'
import { useUIStore, BookmarkViewMode } from '../stores/uiStore'
import { useBookmarksStore } from '../stores/bookmarksStore'
import { X, Folder as FolderIcon, BookMarked, Plus, FolderPlus } from 'lucide-react'
import { useFolderStore } from '../stores/folderStore'
import TopicsBox from '../components/TopicsBox'

export default function Dashboard() {
  const [topTags, setTopTags] = useState<{ tag: string; count: number }[]>([])
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [isLoadingTags, setIsLoadingTags] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const [isCreatingFolderInline, setIsCreatingFolderInline] = useState(false)
  const [newFolderInlineName, setNewFolderInlineName] = useState('')
  const [isFolderSubmitting, setIsFolderSubmitting] = useState(false)

  const { bookmarksViewMode: viewMode, setBookmarksViewMode: setViewMode, openAddModal } = useUIStore()
  const {
    bookmarks,
    total,
    totalCount,
    isLoading,
    fetchBookmarks,
    fetchTotalCount,
    updateBookmark
  } = useBookmarksStore()

  const { selectedFolderId, folders, setSelectedFolderId, fetchFolders, createFolder } = useFolderStore()

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

  const handleCreateFolderInline = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newFolderInlineName.trim()) return
    setIsFolderSubmitting(true)
    try {
      await createFolder(newFolderInlineName.trim())
      setNewFolderInlineName('')
      setIsCreatingFolderInline(false)
      fetchFolders()
    } catch (err) {
      console.error(err)
    } finally {
      setIsFolderSubmitting(false)
    }
  }

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
          <button onClick={clearFilters} className="text-xs font-medium text-slate-700 hover:text-slate-900 hover:underline flex items-center gap-1 dark:text-slate-350 dark:hover:text-slate-200">
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
            className="text-slate-500 transition-colors hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
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
                className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition-all ${viewMode === 'folders' ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100'}`}
                title="Folders view"
              >
                <FolderIcon className="h-3.5 w-3.5" />
                <span>Folders</span>
              </button>
            )}
            <button
              onClick={() => setViewMode('cards')}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition-all ${viewMode === 'cards' || (isInsideFolder && viewMode !== 'list') ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100'}`}
              title="Grid view"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
              <span>Grid</span>
            </button>
            <button
              onClick={() => setViewMode('list' as BookmarkViewMode)}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition-all ${viewMode === 'list' ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100'}`}
              title="List view"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
              <span>List</span>
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
              <div className="max-w-2xl mx-auto rounded-card bg-surface-light px-8 py-10 shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 text-center space-y-6">
                <div className="mx-auto w-16 h-16 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-700 dark:text-slate-300">
                  <BookMarked className="w-8 h-8" />
                </div>
                <div className="space-y-2">
                  <h2 className="font-display text-2xl font-normal text-slate-950 dark:text-slate-50">Let's build your library</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md mx-auto leading-relaxed">
                    Markly is a clean, minimal workspace for the articles and links you want to keep. Save links, organize them in folders, and read clean reader-view copies.
                  </p>
                </div>

                {isCreatingFolderInline ? (
                  <form onSubmit={handleCreateFolderInline} className="flex max-w-sm mx-auto gap-2">
                    <input
                      type="text"
                      placeholder="Folder name..."
                      value={newFolderInlineName}
                      onChange={(e) => setNewFolderInlineName(e.target.value)}
                      className="flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                      autoFocus
                      disabled={isFolderSubmitting}
                    />
                    <button
                      type="submit"
                      disabled={isFolderSubmitting || !newFolderInlineName.trim()}
                      className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white disabled:opacity-50"
                    >
                      {isFolderSubmitting ? 'Creating...' : 'Create'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsCreatingFolderInline(false)}
                      className="rounded-xl bg-slate-100 px-3 py-2 text-sm text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-400"
                    >
                      Cancel
                    </button>
                  </form>
                ) : (
                  <div className="pt-2 flex flex-col sm:flex-row justify-center gap-3">
                    <button
                      onClick={() => openAddModal()}
                      className="inline-flex items-center justify-center gap-2 rounded-full bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
                    >
                      <Plus className="h-4 w-4" />
                      Save your first link
                    </button>
                    <button
                      onClick={() => setIsCreatingFolderInline(true)}
                      className="inline-flex items-center justify-center gap-2 rounded-full bg-white px-5 py-2.5 text-sm font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700 dark:hover:bg-slate-700"
                    >
                      <FolderPlus className="h-4 w-4" />
                      Create a folder
                    </button>
                  </div>
                )}
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
        (() => {
          if (selectedTags.length > 0) {
            return (
              <div className="max-w-md mx-auto rounded-card bg-surface-light px-6 py-10 shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 text-center space-y-4">
                <div className="mx-auto w-12 h-12 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400">
                  <BookMarked className="w-6 h-6" />
                </div>
                <div className="space-y-1">
                  <h3 className="font-display text-lg font-medium text-slate-950 dark:text-slate-50">No matches found</h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    No bookmarks in this view match the selected topics.
                  </p>
                </div>
                <button
                  onClick={clearFilters}
                  className="inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
                >
                  Clear filters
                </button>
              </div>
            )
          }

          if (selectedFolderId) {
            const folderName = folders.find(f => f.id === selectedFolderId)?.name || 'this folder'
            return (
              <div className="max-w-md mx-auto rounded-card bg-surface-light px-6 py-10 shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 text-center space-y-4">
                <div className="mx-auto w-12 h-12 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400">
                  <FolderIcon className="w-6 h-6" />
                </div>
                <div className="space-y-1">
                  <h3 className="font-display text-lg font-medium text-slate-950 dark:text-slate-50">Empty folder</h3>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    Save links directly to <strong>{folderName}</strong> to organize your library.
                  </p>
                </div>
                <div className="flex flex-col items-center justify-center gap-2 sm:flex-row">
                  <button
                    onClick={() => {
                      setSelectedFolderId(selectedFolderId)
                      openAddModal()
                    }}
                    className="inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Add link to folder
                  </button>
                  <button
                    onClick={() => {
                      setSelectedFolderId(null)
                      setViewMode('folders')
                    }}
                    className="inline-flex items-center gap-1.5 rounded-full bg-white px-4 py-2 text-xs font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700 dark:hover:bg-slate-700"
                  >
                    Go back to Everything
                  </button>
                </div>
              </div>
            )
          }

          return (
            <div className="max-w-md mx-auto rounded-card bg-surface-light px-6 py-10 shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 text-center space-y-4">
              <div className="mx-auto w-12 h-12 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400">
                <BookMarked className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="font-display text-lg font-medium text-slate-950 dark:text-slate-50">No bookmarks yet</h3>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Add bookmarks to build your library.
                </p>
              </div>
              <button
                onClick={() => openAddModal()}
                className="inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
              >
                <Plus className="w-3.5 h-3.5" />
                Add bookmark
              </button>
            </div>
          )
        })()
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

