import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Loader2, Filter, X, ChevronDown } from 'lucide-react'
import { useBookmarksStore } from '../stores/bookmarksStore'
import BookmarkCard from '../components/BookmarkCard'

export default function Bookmarks() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [showFilters, setShowFilters] = useState(false)
  
  const {
    bookmarks,
    total,
    page,
    pages,
    isLoading,
    filters,
    fetchBookmarks,
    setFilters,
    clearFilters,
  } = useBookmarksStore()

  // Load initial filters from URL
  useEffect(() => {
    const tag = searchParams.get('tag')
    const domain = searchParams.get('domain')
    const content_type = searchParams.get('content_type')
    
    if (tag || domain || content_type) {
      setFilters({ tag: tag || undefined, domain: domain || undefined, content_type: content_type || undefined })
    }
    
    fetchBookmarks()
  }, [])

  // Update URL when filters change
  useEffect(() => {
    const params = new URLSearchParams()
    if (filters.tag) params.set('tag', filters.tag)
    if (filters.domain) params.set('domain', filters.domain)
    if (filters.content_type) params.set('content_type', filters.content_type)
    setSearchParams(params)
  }, [filters, setSearchParams])

  const handleFilterChange = (key: string, value: string) => {
    setFilters({ [key]: value || undefined })
    fetchBookmarks(1)
  }

  const handleClearFilters = () => {
    clearFilters()
    setSearchParams({})
    fetchBookmarks(1)
  }

  const handlePageChange = (newPage: number) => {
    fetchBookmarks(newPage)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const hasActiveFilters = filters.tag || filters.domain || filters.content_type || filters.status

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Bookmarks
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {total} bookmark{total !== 1 ? 's' : ''} total
          </p>
        </div>
        
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
            hasActiveFilters
              ? 'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300'
              : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
          }`}
        >
          <Filter className="w-4 h-4" />
          Filters
          {hasActiveFilters && (
            <span className="w-2 h-2 bg-primary-500 rounded-full" />
          )}
          <ChevronDown className={`w-4 h-4 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex flex-wrap gap-4">
            {/* Content Type Filter */}
            <div className="flex-1 min-w-[200px]">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Content Type
              </label>
              <select
                value={filters.content_type || ''}
                onChange={(e) => handleFilterChange('content_type', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              >
                <option value="">All Types</option>
                <option value="article">Article</option>
                <option value="documentation">Documentation</option>
                <option value="video">Video</option>
                <option value="tool">Tool</option>
                <option value="paper">Paper</option>
                <option value="other">Other</option>
              </select>
            </div>

            {/* Status Filter */}
            <div className="flex-1 min-w-[200px]">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Status
              </label>
              <select
                value={filters.status || ''}
                onChange={(e) => handleFilterChange('status', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              >
                <option value="">All Statuses</option>
                <option value="completed">Enriched</option>
                <option value="pending">Pending</option>
                <option value="failed">Failed</option>
              </select>
            </div>

            {/* Sort */}
            <div className="flex-1 min-w-[200px]">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Sort By
              </label>
              <select
                value={`${filters.sort}-${filters.order}`}
                onChange={(e) => {
                  const [sort, order] = e.target.value.split('-')
                  setFilters({ sort, order: order as 'asc' | 'desc' })
                  fetchBookmarks(1)
                }}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              >
                <option value="created_at-desc">Newest First</option>
                <option value="created_at-asc">Oldest First</option>
                <option value="access_count-desc">Most Accessed</option>
                <option value="last_accessed_at-desc">Recently Accessed</option>
              </select>
            </div>
          </div>

          {/* Active Filters */}
          {hasActiveFilters && (
            <div className="flex items-center gap-2 mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
              <span className="text-sm text-gray-500 dark:text-gray-400">Active:</span>
              
              {filters.tag && (
                <span className="inline-flex items-center gap-1 px-2 py-1 bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 text-sm rounded-full">
                  Tag: {filters.tag}
                  <button onClick={() => handleFilterChange('tag', '')}>
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              
              {filters.domain && (
                <span className="inline-flex items-center gap-1 px-2 py-1 bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 text-sm rounded-full">
                  Domain: {filters.domain}
                  <button onClick={() => handleFilterChange('domain', '')}>
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              
              {filters.content_type && (
                <span className="inline-flex items-center gap-1 px-2 py-1 bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-300 text-sm rounded-full">
                  Type: {filters.content_type}
                  <button onClick={() => handleFilterChange('content_type', '')}>
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              
              <button
                onClick={handleClearFilters}
                className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
              >
                Clear all
              </button>
            </div>
          )}
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
        </div>
      )}

      {/* Bookmarks Grid */}
      {!isLoading && bookmarks.length > 0 && (
        <>
          <div className="columns-1 sm:columns-2 xl:columns-3 gap-4 space-y-4">
            {bookmarks.map((bookmark) => (
              <div key={bookmark.id} className="mb-4 break-inside-avoid">
                <BookmarkCard bookmark={bookmark} />
              </div>
            ))}
          </div>

          {/* Pagination */}
          {pages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-8">
              <button
                onClick={() => handlePageChange(page - 1)}
                disabled={page <= 1}
                className="px-4 py-2 text-sm font-medium rounded-lg bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                Previous
              </button>
              
              <span className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">
                Page {page} of {pages}
              </span>
              
              <button
                onClick={() => handlePageChange(page + 1)}
                disabled={page >= pages}
                className="px-4 py-2 text-sm font-medium rounded-lg bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 dark:hover:bg-gray-700"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}

      {/* Empty State */}
      {!isLoading && bookmarks.length === 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl p-12 text-center">
          <p className="text-gray-500 dark:text-gray-400">
            {hasActiveFilters
              ? 'No bookmarks match your filters'
              : 'No bookmarks yet. Add your first one!'}
          </p>
        </div>
      )}
    </div>
  )
}
