import {
  ExternalLink,
  Copy,
  Loader2,
  AlertCircle,
  RefreshCw,
  MoreVertical,
  Trash2,
  Edit2,
  Eye,
  EyeOff,
  Plus,
  Check,
  Folder as FolderIcon,
  BookOpen
} from 'lucide-react'
import { useState, memo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bookmark, bookmarksApi } from '../lib/api'
import { useBookmarksStore } from '../stores/bookmarksStore'
import { useUIStore } from '../stores/uiStore'
import { useAuthStore } from '../stores/authStore'
import MoveToFolderModal from './MoveToFolderModal'

interface BookmarkCardProps {
  bookmark: Bookmark
  isOwner?: boolean
  isPublicView?: boolean
  onDeleted?: (id: string) => void
  onTagClick?: (tag: string) => void
  onVisibilityToggle?: (bookmark: Bookmark) => void
  onSave?: (bookmark: Bookmark) => void
  isSaving?: boolean
}

const BookmarkCard = memo(function BookmarkCard({
  bookmark,
  isOwner = true,
  isPublicView = false,
  onDeleted,
  onTagClick,
  onVisibilityToggle,
  onSave,
  isSaving = false,
}: BookmarkCardProps) {
  const [showMenu, setShowMenu] = useState(false)
  const [copied, setCopied] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [showFolderModal, setShowFolderModal] = useState(false)
  const navigate = useNavigate()

  const { trackAccess, retryEnrichment, deleteBookmark, updateBookmark } = useBookmarksStore()
  const setEditingBookmark = useUIStore((state) => state.setEditingBookmark)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

  const title = bookmark.clean_title || bookmark.original_title || bookmark.url
  const isEnriching = bookmark.enrichment_status === 'pending' || bookmark.enrichment_status === 'processing'
  const isFailed = bookmark.enrichment_status === 'failed'

  const handleOpen = () => {
    if (isAuthenticated) {
      trackAccess(bookmark.id)
    }
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

  const handleMoveToFolder = async (folderId: string | null) => {
    try {
      await updateBookmark(bookmark.id, { folder_id: folderId })
      setShowMenu(false)
    } catch (err) {
      console.error('Failed to move bookmark:', err)
    }
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
    return d.toLocaleDateString()
  }

  return (
    <div className={`group relative w-full overflow-hidden break-inside-avoid rounded-card bg-surface-light text-sm shadow-card ring-1 ring-white/60 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-card-hover dark:bg-surface-dark dark:ring-white/5 ${!bookmark.is_public && isPublicView ? 'hidden' : ''}`}>
      {/* Thumbnail */}
      {bookmark.thumbnail_url && (
        <div className="p-3 pb-0">
          <img
            src={bookmark.thumbnail_url.replace(/^http:\/\//, 'https://')}
            alt=""
            className="h-36 w-full rounded-[1.25rem] object-cover"
            onError={(e) => {
              const container = (e.target as HTMLImageElement).parentElement;
              if (container) container.style.display = 'none';
            }}
          />
        </div>
      )}

      <div className="p-5">
        {/* Header */}
        <div className="mb-4 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <div className="flex min-w-0 items-center gap-2">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-white shadow-inner dark:border-slate-700 dark:bg-slate-800">
              <img
                src={bookmark.favicon_url || `https://www.google.com/s2/favicons?domain=${bookmark.domain}&sz=64`}
                alt=""
                className="h-4 w-4 object-contain"
                onError={(e) => {
                  const target = e.target as HTMLImageElement;
                  if (!target.src.includes('BookMarked')) {
                    target.src = `https://www.google.com/s2/favicons?domain=${bookmark.domain}&sz=64`;
                  }
                }}
              />
            </div>
            <span className="truncate font-medium">{bookmark.domain}</span>
          </div>
          <span className="ml-auto shrink-0 text-slate-400 dark:text-slate-500">{formatDate(bookmark.created_at)}</span>

          <div className="relative -mr-2">
            {!isPublicView && (
              <>
                <button
                  onClick={() => setShowMenu(!showMenu)}
                  className="rounded-full p-2 text-slate-400 opacity-0 transition-all hover:bg-white hover:text-slate-700 group-hover:opacity-100 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                  aria-label="Bookmark actions"
                >
                  <MoreVertical className="w-4 h-4" />
                </button>

                {showMenu && (
                  <>
                    <div
                      className="fixed inset-0 z-10"
                      onClick={() => setShowMenu(false)}
                    />
                    <div className="absolute right-0 top-10 z-20 w-48 overflow-hidden rounded-2xl border border-slate-200 bg-white py-2 shadow-xl animate-in fade-in zoom-in duration-200 dark:border-slate-700 dark:bg-slate-800">
                      {bookmark.archive_status === 'completed' && (
                        <button
                          onClick={() => {
                            navigate(`/bookmarks/${bookmark.id}/read`)
                            setShowMenu(false)
                          }}
                          className="flex w-full items-center gap-3 px-4 py-2.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-700"
                        >
                          <BookOpen className="w-4 h-4" />
                          Read saved copy
                        </button>
                      )}
                      {bookmark.archive_status === 'failed' && (
                        <button
                          onClick={() => {
                            bookmarksApi.retryArchive(bookmark.id).then(() => {
                              updateBookmark(bookmark.id, { archive_status: 'pending', archive_error: null })
                            }).catch(err => console.error("Failed to retry archiving:", err))
                            setShowMenu(false)
                          }}
                          className="flex w-full items-center gap-3 px-4 py-2.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-700"
                        >
                          <RefreshCw className="w-4 h-4" />
                          Retry saved copy
                        </button>
                      )}
                      {isFailed && (
                        <button
                          onClick={handleRetry}
                          className="flex w-full items-center gap-3 px-4 py-2.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-700"
                        >
                          <RefreshCw className="w-4 h-4" />
                          Retry enrichment
                        </button>
                      )}
                      <button
                        onClick={() => {
                          setEditingBookmark(bookmark)
                          setShowMenu(false)
                        }}
                        className="flex w-full items-center gap-3 px-4 py-2.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-700"
                      >
                        <Edit2 className="w-4 h-4" />
                        Edit bookmark
                      </button>

                      <button
                        onClick={() => {
                          setShowFolderModal(true)
                          setShowMenu(false)
                        }}
                        className="flex w-full items-center gap-3 px-4 py-2.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-700"
                      >
                        <FolderIcon className="w-4 h-4" />
                        Move to folder
                      </button>

                      <div className="my-1 h-px bg-slate-100 dark:bg-slate-700" />
                      <button
                        onClick={handleDelete}
                        className="flex w-full items-center gap-3 px-4 py-2.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 dark:hover:bg-red-900/20"
                      >
                        <Trash2 className="w-4 h-4" />
                        Delete
                      </button>
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </div>

        {/* Enrichment Status */}
        {isEnriching && (
          <div className="mb-4 flex items-center gap-2 rounded-2xl bg-slate-100 px-3 py-2 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>Analyzing content...</span>
          </div>
        )}

        {/* Archive Status */}
        {(bookmark.archive_status === 'pending' || bookmark.archive_status === 'processing') && (
          <div className="mb-4 flex items-center gap-2 rounded-2xl bg-indigo-50/50 px-3 py-2 text-xs font-medium text-indigo-600 dark:bg-indigo-950/10 dark:text-indigo-400">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>Saving copy...</span>
          </div>
        )}

        {isFailed && (
          <div className="mb-4 flex items-center justify-between rounded-2xl bg-red-50 px-3 py-2 text-xs font-medium text-red-600 dark:bg-red-900/10 dark:text-red-400">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-3 h-3" />
              <span>Failed</span>
            </div>
            <button
              onClick={handleRetry}
              className="rounded-full bg-red-100 px-2 py-0.5 transition-colors hover:bg-red-200 dark:bg-red-900/30 dark:hover:bg-red-900/50"
            >
              Retry
            </button>
          </div>
        )}

        {/* Title */}
        <h3 className="mb-2 font-display text-[1.4rem] font-normal leading-tight text-slate-950 transition-colors group-hover:text-indigo-700 dark:text-slate-50 dark:group-hover:text-indigo-300">
          <a
            href={bookmark.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => {
              if (isAuthenticated) {
                trackAccess(bookmark.id)
              }
            }}
            className="transition-colors"
          >
            {title}
          </a>
        </h3>

        {/* Summary */}
        {bookmark.ai_summary && (
          <p className="mb-5 text-sm font-normal leading-6 text-slate-600 dark:text-slate-400">
            {bookmark.ai_summary}
          </p>
        )}

        {/* Tags */}
        {bookmark.auto_tags && bookmark.auto_tags.length > 0 && (
          <div className="mb-5 flex flex-wrap gap-1.5">
            {bookmark.auto_tags.slice(0, 3).map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  onTagClick?.(tag)
                }}
                className="rounded-full bg-white px-2.5 py-1 text-xs font-medium lowercase text-slate-500 ring-1 ring-slate-200 transition-all hover:text-slate-800 hover:ring-slate-300 dark:bg-slate-800 dark:text-slate-400 dark:ring-slate-700 dark:hover:text-slate-200"
              >
                {tag}
              </button>
            ))}
            {bookmark.auto_tags.length > 3 && (
              <span className="px-2 py-1 text-xs font-medium lowercase text-slate-400 dark:text-slate-500">
                + {bookmark.auto_tags.length - 3} more
              </span>
            )}
          </div>
        )}

        {/* Actions Footer */}
        <div className="mt-auto flex items-center gap-3 border-t border-slate-200/70 pt-4 dark:border-slate-800">
          {isPublicView && !isOwner ? (
            bookmark.is_saved_by_viewer ? (
              <button
                disabled
                className="flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700 ring-1 ring-emerald-200 cursor-not-allowed dark:bg-emerald-900/10 dark:text-emerald-300 dark:ring-emerald-800"
              >
                <Check className="w-4 h-4" /> In your collection
              </button>
            ) : (
              <button
                onClick={() => onSave?.(bookmark)}
                disabled={isSaving}
                className="flex items-center gap-2 rounded-full bg-slate-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-700 active:scale-95 disabled:cursor-not-allowed disabled:bg-slate-500 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
              >
                {isSaving ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Saving...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" /> Save to collection
                  </>
                )}
              </button>
            )
          ) : (
            <button
              onClick={handleOpen}
              className="flex items-center gap-2 text-sm font-medium text-slate-800 transition hover:text-slate-950 dark:text-slate-200 dark:hover:text-white"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span className="truncate">Open link</span>
            </button>
          )}

          <div className="ml-auto flex shrink-0 items-center gap-1.5">
            {/* Visibility Toggle for Owner */}
            {!isPublicView && isOwner && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onVisibilityToggle?.(bookmark)
                }}
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border transition-all ${bookmark.is_public ? 'border-slate-300 bg-white text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300' : 'border-slate-200 bg-white text-slate-400 hover:text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 dark:hover:text-slate-200'}`}
                title={bookmark.is_public ? 'Public (shared)' : 'Private (locked)'}
              >
                {bookmark.is_public ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
              </button>
            )}

            <button
              onClick={handleCopy}
              className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border transition-all ${copied ? 'border-emerald-200 bg-emerald-50 text-emerald-600 dark:border-emerald-800 dark:bg-emerald-900/10' : 'border-slate-200 bg-white text-slate-400 hover:text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500 dark:hover:text-slate-200'}`}
              title="Copy URL"
            >
              {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>
      <MoveToFolderModal
        isOpen={showFolderModal}
        onClose={() => setShowFolderModal(false)}
        currentFolderId={bookmark.folder_id}
        onSelect={handleMoveToFolder}
      />
    </div>
  )
})

export default BookmarkCard
