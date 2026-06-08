import { FormEvent, useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { ExternalLink, Loader2, Plus, RefreshCw, Trash2, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Bookmark, Feed, FeedItem, feedsApi } from '../lib/api'
import { useUIStore } from '../stores/uiStore'
import SignalSection from '../components/SignalSection'

export default function Radar() {
  const [feeds, setFeeds] = useState<Feed[]>([])
  const [items, setItems] = useState<FeedItem[]>([])
  const [total, setTotal] = useState(0)
  const [newFeedUrl, setNewFeedUrl] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isAddingFeed, setIsAddingFeed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastRefreshSummary, setLastRefreshSummary] = useState<string | null>(null)
  const [selectedFeedId, setSelectedFeedId] = useState<string | null>(null)

  const [expandedItems, setExpandedItems] = useState<Record<string, boolean>>({})
  const [activeReaderItem, setActiveReaderItem] = useState<FeedItem | null>(null)
  const [readerContent, setReaderContent] = useState<string | null>(null)
  const [readerFormat, setReaderFormat] = useState<string>('html')
  const [isReaderLoading, setIsReaderLoading] = useState(false)
  const [readerError, setReaderError] = useState<string | null>(null)
  const [isExtractingClean, setIsExtractingClean] = useState(false)
  const [isSourcesExpanded, setIsSourcesExpanded] = useState(false)
  const [activeTab, setActiveTab] = useState<'queue' | 'signal'>('queue')

  const PAGE_SIZE = 30
  const [hasMore, setHasMore] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)

  const openAddModal = useUIStore((state) => state.openAddModal)

  const loadRadar = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [feedsRes, inboxRes] = await Promise.all([
        feedsApi.list(),
        feedsApi.inbox({ limit: PAGE_SIZE, offset: 0, feed_id: selectedFeedId || undefined }),
      ])
      setFeeds(feedsRes.data.feeds)
      setItems(inboxRes.data.items)
      setTotal(inboxRes.data.total)
      setHasMore(inboxRes.data.items.length < inboxRes.data.total)
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load Radar')
    } finally {
      setIsLoading(false)
    }
  }, [selectedFeedId])

  useEffect(() => {
    loadRadar()
  }, [loadRadar])

  const toggleExpandItem = (itemId: string) => {
    setExpandedItems((prev) => ({
      ...prev,
      [itemId]: !prev[itemId],
    }))
  }

  const handleLoadMore = async () => {
    if (isLoadingMore || !hasMore) return
    setIsLoadingMore(true)
    setError(null)
    try {
      const nextOffset = items.length
      const inboxRes = await feedsApi.inbox({
        limit: PAGE_SIZE,
        offset: nextOffset,
        feed_id: selectedFeedId || undefined,
      })
      const newItems = inboxRes.data.items
      setItems((prev) => [...prev, ...newItems])
      setTotal(inboxRes.data.total)
      setHasMore(nextOffset + newItems.length < inboxRes.data.total)
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load more items')
    } finally {
      setIsLoadingMore(false)
    }
  }

  const handleOpenReader = useCallback(async (item: FeedItem) => {
    setActiveReaderItem(item)
    setIsReaderLoading(true)
    setReaderError(null)
    setReaderContent(null)
    try {
      const res = await feedsApi.getItemContent(item.id)
      setReaderContent(res.data.content)
      setReaderFormat(res.data.content_format || 'html')
    } catch (err: any) {
      setReaderError(err.response?.data?.error || 'Failed to load article content.')
    } finally {
      setIsReaderLoading(false)
    }
  }, [])

  const handleExtractCleanContent = async () => {
    if (!activeReaderItem) return
    setIsExtractingClean(true)
    setReaderError(null)
    try {
      const res = await feedsApi.getItemContent(activeReaderItem.id, { fetch_clean: true })
      setReaderContent(res.data.content)
      setReaderFormat(res.data.content_format || 'markdown')
    } catch (err: any) {
      setReaderError(err.response?.data?.error || 'Failed to extract clean readability text.')
    } finally {
      setIsExtractingClean(false)
    }
  }

  const handleAddFeed = async (event: FormEvent) => {
    event.preventDefault()
    if (!newFeedUrl.trim()) return
    setIsAddingFeed(true)
    setError(null)
    try {
      await feedsApi.create(newFeedUrl.trim())
      setNewFeedUrl('')
      setSelectedFeedId(null)
      await handleRefresh(true)
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to add feed')
    } finally {
      setIsAddingFeed(false)
    }
  }

  const handleRefresh = async (force = false) => {
    setIsRefreshing(true)
    setError(null)
    try {
      const response = await feedsApi.refresh({ force, stale_after_minutes: 30 })
      const { items_added, feeds_checked, feeds_failed, feeds_skipped } = response.data
      setLastRefreshSummary(
        `${items_added} new ${items_added === 1 ? 'item' : 'items'} from ${feeds_checked} checked ${feeds_checked === 1 ? 'source' : 'sources'}`
      )
      if (feeds_failed > 0) {
        setLastRefreshSummary((summary) => `${summary}. ${feeds_failed} failed.`)
      } else if (feeds_skipped > 0 && feeds_checked === 0) {
        setLastRefreshSummary('Sources were checked recently.')
      }
      await loadRadar()
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to refresh feeds')
    } finally {
      setIsRefreshing(false)
    }
  }

  const dismissItem = async (item: FeedItem) => {
    try {
      await feedsApi.dismissItem(item.id)
      await loadRadar()
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to dismiss item')
    }
  }

  const deleteFeed = async (feed: Feed) => {
    if (!window.confirm(`Remove ${feed.title || feed.feed_url} from Radar?`)) return
    try {
      await feedsApi.delete(feed.id)
      await loadRadar()
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to remove source')
    }
  }

  const saveItem = (item: FeedItem) => {
    openAddModal({
      url: item.url,
      description: item.summary || undefined,
      sourceLabel: item.feed_title || undefined,
      onSaved: async (bookmark: Bookmark) => {
        await feedsApi.markItemSaved(item.id, bookmark.id)
        await loadRadar()
      },
    })
  }

  const formatDate = (value: string | null) => {
    if (!value) return null
    try {
      return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(new Date(value))
    } catch {
      return null
    }
  }

  const selectedFeed = selectedFeedId ? feeds.find((feed) => feed.id === selectedFeedId) : null
  const allCount = feeds.reduce((count, feed) => count + (feed.new_item_count || 0), 0)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-normal text-slate-950 dark:text-slate-50">
            Radar
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500 dark:text-slate-400">
            {activeTab === 'queue'
              ? 'New articles from your sources. Save only the ones that deserve a place in your library.'
              : 'A high-signal daily intelligence brief synthesized from your followed RSS feeds.'}
          </p>
        </div>

        {activeTab === 'queue' && (
          <button
            onClick={() => handleRefresh(true)}
            disabled={isRefreshing || feeds.length === 0}
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
          >
            {isRefreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Refresh
          </button>
        )}
      </div>

      {/* Tabs Switcher */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 gap-6">
        <button
          onClick={() => setActiveTab('queue')}
          className={`pb-2.5 text-sm font-semibold transition-colors border-b-2 -mb-px ${
            activeTab === 'queue'
              ? 'border-slate-900 text-slate-950 dark:border-slate-100 dark:text-slate-50'
              : 'border-transparent text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-400'
          }`}
        >
          Queue ({isLoading ? '...' : allCount})
        </button>
        <button
          onClick={() => setActiveTab('signal')}
          className={`pb-2.5 text-sm font-semibold transition-colors border-b-2 -mb-px ${
            activeTab === 'signal'
              ? 'border-slate-900 text-slate-950 dark:border-slate-100 dark:text-slate-50'
              : 'border-transparent text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-400'
          }`}
        >
          Signal
        </button>
      </div>

      {activeTab === 'queue' ? (
        <>
          <form
            onSubmit={handleAddFeed}
            className="rounded-card border border-slate-200/70 bg-white/70 p-4 shadow-sm dark:border-slate-800/80 dark:bg-slate-900/50"
          >
            <label className="mb-2 block text-xs font-medium text-slate-500 dark:text-slate-400">
          Add a source
        </label>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            type="text"
            value={newFeedUrl}
            onChange={(event) => setNewFeedUrl(event.target.value)}
            placeholder="Paste a blog or RSS URL"
            className="min-w-0 flex-1 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:focus:border-slate-500 dark:focus:ring-slate-900/40"
          />
          <button
            type="submit"
            disabled={isAddingFeed || !newFeedUrl.trim()}
            className="inline-flex items-center justify-center gap-2 rounded-full bg-white px-4 py-3 text-sm font-medium text-slate-900 ring-1 ring-slate-200 transition hover:bg-slate-50 disabled:opacity-50 dark:bg-slate-800 dark:text-slate-100 dark:ring-slate-700 dark:hover:bg-slate-700"
          >
            {isAddingFeed ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Add source
          </button>
        </div>
      </form>

      {error && (
        <div className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:bg-rose-900/20 dark:text-rose-300">
          {error}
        </div>
      )}

      {lastRefreshSummary && (
        <p className="text-sm text-slate-500 dark:text-slate-400">{lastRefreshSummary}</p>
      )}

      <div className="grid gap-5 xl:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="space-y-3 xl:sticky xl:top-20 xl:self-start">
          <button
            type="button"
            onClick={() => setIsSourcesExpanded(!isSourcesExpanded)}
            className="flex w-full items-center justify-between rounded-2xl border border-slate-200/70 bg-white/70 px-4 py-3 text-left text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-slate-800/80 dark:bg-slate-900/50 dark:text-slate-300 xl:hidden"
          >
            <div className="flex items-center gap-2">
              <span className="text-slate-500 dark:text-slate-400 font-semibold">Sources</span>
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-400 font-medium">
                {selectedFeed ? selectedFeed.title || selectedFeed.feed_url : 'All sources'}
              </span>
            </div>
            <span className="text-xs text-slate-400 font-semibold">
              {isSourcesExpanded ? 'Hide ▲' : 'Show ▼'}
            </span>
          </button>

          <div className="hidden xl:block">
            <h2 className="text-sm font-medium text-slate-500 dark:text-slate-400">Sources</h2>
          </div>

          <div className={`${isSourcesExpanded ? 'block animate-in fade-in slide-in-from-top-2 duration-200' : 'hidden'} xl:block space-y-1`}>
            <button
              onClick={() => {
                setSelectedFeedId(null)
                setIsSourcesExpanded(false)
              }}
              className={`flex w-full items-center justify-between rounded-2xl px-3 py-2 text-left text-sm transition ${selectedFeedId === null
                ? 'bg-white text-slate-950 ring-1 ring-slate-200 shadow-sm dark:bg-slate-800 dark:text-slate-50 dark:ring-slate-700'
                : 'text-slate-600 hover:bg-white/60 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-100'
                }`}
            >
              <span>All sources</span>
              <span className="text-xs tabular-nums text-slate-400 dark:text-slate-500">{allCount}</span>
            </button>
            {feeds.length === 0 ? (
              <div className="rounded-2xl border border-slate-200/70 bg-white/50 p-3 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-400">
                Add your first source to start Radar.
              </div>
            ) : (
              feeds.map((feed) => (
                <div key={feed.id} className="group flex items-center gap-1">
                  <button
                    onClick={() => {
                      setSelectedFeedId(feed.id)
                      setIsSourcesExpanded(false)
                    }}
                    className={`min-w-0 flex-1 rounded-2xl px-3 py-2 text-left transition ${selectedFeedId === feed.id
                      ? 'bg-white text-slate-950 ring-1 ring-slate-200 shadow-sm dark:bg-slate-800 dark:text-slate-50 dark:ring-slate-700'
                      : 'text-slate-600 hover:bg-white/60 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-100'
                      }`}
                  >
                    <div className="flex items-center gap-2">
                      {feed.favicon_url && <img src={feed.favicon_url} alt="" className="h-4 w-4 rounded" />}
                      <span className="truncate text-sm font-medium">{feed.title || feed.feed_url}</span>
                      <span className="ml-auto text-xs tabular-nums text-slate-400 dark:text-slate-500">
                        {feed.new_item_count || 0}
                      </span>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-slate-400 dark:text-slate-500">
                      {feed.last_fetched_at ? `Checked ${new Date(feed.last_fetched_at).toLocaleDateString()}` : 'Not checked yet'}
                    </p>
                    {feed.last_error && (
                      <p className="mt-1 truncate text-xs text-rose-600 dark:text-rose-300">
                        {feed.last_error}
                      </p>
                    )}
                  </button>
                  <button
                    onClick={() => deleteFeed(feed)}
                    className="rounded-lg p-1.5 text-slate-300 opacity-0 transition hover:bg-rose-50 hover:text-rose-600 group-hover:opacity-100 dark:hover:bg-rose-900/20 dark:hover:text-rose-300"
                    title="Remove source"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))
            )}
          </div>
        </aside>

        <section className="space-y-3 min-w-0">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-slate-500 dark:text-slate-400">
              {selectedFeed ? selectedFeed.title || 'Selected source' : 'New from your sources'} ({isLoading ? '...' : total})
            </h2>
          </div>

          {isLoading ? (
            <div className="space-y-2">
              {[1, 2, 3, 4, 5].map((item) => (
                <div key={item} className="h-28 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-slate-800/70" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-card border border-dashed border-slate-300 bg-white/40 py-16 text-center dark:border-slate-700 dark:bg-slate-900/40">
              <p className="text-slate-500 dark:text-slate-400">
                Nothing new in Radar. Add a source or refresh later.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              <div className="space-y-2">
                {items.map((item) => (
                  <article
                    key={item.id}
                    className="rounded-3xl border border-slate-200/70 bg-white/80 p-4 shadow-sm transition hover:shadow-md dark:border-slate-800/80 dark:bg-slate-900/60"
                  >
                    <div className="mb-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
                      {item.feed_favicon_url && (
                        <img src={item.feed_favicon_url} alt="" className="h-4 w-4 rounded" />
                      )}
                      <span>{item.feed_title || item.feed_site_url || 'Feed source'}</span>
                      {formatDate(item.published_at || item.first_seen_at) && (
                        <>
                          <span>&middot;</span>
                          <span>{formatDate(item.published_at || item.first_seen_at)}</span>
                        </>
                      )}
                    </div>
                    <button
                      onClick={() => handleOpenReader(item)}
                      className="block w-full text-left font-display text-lg font-normal leading-snug text-slate-950 transition hover:underline dark:text-slate-50 break-words"
                    >
                      {item.title}
                    </button>
                    {item.summary && (
                      <div className="mt-1.5">
                        <p className={`text-sm leading-5 text-slate-600 dark:text-slate-300 break-words ${expandedItems[item.id] ? '' : 'line-clamp-2'}`}>
                          <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ p: 'span' }}>
                            {item.summary}
                          </ReactMarkdown>
                        </p>
                        {item.summary.length > 140 && (
                          <button
                            onClick={() => toggleExpandItem(item.id)}
                            className="mt-1 text-xs font-semibold text-slate-600 hover:text-slate-950 hover:underline dark:text-slate-400 dark:hover:text-slate-50 transition-colors"
                          >
                            {expandedItems[item.id] ? 'Show less' : 'Show more'}
                          </button>
                        )}
                      </div>
                    )}
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <button
                        onClick={() => saveItem(item)}
                        className="rounded-full bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
                      >
                        Save to Library
                      </button>
                      <button
                        onClick={() => dismissItem(item)}
                        className="inline-flex items-center gap-1 rounded-full px-2.5 py-1.5 text-xs font-medium text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                      >
                        <X className="h-3.5 w-3.5" />
                        Dismiss
                      </button>
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 rounded-full px-2.5 py-1.5 text-xs font-medium text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                      >
                        <ExternalLink className="h-3.5 w-3.5" />
                        Open Link
                      </a>
                    </div>
                  </article>
                ))}
              </div>

              {hasMore && (
                <div className="flex justify-center pt-4">
                  <button
                    onClick={handleLoadMore}
                    disabled={isLoadingMore}
                    className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-6 py-2.5 text-sm font-semibold text-slate-800 shadow-sm transition hover:bg-slate-50 hover:text-slate-900 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800/80 dark:hover:text-slate-100"
                  >
                    {isLoadingMore ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Loading more...
                      </>
                    ) : (
                      'Load More'
                    )}
                  </button>
                </div>
              )}
            </div>
          )}
        </section>

      </div>
      </>
      ) : (
        <SignalSection onGenerateSuccess={loadRadar} />
      )}

      {/* Reader Drawer */}
      {activeReaderItem && createPortal(
        <div className="fixed inset-0 z-[60] flex justify-end bg-slate-950/40 backdrop-blur-sm transition-opacity animate-in fade-in-0 duration-200">
          <div 
            className="fixed inset-0" 
            onClick={() => setActiveReaderItem(null)} 
          />
          <aside className="relative z-10 flex h-full w-full max-w-4xl flex-col bg-white shadow-2xl transition-transform dark:bg-slate-950 border-l border-slate-200 dark:border-slate-800 animate-in slide-in-from-right duration-300">
            {/* Drawer Header */}
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200/60 p-4 dark:border-slate-800/60">
              <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                {activeReaderItem.feed_favicon_url && (
                  <img src={activeReaderItem.feed_favicon_url} alt="" className="h-4 w-4 rounded" />
                )}
                <span className="font-semibold truncate max-w-[150px] sm:max-w-[200px]">
                  {activeReaderItem.feed_title || 'Feed source'}
                </span>
                {formatDate(activeReaderItem.published_at || activeReaderItem.first_seen_at) && (
                  <>
                    <span>&middot;</span>
                    <span>{formatDate(activeReaderItem.published_at || activeReaderItem.first_seen_at)}</span>
                  </>
                )}
              </div>
              <div className="flex items-center gap-1 sm:gap-1.5">
                <button
                  onClick={() => {
                    saveItem(activeReaderItem)
                    setActiveReaderItem(null)
                  }}
                  className="rounded-full bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
                >
                  Save<span className="hidden sm:inline"> to Library</span>
                </button>
                <button
                  onClick={() => {
                    dismissItem(activeReaderItem)
                    setActiveReaderItem(null)
                  }}
                  className="inline-flex items-center gap-1 rounded-full px-2 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                  title="Dismiss from Radar"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">Dismiss</span>
                </button>
                <a
                  href={activeReaderItem.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 rounded-full px-2 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                  title="Open original link"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">Open Link</span>
                </a>
                <button
                  onClick={() => setActiveReaderItem(null)}
                  className="rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                  title="Close Reader"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Drawer Content */}
            <div className="flex-1 overflow-y-auto px-6 py-8 md:px-8 select-text">
              <div className="mx-auto max-w-2xl">
                <h1 className="font-display text-2xl sm:text-3xl font-semibold leading-tight text-slate-950 dark:text-slate-50 mb-2">
                  {activeReaderItem.title}
                </h1>
                <div className="mb-6 flex flex-wrap items-center gap-3 text-sm text-slate-500 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800 pb-4">
                  {activeReaderItem.author && (
                    <>
                      <span>By {activeReaderItem.author}</span>
                      <span className="text-slate-300 dark:text-slate-700">&middot;</span>
                    </>
                  )}
                  <button
                    onClick={handleExtractCleanContent}
                    disabled={isReaderLoading || isExtractingClean}
                    className="inline-flex items-center gap-1.5 rounded-full bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-slate-200/60 transition hover:bg-slate-100 dark:bg-slate-900 dark:text-slate-300 dark:ring-slate-800/80 disabled:opacity-50"
                  >
                    {isExtractingClean ? (
                      <>
                        <Loader2 className="h-3 w-3 animate-spin" />
                        Extracting...
                      </>
                    ) : (
                      <>
                        <RefreshCw className="h-3 w-3" />
                        Extract Clean Reader View
                      </>
                    )}
                  </button>
                </div>

                {isReaderLoading ? (
                  <div className="flex flex-col items-center justify-center py-24 text-slate-500 dark:text-slate-400">
                    <Loader2 className="h-8 w-8 animate-spin text-slate-600 dark:text-slate-400 mb-4" />
                    <p className="text-sm font-medium">Loading content...</p>
                  </div>
                ) : readerError ? (
                  <div className="rounded-2xl bg-rose-50 p-4 text-sm text-rose-700 dark:bg-rose-900/20 dark:text-rose-300">
                    {readerError}
                  </div>
                ) : readerContent ? (
                  <article className="prose prose-slate dark:prose-invert max-w-none text-slate-800 dark:text-slate-200">
                    {readerFormat === 'markdown' ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{readerContent}</ReactMarkdown>
                    ) : (
                      <div 
                        className="feed-html-content space-y-4 text-base leading-relaxed" 
                        dangerouslySetInnerHTML={{ __html: readerContent }} 
                      />
                    )}
                  </article>
                ) : (
                  <div className="py-12 text-center text-sm text-slate-500 dark:text-slate-400">
                    No content available. Click 'Extract Clean Reader View' to load the full article.
                  </div>
                )}
              </div>
            </div>
          </aside>
        </div>,
        document.body
      )}
    </div>
  )
}
