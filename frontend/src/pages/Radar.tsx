import { FormEvent, useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Clipboard, Check, ExternalLink, Loader2, Plus, RefreshCw, Trash2, X, Radio } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Bookmark, Feed, FeedItem, feedsApi } from '../lib/api'
import { useUIStore } from '../stores/uiStore'
import SignalSection from '../components/SignalSection'
// Clusters feature temporarily hidden — pending more testing before re-enabling.
// import ClusterSection from '../components/ClusterSection'

const SAMPLE_FEEDS = [
  { title: "Hacker News: Front Page", desc: "Front page tech & startup community news.", url: "https://hnrss.org/frontpage" },
  { title: "Simon Willison's Weblog: ai", desc: "Insightful developer writing & AI updates.", url: "https://simonwillison.net/tags/ai.atom" },
  { title: "Geoffrey Litt", desc: "Dynamic software research & programming systems.", url: "https://www.geoffreylitt.com/feed.xml" },
  { title: "Ed Zitron's Where's Your Ed At", desc: "Sharp commentary on the tech industry.", url: "https://www.wheresyoured.at/rss/" },
  { title: "Lenny's Newsletter", desc: "Product management & startup advice.", url: "https://www.lennysnewsletter.com/feed" },
  { title: "Techmeme", desc: "Essential daily tech news aggregator.", url: "https://www.techmeme.com/feed.xml" },
  { title: "Stratechery by Ben Thompson", desc: "Business, strategy, and tech analysis.", url: "https://stratechery.com/feed/" },
  { title: "Last Week in AI", desc: "A digest of everything happening in artificial intelligence.", url: "https://lastweekin.ai/feed" },
]

interface GroupedFeedItems {
  feed_id: string
  feed_title: string
  feed_favicon_url: string | null
  feed_site_url: string | null
  items: FeedItem[]
}

