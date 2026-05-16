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
        mode: 'keyword',
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

  const handleSearch = (e?: React.FormEvent) => {
    e?.preventDefault()
    const params: Record<string, string> = { q: query }
    if (tag) params.tag = tag
    setSearchParams(params)
    performSearch(query, tag)
    setShowHistory(false)
  }

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
    <div className="space-y-8">
      {/* Search header */}
      <div className="rounded-card bg-surface-light shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 px-6 py-6 sm:px-8 sm:py-7">
        <h1 className="font-display text-3xl text-slate-950 dark:text-slate-50 sm:text-4xl">Search your library</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Find any link by title, summary, or topic.</p>

        <form onSubmit={handleSearch} className="mt-6 relative">
          <SearchIcon className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setShowHistory(true)}
            placeholder="What are you looking for?"
            className="w-full pl-14 pr-12 py-4 rounded-full bg-white/80 ring-1 ring-slate-200 text-base text-slate-900 placeholder-slate-400 outline-none transition focus:ring-2 focus:ring-indigo-300 dark:bg-slate-900/60 dark:ring-slate-700 dark:text-slate-100 dark:placeholder-slate-500 dark:focus:ring-indigo-500/40"
          />
          {query && (
            <button
              type="button"
              onClick={clearSearch}
              className="absolute right-5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          )}

          {showHistory && searchHistory.length > 0 && !query && (
            <div className="absolute left-0 right-0 mt-2 z-10 rounded-2xl bg-white shadow-card ring-1 ring-slate-200/70 overflow-hidden dark:bg-slate-900 dark:ring-slate-800">
              <div className="px-4 py-2 text-xs font-medium text-slate-500 dark:text-slate-400">
                Recent searches
              </div>
              {searchHistory.slice(0, 5).map((historyQuery, index) => (
                <button
                  key={index}
                  type="button"
                  onClick={() => handleHistoryClick(historyQuery)}
                  className="w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-100/70 dark:text-slate-200 dark:hover:bg-slate-800/60 transition-colors"
                >
                  <Clock className="w-4 h-4 text-slate-400" />
                  {historyQuery}
                </button>
              ))}
            </div>
          )}
        </form>
      </div>

      {/* Results */}
      {isSearching && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
        </div>
      )}

      {!isSearching && hasSearched && (
        <>
          <div className="text-sm text-slate-500 dark:text-slate-400">
            {results.length} {results.length === 1 ? 'result' : 'results'} for <span className="text-slate-900 dark:text-slate-100">"{query}"</span>
          </div>

          {results.length === 0 ? (
            <div className="rounded-card bg-surface-light shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 px-8 py-16 text-center">
              <div className="mx-auto w-12 h-12 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400 mb-3">
                <SearchIcon className="w-5 h-5" />
              </div>
              <p className="font-display text-xl text-slate-950 dark:text-slate-50">No matches</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Try a different word or check your topics.</p>
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
        <div className="rounded-card bg-surface-light shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 px-8 py-16 text-center">
          <div className="mx-auto w-12 h-12 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400 mb-3">
            <SearchIcon className="w-5 h-5" />
          </div>
          <p className="font-display text-xl text-slate-950 dark:text-slate-50">Start a search</p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Type a phrase, a topic, or part of a title.</p>
        </div>
      )}
    </div>
  )
}
