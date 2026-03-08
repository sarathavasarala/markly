import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search as SearchIcon, Loader2, X, Clock } from 'lucide-react'
import { searchApi, Bookmark } from '../lib/api'
import BookmarkCard from '../components/BookmarkCard'
import MasonryGrid from '../components/MasonryGrid'

export default function Search() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialQuery = searchParams.get('q') || ''
  const initialTag = searchParams.get('tag') || ''
  const [query, setQuery] = useState(initialQuery)
  const [tag, setTag] = useState(initialTag)
  const [results, setResults] = useState<Bookmark[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [searchHistory, setSearchHistory] = useState<string[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [isTyping, setIsTyping] = useState(false)

  // Load search history on mount
  useEffect(() => {
    loadHistory()
  }, [])

  const loadHistory = async () => {
    try {
      const response = await searchApi.getHistory(10)
      const queries = response.data.history.map((h) => h.query)
      setSearchHistory([...new Set(queries)])
    } catch {
      // Ignore error
    }
  }

  // Debounced search (now semantic only)
  const performSearch = useCallback(async (searchQuery: string, searchTag?: string) => {
    if (!searchQuery.trim()) {
      setResults([])
      setHasSearched(false)
      return
    }

    setIsSearching(true)
    setHasSearched(true)

    try {
      const response = await searchApi.search({
        q: searchQuery,
        mode: 'semantic',
        limit: 30,
        tag: searchTag || undefined,
      })
      setResults(response.data.results)
    } catch (error) {
      console.error('Search failed:', error)
      setResults([])
    } finally {
      setIsSearching(false)
    }
  }, [])

  // Sync state with URL params (supports header search navigation)
  useEffect(() => {
    const paramQuery = searchParams.get('q') || ''
    const paramTag = searchParams.get('tag') || ''

    setQuery(paramQuery)
    setTag(paramTag)

    if (paramQuery) {
      performSearch(paramQuery, paramTag)
      setHasSearched(true)
    } else {
      setResults([])
      setHasSearched(false)
    }
  }, [searchParams, performSearch])

  // Handle search on Enter
  const handleSearch = (e?: React.FormEvent) => {
    e?.preventDefault()
    const params: Record<string, string> = { q: query }
    if (tag) params.tag = tag
    setSearchParams(params)
    performSearch(query, tag)
    setShowHistory(false)
  }

  // Keyboard search logic removed for semantic search to save API calls
  useEffect(() => {
    // We intentionally don't auto-search on typing for semantic search
    setIsTyping(false)
  }, [query])

  const handleHistoryClick = (historyQuery: string) => {
    setQuery(historyQuery)
    setShowHistory(false)
    performSearch(historyQuery, tag)
  }

  const clearSearch = () => {
    setQuery('')
    setTag('')
    setResults([])
    setHasSearched(false)
    setSearchParams({})
  }

  return (
    <div className="space-y-6">
      {/* Search Header */}
      <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
        <form onSubmit={handleSearch}>
          {/* Search Input */}
          <div className="relative">
            <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => setShowHistory(true)}
              placeholder="Search by meaning..."
              className="w-full pl-12 pr-10 py-4 text-lg border border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
            {query && (
              <button
                type="button"
                onClick={clearSearch}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* Search History Dropdown */}
          {showHistory && searchHistory.length > 0 && !query && (
            <div className="mt-2 bg-white dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600 shadow-lg overflow-hidden">
              <div className="px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-600">
                Recent Searches
              </div>
              {searchHistory.slice(0, 5).map((historyQuery, index) => (
                <button
                  key={index}
                  type="button"
                  onClick={() => handleHistoryClick(historyQuery)}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-600"
                >
                  <Clock className="w-4 h-4 text-gray-400" />
                  {historyQuery}
                </button>
              ))}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end mt-4">
            <button
              type="submit"
              disabled={!query.trim() || isSearching}
              className="px-6 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Search
            </button>
          </div>
        </form>
      </div>

      {/* Results */}
      {(isSearching || isTyping) && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
          {isTyping && <span className="ml-3 text-gray-500">Typing...</span>}
        </div>
      )}

      {!isSearching && !isTyping && hasSearched && (
        <>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            Found {results.length} result{results.length !== 1 ? 's' : ''} for "{query}"
          </div>

          {results.length === 0 ? (
            <div className="bg-white dark:bg-gray-800 rounded-xl p-12 text-center">
              <SearchIcon className="w-12 h-12 mx-auto text-gray-300 dark:text-gray-600 mb-4" />
              <p className="text-gray-500 dark:text-gray-400">
                No bookmarks found matching your search
              </p>
            </div>
          ) : (
            <MasonryGrid
              items={results}
              renderItem={(bookmark) => (
                <BookmarkCard
                  bookmark={bookmark}
                  onDeleted={(id) => setResults((prev) => prev.filter((b) => b.id !== id))}
                />
              )}
              gap={16}
              breakpoints={{ 0: 1, 640: 2, 1024: 3 }}
            />
          )}
        </>
      )}

      {!hasSearched && !isSearching && (
        <div className="bg-white dark:bg-gray-800 rounded-xl p-12 text-center">
          <SearchIcon className="w-12 h-12 mx-auto text-gray-300 dark:text-gray-600 mb-4" />
          <p className="text-gray-500 dark:text-gray-400">
            Start typing to search your bookmarks
          </p>
        </div>
      )}
    </div>
  )
}
