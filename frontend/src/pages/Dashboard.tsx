import { useState, useEffect, useCallback, useRef } from 'react'
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
  const [recentBookmarks, setRecentBookmarks] = useState<Bookmark[]>([])
  const [topTags, setTopTags] = useState<{ tag: string; count: number }[]>([])
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [isFiltering, setIsFiltering] = useState(false)
  const [isLoadingTags, setIsLoadingTags] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const { bookmarksViewMode: viewMode, setBookmarksViewMode: setViewMode } = useUIStore()
  const { updateBookmark, bookmarks: storeBookmarks } = useBookmarksStore()
  const { selectedFolderId, folders, setSelectedFolderId, fetchFolders } = useFolderStore()

  // Unfiled bookmarks for folders view
  const [unfiledBookmarks, setUnfiledBookmarks] = useState<Bookmark[]>([])
  const [isLoadingUnfiled, setIsLoadingUnfiled] = useState(false)
  // All tag-filtered bookmarks for computing folder match counts
  const [tagFilteredBookmarks, setTagFilteredBookmarks] = useState<Bookmark[]>([])

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

  // Load unfiled bookmarks when in folders view
  useEffect(() => {
    if (viewMode === 'folders') {
      setIsLoadingUnfiled(true)

      // If tags are selected, fetch all bookmarks with those tags to compute folder counts
      if (selectedTags.length > 0) {
        bookmarksApi.list({ tag: selectedTags, per_page: 100 })
          .then(res => {
            setTagFilteredBookmarks(res.data.bookmarks)
            // Filter for unfiled only
            setUnfiledBookmarks(res.data.bookmarks.filter(b => !b.folder_id))
          })
          .catch(err => console.error('Failed to load filtered bookmarks:', err))
          .finally(() => setIsLoadingUnfiled(false))
      } else {
        // No tags selected, just load unfiled bookmarks
        setTagFilteredBookmarks([])
        bookmarksApi.list({ folder_id: 'unfiled', per_page: 40 })
          .then(res => setUnfiledBookmarks(res.data.bookmarks))
          .catch(err => console.error('Failed to load unfiled bookmarks:', err))
          .finally(() => setIsLoadingUnfiled(false))
      }
      // Refresh folders to get updated counts
      fetchFolders()
    }
  }, [viewMode, fetchFolders, selectedTags])

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
    loadTopTags()
  }, [loadTopTags])

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

    // Determine if we're inside a folder (not in folders view, but with a folder selected)
    const isInsideFolder = currentFolder && viewMode !== 'folders'

    let titleContent: React.ReactNode = (
      <span className="flex items-center gap-1">Your bookmarks ({countDisplay})</span>
    )

    if (viewMode === 'folders') {
      // Calculate total bookmark count for folders view: folder bookmarks + unfiled
      const folderBookmarkCount = folders.reduce((sum, f) => sum + (f.bookmark_count || 0), 0)
      const totalCount = isFiltering ? (
        <span className="inline-block w-6 h-5 bg-gray-200 dark:bg-gray-700 rounded animate-pulse align-middle" />
      ) : (
        folderBookmarkCount + unfiledBookmarks.length
      )
      titleContent = (
        <span className="flex items-center gap-1">Your bookmarks ({totalCount})</span>
      )
    } else if (selectedTags.length > 0) {
      titleContent = (
        <span className="flex items-center gap-2">
          Filtered results ({countDisplay})
          <button onClick={clearFilters} className="text-xs font-normal text-primary-600 hover:underline flex items-center gap-1">
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
            className="text-primary-600 hover:text-primary-700 hover:underline transition-colors"
          >
            Your bookmarks
          </button>
          <span className="text-gray-400 dark:text-gray-500">›</span>
          <span>{currentFolder.name}</span>
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
            {/* Only show Folders toggle when NOT inside a folder */}
            {!isInsideFolder && (
              <button
                onClick={() => setViewMode('folders' as BookmarkViewMode)}
                className={`p-1.5 rounded-md transition-all ${viewMode === 'folders' ? 'bg-white dark:bg-gray-700 shadow-sm text-primary-600 dark:text-primary-400' : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'}`}
                title="Folders view"
              >
                <FolderIcon className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={() => setViewMode('cards')}
              className={`p-1.5 rounded-md transition-all ${viewMode === 'cards' || (isInsideFolder && viewMode !== 'list') ? 'bg-white dark:bg-gray-700 shadow-sm text-primary-600 dark:text-primary-400' : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'}`}
              title="Grid view"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
            </button>
            <button
              onClick={() => setViewMode('list' as BookmarkViewMode)}
              className={`p-1.5 rounded-md transition-all ${viewMode === 'list' ? 'bg-white dark:bg-gray-700 shadow-sm text-primary-600 dark:text-primary-400' : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'}`}
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

      <TopicsBox
        tags={topTags}
        selectedTags={selectedTags}
        isLoading={isLoadingTags}
        onTagClick={toggleTag}
        onClearFilters={clearFilters}
      />

      {isFiltering || (viewMode === 'folders' && isLoadingUnfiled) ? (
        <MasonryGrid
          items={[1, 2, 3, 4]}
          renderItem={() => <div className="h-64 bg-gray-100 dark:bg-gray-800 rounded-2xl animate-pulse" />}
        />
      ) : viewMode === 'folders' ? (
        (() => {
          // Compute folder match counts from tag-filtered bookmarks
          const folderMatchCounts = new Map<string, number>()
          if (selectedTags.length > 0) {
            tagFilteredBookmarks.forEach(b => {
              if (b.folder_id) {
                folderMatchCounts.set(b.folder_id, (folderMatchCounts.get(b.folder_id) || 0) + 1)
              }
            })
          }

          // When filtering, only show folders that have matches
          const foldersToShow = selectedTags.length > 0
            ? folders.filter(f => folderMatchCounts.has(f.id))
            : folders

          const items = [
            ...foldersToShow.map(f => ({
              type: 'folder' as const,
              data: f,
              matchCount: selectedTags.length > 0 ? folderMatchCounts.get(f.id) : undefined
            })),
            ...unfiledBookmarks.map(b => ({ type: 'bookmark' as const, data: b, matchCount: undefined }))
          ]

          if (items.length === 0) {
            return (
              <div className="text-center py-20 bg-gray-50 dark:bg-gray-800/50 rounded-2xl border-2 border-dashed border-gray-200 dark:border-gray-800">
                <p className="text-gray-500">
                  {selectedTags.length > 0
                    ? 'No bookmarks match the selected tags.'
                    : 'No folders or bookmarks yet. Create a folder from the sidebar.'}
                </p>
              </div>
            )
          }

          return (
            <MasonryGrid
              items={items}
              renderItem={(item) => {
                if (item.type === 'folder') {
                  return (
                    <FolderCard
                      folder={item.data}
                      matchCount={item.matchCount}
                      onClick={() => {
                        setSelectedFolderId(item.data.id)
                        setViewMode('cards')
                      }}
                    />
                  )
                } else {
                  return (
                    <BookmarkCard
                      bookmark={item.data}
                      onDeleted={() => handleBookmarkDeleted(item.data.id)}
                      onTagClick={toggleTag}
                      onVisibilityToggle={() => toggleVisibility(item.data)}
                    />
                  )
                }
              }}
            />
          )
        })()
      ) : recentBookmarks.length === 0 ? (
        <div className="text-center py-20 bg-gray-50 dark:bg-gray-800/50 rounded-2xl border-2 border-dashed border-gray-200 dark:border-gray-800">
          <p className="text-gray-500">No bookmarks found here yet.</p>
        </div>
      ) : viewMode === 'cards' ? (
        <MasonryGrid
          items={recentBookmarks}
          renderItem={(bookmark) => (
            <BookmarkCard
              bookmark={bookmark}
              onDeleted={() => handleBookmarkDeleted(bookmark.id)}
              onTagClick={toggleTag}
              onVisibilityToggle={() => toggleVisibility(bookmark)}
            />
          )}
        />
      ) : (
        <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800 overflow-hidden">
          {recentBookmarks.map(bookmark => (
            <BookmarkRow
              key={bookmark.id}
              bookmark={bookmark}
              onDeleted={() => handleBookmarkDeleted(bookmark.id)}
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