export default function Radar() {
  const [feeds, setFeeds] = useState<Feed[]>([])
  const [items, setItems] = useState<FeedItem[]>([])
  const [total, setTotal] = useState(0)
  const [newFeedUrl, setNewFeedUrl] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isAddingFeed, setIsAddingFeed] = useState(false)
  const [addingFeedUrl, setAddingFeedUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lastRefreshSummary, setLastRefreshSummary] = useState<string | null>(null)
  const [selectedFeedId, setSelectedFeedId] = useState<string | null>(null)

  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const rawTab = searchParams.get('tab')
  // Normalize legacy tab=signal → tab=brief
  const activeTab = ((rawTab === 'signal' ? 'brief' : rawTab) ?? 'queue') as 'queue' | 'clusters' | 'brief'
  const readItemId = searchParams.get('read')

  // Replace tab=signal in the URL immediately without adding a history entry
  useEffect(() => {
    if (rawTab === 'signal') {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        next.set('tab', 'brief')
        return next
      }, { replace: true })
    }
  }, [rawTab, setSearchParams])

  const [expandedItems, setExpandedItems] = useState<Record<string, boolean>>({})
  const [activeReaderItem, setActiveReaderItem] = useState<FeedItem | null>(null)
  const [readerContent, setReaderContent] = useState<string | null>(null)
  const [readerFormat, setReaderFormat] = useState<string>('html')
  const [isReaderLoading, setIsReaderLoading] = useState(false)
  const [readerError, setReaderError] = useState<string | null>(null)
  const [isExtractingClean, setIsExtractingClean] = useState(false)
  const [isSourcesExpanded, setIsSourcesExpanded] = useState(false)
  const [copiedFeedId, setCopiedFeedId] = useState<string | null>(null)
  const [confirmDeleteFeedId, setConfirmDeleteFeedId] = useState<string | null>(null)

  const PAGE_SIZE = 30
  const [hasMore, setHasMore] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)

  const openAddModal = useUIStore((state) => state.openAddModal)

  const lastSyncedAt = feeds.length
    ? new Date(Math.max(...feeds.filter(f => f.last_fetched_at).map(f => new Date(f.last_fetched_at!).getTime())))
    : null

  const erroredFeeds = feeds.filter(f => f.failure_count && f.failure_count > 0)

  function relativeTime(date: Date): string {
    const diffMs = Date.now() - date.getTime()
    const mins = Math.floor(diffMs / 60000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    return `${Math.floor(hrs / 24)}d ago`
  }

  const handleCopyFeedUrl = (feed: Feed) => {
    navigator.clipboard.writeText(feed.feed_url)
    setCopiedFeedId(feed.id)
    setTimeout(() => setCopiedFeedId(null), 1500)
  }

  const setActiveTab = (tab: 'queue' | 'clusters' | 'brief') => {
    setSearchParams((prev) => {
      const newParams = new URLSearchParams(prev)
      newParams.set('tab', tab)
      return newParams
    }, { replace: true })
  }

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
      setError(err.response?.data?.error || 'Failed to load sources')
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

  const handleOpenReader = useCallback((item: FeedItem) => {
    setSearchParams((prev) => {
      const newParams = new URLSearchParams(prev)
      newParams.set('read', item.id)
      return newParams
    })
  }, [setSearchParams])

  const handleCloseReader = useCallback(() => {
    if (window.history.length > 1) {
      navigate(-1)
    } else {
      setSearchParams((prev) => {
        const newParams = new URLSearchParams(prev)
        newParams.delete('read')
        return newParams
      }, { replace: true })
    }
  }, [navigate, setSearchParams])

  useEffect(() => {
    if (readItemId) {
      const item = items.find((i) => i.id === readItemId)
      if (item) {
        setActiveReaderItem(item)
        setIsReaderLoading(true)
        setReaderError(null)
        setReaderContent(null)
        feedsApi.getItemContent(item.id)
          .then((res) => {
            setReaderContent(res.data.content)
            setReaderFormat(res.data.content_format || 'html')
          })
          .catch((err: any) => {
            setReaderError(err.response?.data?.error || 'Failed to load article content.')
          })
          .finally(() => {
            setIsReaderLoading(false)
          })
      }
    } else {
      setActiveReaderItem(null)
    }
  }, [readItemId, items])

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

  const isAlreadyAdded = (url: string) => {
    const norm = (u: string) => u.toLowerCase().replace(/\/$/, '')
    return feeds.some(f => norm(f.feed_url) === norm(url))
  }

  const handleAddSampleFeed = async (url: string) => {
    setAddingFeedUrl(url)
    setError(null)
    try {
      await feedsApi.create(url)
      setSelectedFeedId(null)
      await handleRefresh(true)
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to add feed')
    } finally {
      setAddingFeedUrl(null)
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

  const deleteFeed = async (feedId: string) => {
    try {
      await feedsApi.delete(feedId)
      setConfirmDeleteFeedId(null)
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
            Sources
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-500 dark:text-slate-400">
            {activeTab === 'queue'
              ? 'New posts from your sources. Save only the ones that deserve a place in your library.'
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
        {/* Clusters feature temporarily hidden — pending more testing before re-enabling.
        <button
          onClick={() => setActiveTab('clusters')}
          className={`pb-2.5 text-sm font-semibold transition-colors border-b-2 -mb-px ${
            activeTab === 'clusters'
              ? 'border-slate-900 text-slate-950 dark:border-slate-100 dark:text-slate-50'
              : 'border-transparent text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-400'
          }`}
        >
          Clusters
        </button>
        */}
        <button
          onClick={() => setActiveTab('brief')}
          className={`pb-2.5 text-sm font-semibold transition-colors border-b-2 -mb-px ${
            activeTab === 'brief'
              ? 'border-slate-900 text-slate-950 dark:border-slate-100 dark:text-slate-50'
              : 'border-transparent text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-400'
          }`}
        >
          Daily Brief
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

      <div className="grid gap-5 xl:grid-cols-[260px_minmax(0,1fr)] w-full min-w-0">
        <aside className="xl:sticky xl:top-20 xl:self-start w-full min-w-0">
          <button
            type="button"
            onClick={() => setIsSourcesExpanded(!isSourcesExpanded)}
            className="flex w-full items-center justify-between rounded-2xl border border-slate-200/70 bg-white/70 px-4 py-3 text-left text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-slate-800/80 dark:bg-slate-900/50 dark:text-slate-300 xl:hidden mb-3"
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

          <div className="hidden xl:block mb-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-medium text-slate-500 dark:text-slate-400">Sources</h2>
              {!isLoading && feeds.length > 0 && (
                <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
                  {lastSyncedAt && (
                    <span title={lastSyncedAt.toLocaleString()}>Synced {relativeTime(lastSyncedAt)}</span>
                  )}
                  {erroredFeeds.length > 0 && (
                    <button
                      onClick={() => setSelectedFeedId(erroredFeeds[0].id)}
                      className="text-rose-500 dark:text-rose-400 hover:underline"
                    >
                      {erroredFeeds.length} failed
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className={`${isSourcesExpanded ? 'block animate-in fade-in slide-in-from-top-2 duration-200' : 'hidden'} xl:block space-y-1 w-full min-w-0`}>
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
                Your followed sources will appear here.
              </div>
            ) : (
              feeds.map((feed) => (
                <div key={feed.id} className="group flex items-center gap-1 w-full min-w-0">
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
                  {confirmDeleteFeedId === feed.id ? (
                    <div className="flex items-center gap-1 animate-in fade-in duration-200 flex-shrink-0">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          deleteFeed(feed.id)
                        }}
                        className="rounded bg-rose-600 px-1.5 py-0.5 text-[10px] font-bold text-white hover:bg-rose-700"
                      >
                        Confirm
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setConfirmDeleteFeedId(null)
                        }}
                        className="rounded bg-slate-200 dark:bg-slate-700 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 dark:text-slate-350 hover:bg-slate-300 dark:hover:bg-slate-600"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <>
                      <button
                        onClick={() => handleCopyFeedUrl(feed)}
                        className="rounded-lg p-1.5 text-slate-350 transition hover:bg-slate-100 hover:text-slate-600 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-300"
                        title="Copy feed URL"
                      >
                        {copiedFeedId === feed.id
                          ? <Check className="h-3.5 w-3.5 text-green-500" />
                          : <Clipboard className="h-3.5 w-3.5" />}
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setConfirmDeleteFeedId(feed.id)
                        }}
                        className="rounded-lg p-1.5 text-slate-355 transition hover:bg-rose-50 hover:text-rose-600 dark:text-slate-400 dark:hover:bg-rose-900/20 dark:hover:text-rose-350"
                        title="Remove source"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </>
                  )}
                </div>
              ))
            )}
          </div>
        </aside>

        <section className="space-y-3 w-full min-w-0">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-slate-500 dark:text-slate-400">
              {selectedFeed ? selectedFeed.title || 'Selected source' : 'New from your sources'} ({isLoading ? '...' : total})
            </h2>
          </div>

          {isLoading ? (
            <div className="grid gap-6 md:grid-cols-2">
              {[1, 2, 3, 4].map((item) => (
                <div key={item} className="h-44 animate-pulse rounded-card bg-slate-200/70 dark:bg-slate-800/70" />
              ))}
            </div>
          ) : feeds.length === 0 ? (
            <div className="rounded-card bg-surface-light px-8 py-10 shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 text-center space-y-6">
              <div className="mx-auto w-16 h-16 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-700 dark:text-slate-300">
                <Radio className="w-8 h-8" />
              </div>
              <div className="space-y-2">
                <h2 className="font-display text-2xl font-normal text-slate-950 dark:text-slate-50">Add your first sources</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md mx-auto leading-relaxed">
                  markly follows blogs, newsletters, and RSS feeds for you. New posts appear in your inbox, and you can generate a daily brief from everything you follow.
                </p>
              </div>

              <div className="border-t border-slate-200/50 dark:border-slate-800/80 pt-6">
                <h3 className="text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-4 text-left">
                  Suggested tech feeds (from your profile)
                </h3>
                <div className="grid gap-4 sm:grid-cols-2 text-left">
                  {SAMPLE_FEEDS.map((feed) => {
                    const added = isAlreadyAdded(feed.url)
                    const adding = addingFeedUrl === feed.url
                    return (
                      <div key={feed.url} className="rounded-2xl border border-slate-200/70 bg-white/50 p-4 flex flex-col justify-between hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900/30 transition-all">
                        <div className="space-y-1">
                          <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{feed.title}</h4>
                          <p className="text-xs text-slate-500 dark:text-slate-400 leading-normal">{feed.desc}</p>
                        </div>
                        <div className="mt-4 flex items-center justify-between">
                          <span className="text-[10px] text-slate-400 dark:text-slate-500 truncate max-w-[150px] font-mono">
                            {new URL(feed.url).hostname}
                          </span>
                          <button
                            onClick={() => handleAddSampleFeed(feed.url)}
                            disabled={added || adding}
                            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors flex items-center gap-1 ${
                              added
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-400 border border-emerald-200/40 dark:border-emerald-900/30'
                                : 'bg-slate-900 text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white disabled:opacity-50'
                            }`}
                          >
                            {adding ? (
                              <>
                                <Loader2 className="w-3 h-3 animate-spin" />
                                Adding...
                              </>
                            ) : added ? (
                              'Added'
                            ) : (
                              <>
                                <Plus className="w-3 h-3" />
                                Add
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-card bg-surface-light px-8 py-12 shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 text-center space-y-4">
              <div className="mx-auto w-12 h-12 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400">
                <Radio className="w-6 h-6" />
              </div>
              <div className="space-y-1">
                <h3 className="font-display text-lg font-medium text-slate-950 dark:text-slate-50">All caught up</h3>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Nothing new in your inbox right now. Check back later or add more sources.
                </p>
              </div>
              <button
                onClick={() => handleRefresh(true)}
                disabled={isRefreshing}
                className="inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white disabled:opacity-50"
              >
                {isRefreshing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                Refresh feeds
              </button>
            </div>
          ) : (
            <div className="space-y-10 select-text">
              {(() => {
                const groupedItems = items.reduce((acc: GroupedFeedItems[], item) => {
                const feedId = item.feed_id || 'unknown';
                let group = acc.find(g => g.feed_id === feedId);
                if (!group) {
                  group = {
                    feed_id: feedId,
                    feed_title: item.feed_title || item.feed_site_url || 'Feed source',
                    feed_favicon_url: item.feed_favicon_url || null,
                    feed_site_url: item.feed_site_url || null,
                    items: []
                  };
                  acc.push(group);
                }
                group.items.push(item);
                return acc;
              }, []);

              return (
                <>
                  {groupedItems.map((group) => (
                    <div key={group.feed_id} className="space-y-4">
                      {/* Source Header */}
                      <div className="flex items-center gap-2 border-b border-slate-200/50 pb-2 dark:border-slate-800/50">
                        {group.feed_favicon_url && (
                          <img src={group.feed_favicon_url} alt="" className="h-4 w-4 rounded" />
                        )}
                        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-350">
                          {group.feed_title}
                        </h3>
                        <span className="rounded-full bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-xs text-slate-500 dark:text-slate-400 font-medium">
                          {group.items.length} {group.items.length === 1 ? 'post' : 'posts'}
                        </span>
                      </div>

                      {/* Cards Grid */}
                      <div className="grid gap-6 md:grid-cols-2">
                        {group.items.map((item) => (
                          <article
                            key={item.id}
                            className="group relative overflow-hidden rounded-card bg-surface-light p-6 shadow-card ring-1 ring-white/60 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-card-hover dark:bg-surface-dark dark:ring-white/10 flex flex-col justify-between"
                          >
                            <div className="space-y-3">
                              <div className="flex items-center justify-between text-xs text-slate-400 dark:text-slate-500 font-sans">
                                {formatDate(item.published_at || item.first_seen_at) && (
                                  <span>{formatDate(item.published_at || item.first_seen_at)}</span>
                                )}
                              </div>
                              
                              <button
                                onClick={() => handleOpenReader(item)}
                                className="block w-full text-left font-display text-lg font-normal leading-snug text-slate-950 transition hover:underline dark:text-slate-50 break-words"
                              >
                                {item.title}
                              </button>

                              {item.summary && (
                                <div>
                                  <p className={`text-sm leading-relaxed text-slate-600 dark:text-slate-300 break-words font-sans ${expandedItems[item.id] ? '' : 'line-clamp-2'}`}>
                                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ p: 'span' }}>
                                      {item.summary}
                                    </ReactMarkdown>
                                  </p>
                                  {item.summary.length > 140 && (
                                    <button
                                      onClick={() => toggleExpandItem(item.id)}
                                      className="mt-2 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
                                    >
                                      {expandedItems[item.id] ? 'Show less' : 'Show more'}
                                    </button>
                                  )}
                                </div>
                              )}
                            </div>

                            <div className="mt-5 border-t border-slate-200/50 pt-4 dark:border-slate-800/50 flex flex-wrap items-center gap-2">
                              <button
                                onClick={() => saveItem(item)}
                                className="rounded-full bg-slate-900 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
                              >
                                Save to Library
                              </button>
                              <button
                                onClick={() => dismissItem(item)}
                                className="inline-flex items-center gap-1 rounded-full px-2.5 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-950 dark:text-slate-450 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                              >
                                <X className="h-3.5 w-3.5" />
                                Dismiss
                              </button>
                              <a
                                href={item.url}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex items-center gap-1 rounded-full px-2.5 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-950 dark:text-slate-450 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                              >
                                <ExternalLink className="h-3.5 w-3.5" />
                                Open Link
                              </a>
                            </div>
                          </article>
                        ))}
                      </div>
                    </div>
                  ))}
                </>
              );
            })()}

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
      /* Clusters feature temporarily hidden — pending more testing before re-enabling.
      ) : activeTab === 'clusters' ? (
        <ClusterSection onSavedSuccess={loadRadar} />
      */
      ) : (
        <SignalSection onGenerateSuccess={loadRadar} />
      )}

      {/* Reader Drawer */}
      {activeReaderItem && createPortal(
        <div className="fixed inset-0 z-[60] flex justify-end bg-slate-950/40 backdrop-blur-sm transition-opacity animate-in fade-in-0 duration-200">
          <div 
            className="fixed inset-0" 
            onClick={handleCloseReader} 
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
                    handleCloseReader()
                  }}
                  className="rounded-full bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
                >
                  Save<span className="hidden sm:inline"> to Library</span>
                </button>
                <button
                  onClick={() => {
                    dismissItem(activeReaderItem)
                    handleCloseReader()
                  }}
                  className="inline-flex items-center gap-1 rounded-full px-2 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                  title="Dismiss from inbox"
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
                  onClick={handleCloseReader}
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
