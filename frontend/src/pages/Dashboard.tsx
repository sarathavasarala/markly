import { useEffect, useState, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { 
  BookMarked, 
  Loader2,
  Sparkles
} from 'lucide-react'
import { statsApi, Bookmark, ResurfaceSuggestion } from '../lib/api'
import BookmarkCard from '../components/BookmarkCard'

export default function Dashboard() {
  const [recentBookmarks, setRecentBookmarks] = useState<Bookmark[]>([])
  const [resurfaceItems, setResurfaceItems] = useState<ResurfaceSuggestion[]>([])
  const [topDomains, setTopDomains] = useState<{domain: string; count: number}[]>([])
  const [topTags, setTopTags] = useState<{tag: string; count: number}[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showAllTags, setShowAllTags] = useState(false)
  
  // Use ref to track enriching state without causing re-renders
  const enrichingCountRef = useRef(0)
  const pollingRef = useRef<NodeJS.Timeout | null>(null)

  const loadDashboard = useCallback(async (showLoader = true) => {
    if (showLoader) setIsLoading(true)
    try {
      const [recentRes, domainsRes, tagsRes, resurfaceRes] = await Promise.all([
        statsApi.getRecent(20),
        statsApi.getTopDomains(5),
        statsApi.getTopTags(10),
        statsApi.getResurface().catch(() => ({ data: { suggestions: [] } })),
      ])

      const bookmarks = recentRes.data.bookmarks
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
          loadDashboard(false) // Don't show loader on poll
        }, 5000)
      }
      
      enrichingCountRef.current = enrichingCount
      
      setTopDomains(domainsRes.data.domains)
      setTopTags(tagsRes.data.tags)
      setResurfaceItems(resurfaceRes.data.suggestions)
    } catch (error) {
      console.error('Failed to load dashboard:', error)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDashboard()
    
    // Cleanup polling on unmount
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
      }
    }
  }, [loadDashboard])

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
            Your bookmarks ({recentBookmarks.length})
          </h1>
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
          <div className="flex flex-wrap gap-2">
            {(showAllTags ? topTags : topTags.slice(0, 8)).map(({ tag, count }) => (
              <Link
                key={tag}
                to={`/search?mode=keyword&tag=${encodeURIComponent(tag)}&q=${encodeURIComponent(tag)}`}
                className="inline-flex items-center gap-1 px-3 py-1.5 bg-gray-100 dark:bg-gray-700 rounded-full text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              >
                <span>{tag}</span>
                <span className="text-xs text-gray-500">({count})</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Main Content - Bookmarks */}
      <div className="space-y-6">
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
          <div className="columns-1 sm:columns-2 xl:columns-3 2xl:columns-4 gap-4 space-y-4">
            {recentBookmarks.map((bookmark) => (
              <div key={bookmark.id} className="mb-4 break-inside-avoid">
                <BookmarkCard
                  bookmark={bookmark}
                  onDeleted={(id) => setRecentBookmarks((prev) => prev.filter((b) => b.id !== id))}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
