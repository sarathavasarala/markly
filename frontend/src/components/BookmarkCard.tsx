import {
  ExternalLink,
  Copy,
  Loader2,
  AlertCircle,
  RefreshCw,
  MoreVertical,
  Trash2,
  Edit2
} from 'lucide-react'
import { useState, memo } from 'react'
import { Bookmark } from '../lib/api'
import { useBookmarksStore } from '../stores/bookmarksStore'
import { useUIStore } from '../stores/uiStore'

interface BookmarkCardProps {
  bookmark: Bookmark
  onDeleted?: (id: string) => void
  onTagClick?: (tag: string) => void
}

const BookmarkCard = memo(function BookmarkCard({
  bookmark,
  onDeleted,
  onTagClick,
}: BookmarkCardProps) {
  const [showMenu, setShowMenu] = useState(false)
  const [copied, setCopied] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  const { trackAccess, retryEnrichment, deleteBookmark } = useBookmarksStore()
  const setEditingBookmark = useUIStore((state) => state.setEditingBookmark)

  const title = bookmark.clean_title || bookmark.original_title || bookmark.url
  const isEnriching = bookmark.enrichment_status === 'pending' || bookmark.enrichment_status === 'processing'
  const isFailed = bookmark.enrichment_status === 'failed'

  const handleOpen = () => {
    trackAccess(bookmark.id)
    window.open(bookmark.url, '_blank')
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(bookmark.url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleRetry = () => {
    retryEnrichment(bookmark.id)
    setShowMenu(false)
  }

  const handleDelete = () => {
    if (isDeleting) return
    if (window.confirm('Delete this bookmark?')) {
      setIsDeleting(true)
      deleteBookmark(bookmark.id).then(() => {
        onDeleted?.(bookmark.id)
      }).finally(() => {
        setIsDeleting(false)
      })
    }
    setShowMenu(false)
  }

  const formatDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return '—'
    const d = new Date(dateStr)
    if (Number.isNaN(d.getTime())) return '—'
    const now = new Date()

    // Normalize dates to midnight to compare calendar days
    const d1 = new Date(d.getFullYear(), d.getMonth(), d.getDate())
    const d2 = new Date(now.getFullYear(), now.getMonth(), now.getDate())

    const diffMs = d2.getTime() - d1.getTime()
    const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24))

    if (diffDays === 0) return 'Today'
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays} days ago`
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
    return d.toLocaleDateString()
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden hover:shadow-lg transition-shadow break-inside-avoid w-full text-sm">
      {/* Thumbnail */}
      {bookmark.thumbnail_url && (
        <div className="h-32 bg-gray-100 dark:bg-gray-700 overflow-hidden">
          <img
            src={bookmark.thumbnail_url}
            alt=""
            className="w-full h-full object-cover"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = 'none'
            }}
          />
        </div>
      )}

      <div className="p-3">
        {/* Header */}
        <div className="flex items-start gap-3">
          {/* Favicon */}
          <div className="flex-shrink-0 w-8 h-8 bg-gray-100 dark:bg-gray-700 rounded-lg overflow-hidden">
            {bookmark.favicon_url ? (
              <img
                src={bookmark.favicon_url}
                alt=""
                className="w-full h-full object-contain"
                onError={(e) => {
                  (e.target as HTMLImageElement).src = `https://www.google.com/s2/favicons?domain=${bookmark.domain}&sz=64`
                }}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-gray-400">
                🔗
              </div>
            )}
          </div>

          {/* Title & Domain */}
          <div className="flex-1 min-w-0">
            <a
              href={bookmark.url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackAccess(bookmark.id)}
              className="font-medium text-gray-900 dark:text-white hover:text-primary-600 dark:hover:text-primary-400 line-clamp-2 block text-base"
            >
              {title}
            </a>
            <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
              {bookmark.domain}
            </p>
          </div>

          {/* Menu */}
          <div className="relative">
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            >
              <MoreVertical className="w-5 h-5" />
            </button>

            {showMenu && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setShowMenu(false)}
                />
                <div className="absolute right-0 top-8 z-20 w-48 bg-white dark:bg-gray-700 rounded-lg shadow-lg border border-gray-200 dark:border-gray-600 py-1">
                  {isFailed && (
                    <button
                      onClick={handleRetry}
                      className="w-full flex items-center gap-2 px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                    >
                      <RefreshCw className="w-4 h-4" />
                      Retry Enrichment
                    </button>
                  )}
                  <button
                    onClick={() => {
                      setEditingBookmark(bookmark)
                      setShowMenu(false)
                    }}
                    className="w-full flex items-center gap-2 px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                  >
                    <Edit2 className="w-4 h-4" />
                    Edit
                  </button>
                  <button
                    onClick={handleDelete}
                    className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-600"
                  >
                    <Trash2 className="w-4 h-4" />
                    Delete
                  </button>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Enrichment Status */}
        {isEnriching && (
          <div className="mt-3 flex items-center gap-2 px-3 py-2 bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400 rounded-lg text-sm">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Analyzing content...</span>
          </div>
        )}

        {isFailed && (
          <div className="mt-3 flex items-center justify-between px-3 py-2 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg text-sm">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              <span>Enrichment failed</span>
            </div>
            <button
              onClick={handleRetry}
              className="flex items-center gap-1 px-2 py-1 bg-red-100 dark:bg-red-900/40 hover:bg-red-200 dark:hover:bg-red-900/60 rounded text-xs font-medium"
            >
              <RefreshCw className="w-3 h-3" />
              Retry
            </button>
          </div>
        )}

        {/* Summary */}
        {bookmark.ai_summary && (
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
            {bookmark.ai_summary}
          </p>
        )}

        {/* Tags */}
        {bookmark.auto_tags && bookmark.auto_tags.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5 items-center">
            {bookmark.auto_tags.slice(0, 5).map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  onTagClick?.(tag)
                }}
                className="inline-flex items-center px-2 py-0.5 text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
              >
                {tag}
              </button>
            ))}
            {bookmark.auto_tags.length > 5 && (
              <span className="text-[10px] font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wider ml-0.5">
                +{bookmark.auto_tags.length - 5} more
              </span>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="mt-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button
              onClick={handleOpen}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-primary-600 dark:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/20 rounded-lg transition-colors cursor-pointer"
            >
              <ExternalLink className="w-4 h-4" />
              Open
            </button>

            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors cursor-pointer"
            >
              <Copy className="w-4 h-4" />
              {copied ? 'Copied!' : 'Copy'}
            </button>

          </div>

          {/* Meta */}
          <div className="text-[11px] text-gray-400">
            {isDeleting ? 'Deleting…' : formatDate(bookmark.created_at)}
          </div>
        </div>
      </div>
    </div>
  )
})

export default BookmarkCard
