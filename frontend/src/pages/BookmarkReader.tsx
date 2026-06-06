import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { bookmarksApi, BookmarkArchive } from '../lib/api'
import { ArrowLeft, ExternalLink, Loader2, AlertCircle, RefreshCw, BookOpen, Clock } from 'lucide-react'

export default function BookmarkReader() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [archive, setArchive] = useState<BookmarkArchive | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isRetrying, setIsRetrying] = useState(false)

  const loadArchive = useCallback(async (showLoading = true) => {
    if (!id) return
    if (showLoading) setIsLoading(true)
    setError(null)
    try {
      const res = await bookmarksApi.getArchive(id)
      setArchive(res.data)
    } catch (err: any) {
      if (err.response?.status === 409 && err.response?.data) {
        setArchive(err.response.data)
      } else {
        setError(err.response?.data?.error || 'Failed to load article archive.')
      }
    } finally {
      setIsLoading(false)
    }
  }, [id])

  useEffect(() => {
    loadArchive()
  }, [id, loadArchive])

  // Poll for changes if status is pending or processing
  useEffect(() => {
    if (!archive) return
    const status = archive.archive_status
    if (status === 'pending' || status === 'processing') {
      const interval = setInterval(() => {
        loadArchive(false)
      }, 3000)
      return () => clearInterval(interval)
    }
  }, [archive, loadArchive])

  const handleRetry = async () => {
    if (!id) return
    setIsRetrying(true)
    try {
      await bookmarksApi.retryArchive(id)
      setArchive((prev) =>
        prev
          ? {
              ...prev,
              archive_status: 'pending' as const,
              archive_error: null,
            }
          : null
      )
      await loadArchive(false)
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to restart archiving.')
    } finally {
      setIsRetrying(false)
    }
  }

  const formatDateTime = (dateStr: string | null) => {
    if (!dateStr) return ''
    return new Date(dateStr).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    })
  }

  const readingTime = (wordCount: number | null) => {
    if (!wordCount) return '1 min read'
    const wordsPerMinute = 225
    const minutes = Math.ceil(wordCount / wordsPerMinute)
    return `${minutes} min read`
  }

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-slate-500 dark:text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mb-4" />
        <p className="text-sm font-medium">Loading saved copy...</p>
      </div>
    )
  }

  if (error && !archive) {
    return (
      <div className="max-w-2xl mx-auto my-8 p-6 bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/40 rounded-card flex flex-col items-center text-center">
        <AlertCircle className="w-10 h-10 text-rose-500 dark:text-rose-400 mb-4" />
        <h3 className="font-display text-xl text-slate-900 dark:text-white mb-2">Error Loading Archive</h3>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">{error}</p>
        <button
          onClick={() => loadArchive()}
          className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-950 font-medium text-xs hover:opacity-90 transition-all active:scale-95"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Try Again
        </button>
      </div>
    )
  }

  const status = archive?.archive_status

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Header Controls */}
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-slate-200/60 dark:border-slate-800/60">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to library</span>
        </button>

        {archive && (
          <a
            href={archive.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-sm font-medium text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300 transition-colors"
          >
            <span>Open original</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>

      {archive && (
        <>
          {/* Article Info */}
          <div className="mb-8">
            <span className="text-xs font-semibold uppercase tracking-wider text-indigo-500 dark:text-indigo-400">
              {archive.domain || 'Local Copy'}
            </span>
            <h1 className="font-display text-3xl sm:text-4xl font-normal leading-tight text-slate-950 dark:text-slate-50 mt-2 mb-4">
              {archive.title}
            </h1>
            
            <div className="flex flex-wrap gap-4 text-xs text-slate-400 dark:text-slate-500">
              {archive.archive_word_count && (
                <span className="flex items-center gap-1.5">
                  <BookOpen className="w-3.5 h-3.5" />
                  {archive.archive_word_count.toLocaleString()} words
                </span>
              )}
              {archive.archive_word_count && (
                <span className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" />
                  {readingTime(archive.archive_word_count)}
                </span>
              )}
              {archive.archived_at && (
                <span>Archived on {formatDateTime(archive.archived_at)}</span>
              )}
            </div>
          </div>

          {/* Pending / Processing State */}
          {(status === 'pending' || status === 'processing') && (
            <div className="flex flex-col items-center justify-center py-16 px-6 bg-slate-50 dark:bg-slate-900/40 border border-slate-200/50 dark:border-slate-800/50 rounded-card text-center">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-500 mb-4" />
              <h3 className="font-display text-lg text-slate-900 dark:text-white mb-2">Saving local copy...</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm">
                We are currently downloading and formatting a clean, readable copy of this article. This page will update automatically.
              </p>
            </div>
          )}

          {/* Failed / Unavailable State */}
          {(status === 'failed' || status === 'unavailable') && (
            <div className="flex flex-col items-center justify-center py-12 px-6 bg-rose-50/50 dark:bg-rose-950/10 border border-rose-200/60 dark:border-rose-900/30 rounded-card text-center">
              <AlertCircle className="w-8 h-8 text-rose-500 dark:text-rose-400 mb-4" />
              <h3 className="font-display text-lg text-slate-900 dark:text-white mb-2">Saved Copy Unavailable</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mb-6">
                {archive.archive_error || "A local copy could not be saved because the website blocked downloading or is password-protected."}
              </p>
              <button
                onClick={handleRetry}
                disabled={isRetrying}
                className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-slate-950 text-white dark:bg-slate-100 dark:text-slate-950 font-medium text-xs hover:opacity-90 transition-all active:scale-95 disabled:opacity-50"
              >
                {isRetrying ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Queueing retry...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-3.5 h-3.5" />
                    Retry saved copy
                  </>
                )}
              </button>
            </div>
          )}

          {/* Completed State - Clean Content Render */}
          {status === 'completed' && archive.archive_content && (
            <article className="prose prose-slate dark:prose-invert max-w-none select-text">
              {archive.archive_format === 'markdown' ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{archive.archive_content}</ReactMarkdown>
              ) : (
                <div className="whitespace-pre-wrap font-sans text-base sm:text-[17px] leading-relaxed">
                  {archive.archive_content}
                </div>
              )}
            </article>
          )}
        </>
      )}
    </div>
  )
}
