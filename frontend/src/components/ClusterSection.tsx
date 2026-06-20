import { useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Sparkles, Loader2, RefreshCw, Layers, X, BookOpen } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { clustersApi, SignalCluster, SignalClusterReport, Bookmark, FeedItem, feedsApi } from '../lib/api'
import { useUIStore } from '../stores/uiStore'
import MasonryGrid from './MasonryGrid'

export default function ClusterSection({ onSavedSuccess }: { onSavedSuccess?: () => void }) {
  const [clusters, setClusters] = useState<SignalCluster[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  
  // Drawer states
  const [reportCluster, setReportCluster] = useState<SignalCluster | null>(null)
  const [reportsHistory, setReportsHistory] = useState<SignalClusterReport[]>([])
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  
  const [error, setError] = useState<string | null>(null)
  const [infoMessage, setInfoMessage] = useState<string | null>(null)
  
  const openAddModal = useUIStore((state) => state.openAddModal)

  const loadClusters = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await clustersApi.list()
      setClusters(res.data.clusters)
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load clusters')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadClusters()
  }, [loadClusters])

  const handleRefresh = async () => {
    setIsRefreshing(true)
    setError(null)
    setInfoMessage(null)
    try {
      const res = await clustersApi.refresh()
      setClusters(res.data.clusters)
      const { created, updated } = res.data
      if (created === 0 && updated === 0) {
        setInfoMessage('Your clusters are up to date. No new groups were found.')
      } else {
        const parts = []
        if (created > 0) parts.push(`${created} new ${created === 1 ? 'cluster' : 'clusters'}`)
        if (updated > 0) parts.push(`${updated} updated`)
        setInfoMessage(`Sources updated: ${parts.join(' and ')}.`)
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to refresh clusters')
    } finally {
      setIsRefreshing(false)
    }
  }

  const handleOpenReportDrawer = async (cluster: SignalCluster) => {
    setError(null)
    setReportCluster(cluster)
    try {
      const histRes = await clustersApi.listReports(cluster.id)
      setReportsHistory(histRes.data.reports)
      
      if (cluster.latest_report) {
        setSelectedReportId(cluster.latest_report.id)
      } else if (histRes.data.reports.length > 0) {
        setSelectedReportId(histRes.data.reports[0].id)
      } else {
        setSelectedReportId(null)
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load report history')
    }
  }

  const handleCloseReportDrawer = () => {
    setReportCluster(null)
    setReportsHistory([])
    setSelectedReportId(null)
  }

  const handleGenerateReport = async (clusterId: string) => {
    setIsGenerating(true)
    setError(null)
    setInfoMessage(null)
    try {
      const report = await clustersApi.generateReport(clusterId)
      
      // Reload clusters list to get the updated reports and status
      const listRes = await clustersApi.list()
      setClusters(listRes.data.clusters)
      
      // If the drawer is currently open for this cluster, update the drawer states
      if (reportCluster && reportCluster.id === clusterId) {
        const updatedCluster = listRes.data.clusters.find(c => c.id === clusterId)
        if (updatedCluster) {
          setReportCluster(updatedCluster)
          const histRes = await clustersApi.listReports(clusterId)
          setReportsHistory(histRes.data.reports)
          setSelectedReportId(report.data.id)
        }
      }
      
      setInfoMessage(`Report generated: "${report.data.title}"`)
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to generate report')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleDeleteConfirm = async (id: string) => {
    setError(null)
    try {
      await clustersApi.delete(id)
      setClusters(prev => prev.filter(c => c.id !== id))
      if (reportCluster && reportCluster.id === id) {
        handleCloseReportDrawer()
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to delete cluster')
    } finally {
      setConfirmDeleteId(null)
    }
  }

  const saveItem = (item: FeedItem) => {
    openAddModal({
      url: item.url,
      description: item.summary || undefined,
      sourceLabel: item.feed_title || undefined,
      onSaved: async (bookmark: Bookmark) => {
        await feedsApi.markItemSaved(item.id, bookmark.id)
        // Refresh list to update saved status
        const listRes = await clustersApi.list()
        setClusters(listRes.data.clusters)
        
        // If drawer is open, reload drawer's items status as well
        if (reportCluster) {
          const updatedCluster = listRes.data.clusters.find(c => c.id === reportCluster.id)
          if (updatedCluster) {
            setReportCluster(updatedCluster)
          }
        }
        
        if (onSavedSuccess) {
          onSavedSuccess()
        }
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

  const formatLongDate = (value: string | null) => {
    if (!value) return null
    try {
      return new Intl.DateTimeFormat(undefined, { 
        weekday: 'long',
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
      }).format(new Date(value))
    } catch {
      return null
    }
  }

  const selectedReport = reportsHistory.find(r => r.id === selectedReportId)

  return (
    <div className="space-y-6">
      {/* Action Bar */}
      <div className="flex flex-col gap-3 border-b border-slate-200/60 pb-3 dark:border-slate-800/60 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
          Topic Clusters
        </h2>
        
        <div className="flex items-center gap-2">
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
          >
            {isRefreshing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Refresh clusters
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:bg-rose-900/20 dark:text-rose-300">
          {error}
        </div>
      )}

      {infoMessage && (
        <p className="text-sm text-slate-500 dark:text-slate-400 animate-in fade-in duration-200">
          {infoMessage}
        </p>
      )}

      {isLoading ? (
        <div className="grid gap-5 md:grid-cols-2 w-full min-w-0">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-48 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-slate-800/70" />
          ))}
        </div>
      ) : clusters.length === 0 && !isRefreshing ? (
        /* Empty State */
        <div className="rounded-card border border-dashed border-slate-300 bg-white/40 px-6 py-16 text-center dark:border-slate-700 dark:bg-slate-900/40">
          <div className="mx-auto max-w-lg space-y-4">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-800">
              <Layers className="h-6 w-6 text-slate-600 dark:text-slate-400" />
            </div>
            <h2 className="font-display text-xl font-normal text-slate-900 dark:text-slate-100">
              No clusters yet
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Refresh sources or generate clusters from recent articles. Clusters group related RSS items together by theme and topic.
            </p>
            <div className="pt-4 flex justify-center">
              <button
                onClick={handleRefresh}
                className="rounded-full bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
              >
                Refresh clusters
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* Techmeme-style Board Layout using MasonryGrid */
        <MasonryGrid
          items={clusters}
          breakpoints={{ 0: 1, 768: 2, 1280: 3 }}
          renderItem={(cluster) => {
            const hasReport = !!cluster.latest_report
            const newCount = cluster.new_since_last_report || 0
            const clusterImage = cluster.items?.find(item => item.bookmark_thumbnail_url)?.bookmark_thumbnail_url
            
            return (
              <article 
                className="group relative flex flex-col justify-between overflow-hidden rounded-3xl border border-slate-200/70 bg-white/80 shadow-sm hover:-translate-y-0.5 hover:shadow-card-hover transition-all duration-300 dark:border-slate-800/80 dark:bg-slate-900/50"
              >
                {/* Dismiss button overlaid on top right */}
                {confirmDeleteId === cluster.id ? (
                  <div className="absolute top-3 right-3 z-20 flex items-center gap-1 bg-white dark:bg-slate-950 rounded-full shadow-md p-1.5 ring-1 ring-slate-200 dark:ring-slate-850 animate-in fade-in slide-in-from-top-1">
                    <button
                      onClick={() => handleDeleteConfirm(cluster.id)}
                      className="px-2 py-0.5 text-[9px] font-bold text-white bg-rose-600 rounded-full hover:bg-rose-700 transition-colors"
                    >
                      Delete
                    </button>
                    <button
                      onClick={() => setConfirmDeleteId(null)}
                      className="px-2 py-0.5 text-[9px] font-bold text-slate-650 bg-slate-100 dark:text-slate-350 dark:bg-slate-850 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-full transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmDeleteId(cluster.id)}
                    className={`absolute top-4 right-4 z-10 rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-rose-600 dark:hover:bg-slate-850 dark:text-slate-500 dark:hover:text-rose-450 transition-all duration-200 ${clusterImage ? 'bg-slate-950/35 text-white/80 hover:bg-slate-950/60 hover:text-white' : ''} opacity-0 group-hover:opacity-100`}
                    title="Dismiss cluster"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}

                {/* Card Header Banner (Image only) */}
                {clusterImage && (
                  <div className="h-28 w-full overflow-hidden relative border-b border-slate-100 dark:border-slate-800">
                    <img src={clusterImage.replace(/^http:\/\//, 'https://')} alt="" className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" />
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950/70 via-slate-950/20 to-transparent" />
                  </div>
                )}

                <div className="p-5 flex-1 flex flex-col justify-between">
                  <div className="space-y-4">
                    {/* Topic Badge */}
                    <div className="flex items-center justify-between">
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-[9px] font-bold text-slate-500 dark:bg-slate-800 dark:text-slate-450 uppercase tracking-wider font-mono">
                        {cluster.topic_key || 'topic'}
                      </span>
                    </div>
                    {/* Title and Short Description */}
                    <div className="space-y-1.5">
                      <h3 className="font-display text-base font-bold text-slate-950 dark:text-slate-50 leading-snug group-hover:text-slate-700 dark:group-hover:text-slate-300 transition-colors">
                        {cluster.title}
                      </h3>
                      {cluster.summary && (
                        <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed italic">
                          {cluster.summary}
                        </p>
                      )}
                    </div>

                    {/* Techmeme-style straight link list of articles */}
                    <div className="pt-3 border-t border-slate-100 dark:border-slate-800/85">
                      <ul className="space-y-2.5 text-xs">
                        {cluster.items?.map((item) => {
                          const isSaved = item.status === 'saved' || item.bookmark_id !== null
                          return (
                            <li key={item.id} className="flex items-start justify-between gap-3 group/link">
                              <div className="flex items-start gap-2 min-w-0 leading-relaxed text-slate-700 dark:text-slate-350">
                                <div className="flex h-5 w-5 shrink-0 items-center justify-center overflow-hidden rounded-md border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900 mt-0.5">
                                  <img
                                    src={item.feed_favicon_url || `https://www.google.com/s2/favicons?domain=${item.feed_site_url || 'domain'}&sz=32`}
                                    alt=""
                                    className="h-3 w-3 object-contain"
                                    onError={(e) => {
                                      const target = e.target as HTMLImageElement;
                                      target.style.display = 'none';
                                    }}
                                  />
                                </div>
                                <a
                                  href={item.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="hover:underline text-slate-800 dark:text-slate-200 font-medium break-words"
                                >
                                  {item.title}
                                </a>
                                {formatDate(item.published_at || item.first_seen_at) && (
                                  <span className="text-[10px] text-slate-400 dark:text-slate-500 font-medium flex-shrink-0 whitespace-nowrap ml-1">
                                    ({formatDate(item.published_at || item.first_seen_at)})
                                  </span>
                                )}
                              </div>
                              
                              <button
                                onClick={() => saveItem(item)}
                                disabled={isSaved}
                                className={`flex-shrink-0 text-[9px] font-bold opacity-0 group-hover/link:opacity-100 transition duration-150 px-2 py-0.5 rounded-full ${
                                  isSaved
                                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-400 border border-emerald-250/20 opacity-100'
                                    : 'bg-slate-100 text-slate-700 hover:bg-slate-250 dark:bg-slate-850 dark:text-slate-300'
                                }`}
                              >
                                {isSaved ? 'Saved' : 'Save'}
                              </button>
                            </li>
                          )
                        })}
                      </ul>
                    </div>
                  </div>

                  {/* Single Clear Action Button */}
                  <div className="pt-4 mt-4 border-t border-slate-100 dark:border-slate-850/80 flex items-center justify-between">
                    <div className="text-[10px] text-slate-400 dark:text-slate-500 font-medium">
                      {cluster.article_count} articles &middot; {cluster.source_count} sources
                    </div>

                    <div className="flex items-center gap-2">
                      {hasReport ? (
                        <>
                          {newCount > 0 && (
                           <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-bold text-slate-650 dark:bg-slate-800 dark:text-slate-350 whitespace-nowrap">
                              {newCount} new
                            </span>
                          )}
                          <button
                            onClick={() => handleOpenReportDrawer(cluster)}
                            className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 ring-1 ring-slate-200 transition hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700 dark:hover:bg-slate-750"
                          >
                            <BookOpen className="h-3.5 w-3.5" />
                            Read analysis
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => handleGenerateReport(cluster.id)}
                          disabled={isGenerating}
                          className="inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-slate-750 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white animate-in fade-in"
                        >
                          <Sparkles className="h-3.5 w-3.5" />
                          Generate analysis
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </article>
            )
          }}
        />
      )}

      {/* Slide-over analysis drawer (rendered via Portal) */}
      {reportCluster && createPortal(
        <div className="fixed inset-0 z-[60] flex justify-end bg-slate-950/40 backdrop-blur-sm transition-opacity animate-in fade-in-0 duration-200">
          <div 
            className="fixed inset-0" 
            onClick={handleCloseReportDrawer} 
          />
          <aside className="relative z-10 flex h-full w-full max-w-3xl flex-col bg-white shadow-2xl transition-transform dark:bg-slate-950 border-l border-slate-200 dark:border-slate-800 animate-in slide-in-from-right duration-300">
            {/* Drawer Header */}
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200/60 p-5 dark:border-slate-800/60">
              <div className="min-w-0 flex-1 space-y-1">
                <span className="rounded bg-slate-100 px-2 py-0.5 text-[9px] font-bold text-slate-500 dark:bg-slate-800 dark:text-slate-400 font-mono">
                  {reportCluster.topic_key || 'topic'}
                </span>
                <h3 className="font-display text-lg font-bold text-slate-950 dark:text-slate-50 leading-tight truncate">
                  {reportCluster.title}
                </h3>
              </div>

              <div className="flex items-center gap-2">
                {/* Version dropdown if there is report history */}
                {reportsHistory.length > 1 && (
                  <select
                    value={selectedReportId || ''}
                    onChange={(e) => setSelectedReportId(e.target.value)}
                    className="rounded border border-slate-200 px-2.5 py-1 text-xs outline-none bg-white dark:border-slate-800 dark:bg-slate-900 text-slate-850 dark:text-slate-200 focus:border-slate-400"
                  >
                    {reportsHistory.map((rep, idx) => (
                      <option key={rep.id} value={rep.id}>
                        {formatDate(rep.generated_at)} (v{reportsHistory.length - idx})
                      </option>
                    ))}
                  </select>
                )}

                <button
                  onClick={() => handleGenerateReport(reportCluster.id)}
                  disabled={isGenerating}
                  className="rounded-full bg-slate-900 px-3.5 py-1.5 text-xs font-semibold text-white transition hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white disabled:opacity-50 inline-flex items-center gap-1"
                >
                  {isGenerating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
                  Regenerate
                </button>

                <button
                  onClick={handleCloseReportDrawer}
                  className="rounded-full p-1.5 text-slate-450 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                  title="Close report"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Drawer Body - Synthesized Analysis */}
            <div className="flex-1 overflow-y-auto px-6 py-8 md:px-8 select-text">
              <div className="mx-auto max-w-2xl space-y-6">
                {selectedReport ? (
                  <>
                    <div className="border-b border-slate-100 pb-4 dark:border-slate-900">
                      <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1">
                        Report generated &bull; {formatLongDate(selectedReport.generated_at) || formatDate(selectedReport.generated_at)}
                      </div>
                      <h1 className="font-display text-2xl font-bold leading-tight text-slate-950 dark:text-slate-50">
                        {selectedReport.title || 'Cluster Analysis Report'}
                      </h1>
                    </div>

                    <div className="prose prose-slate dark:prose-invert max-w-none text-slate-800 dark:text-slate-200 leading-relaxed font-sans text-base">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          a: ({ href, children }) => (
                            <a
                              href={href}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-slate-700 dark:text-slate-300 underline decoration-slate-400/50 underline-offset-2 transition hover:text-slate-950 hover:decoration-slate-700 dark:hover:text-slate-100 dark:decoration-slate-500/50 dark:hover:decoration-slate-300 font-medium"
                            >
                              {children}
                            </a>
                          )
                        }}
                      >
                        {selectedReport.content}
                      </ReactMarkdown>
                    </div>
                  </>
                ) : (
                  <div className="flex flex-col items-center justify-center py-20 text-slate-500 dark:text-slate-400">
                    <Loader2 className="h-8 w-8 animate-spin mb-4" />
                    <p className="text-sm font-medium">Loading report content...</p>
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
