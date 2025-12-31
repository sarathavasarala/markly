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
  BookMarked,
  Folder as FolderIcon
} from 'lucide-react'
import { useState, memo } from 'react'
import { Bookmark } from '../lib/api'
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
  const [titleHovered, setTitleHovered] = useState(false)
  const [showFolderModal, setShowFolderModal] = useState(false)

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
    <div className={`group bg-white dark:bg-gray-900/40 border-2 rounded-2xl overflow-hidden transition-all duration-300 break-inside-avoid w-full text-sm ${titleHovered ? 'border-primary-500/50 shadow-2xl shadow-primary-500/10' : 'border-gray-100 dark:border-gray-800'} ${!bookmark.is_public && isPublicView ? 'hidden' : ''} ${!bookmark.is_public && !isPublicView && isOwner ? 'opacity-70 bg-gray-50/50 dark:bg-gray-900/20 border-dashed' : ''}`}>
      {/* Thumbnail */}
      {bookmark.thumbnail_url && (
        <div className="h-40 bg-gray-100 dark:bg-gray-800 overflow-hidden">
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

      <div className="p-4 sm:p-5">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 bg-gray-50 dark:bg-gray-800 rounded-xl flex items-center justify-center shrink-0 shadow-inner border border-gray-100 dark:border-gray-700">
              {bookmark.favicon_url ? (
                <img
                  src={bookmark.favicon_url}
                  alt=""
                  className="w-6 h-6 object-contain"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = `https://www.google.com/s2/favicons?domain=${bookmark.domain}&sz=64`
                  }}
                />
              ) : (
                <BookMarked className="w-5 h-5 text-gray-400" />
              )}
            </div>
            <div className="min-w-0">
              <p className="text-gray-500 dark:text-gray-400 text-[10px] font-black uppercase tracking-widest truncate">{bookmark.domain}</p>
              <p className="text-gray-400 dark:text-gray-600 text-[9px] font-bold mt-0 uppercase tracking-tighter">{formatDate(bookmark.created_at)}</p>
            </div>
          </div>

          {/* User Actions (Menu) */}
          <div className="flex items-center gap-1">
            {!isPublicView && (
              <div className="relative">
                <button
                  onClick={() => setShowMenu(!showMenu)}
                  className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
                >
                  <MoreVertical className="w-4 h-4" />
                </button>

                {showMenu && (
                  <>
                    <div
                      className="fixed inset-0 z-10"
                      onClick={() => setShowMenu(false)}
                    />
                    <div className="absolute right-0 top-10 z-20 w-48 bg-white dark:bg-gray-800 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 py-2 overflow-hidden animate-in fade-in zoom-in duration-200">
                      {isFailed && (
                        <button
                          onClick={handleRetry}
                          className="w-full flex items-center gap-3 px-4 py-2.5 text-xs font-bold text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                        >
                          <RefreshCw className="w-4 h-4" />
                          RETRY ENRICHMENT
                        </button>
                      )}
                      <button
                        onClick={() => {
                          setEditingBookmark(bookmark)
                          setShowMenu(false)
                        }}
                        className="w-full flex items-center gap-3 px-4 py-2.5 text-xs font-bold text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                      >
                        <Edit2 className="w-4 h-4" />
                        EDIT BOOKMARK
                      </button>

                      <button
                        onClick={() => {
                          setShowFolderModal(true)
                          setShowMenu(false)
                        }}
                        className="w-full flex items-center gap-3 px-4 py-2.5 text-xs font-bold text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                      >
                        <FolderIcon className="w-4 h-4" />
                        MOVE TO FOLDER
                      </button>

                      <div className="h-px bg-gray-100 dark:bg-gray-700 my-1" />
                      <button
                        onClick={handleDelete}
                        className="w-full flex items-center gap-3 px-4 py-2.5 text-xs font-bold text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                        DELETE
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Enrichment Status */}
        {isEnriching && (
          <div className="mb-4 flex items-center gap-2 px-3 py-2 bg-primary-50 dark:bg-primary-900/10 text-primary-600 dark:text-primary-400 rounded-xl text-[10px] font-black uppercase tracking-widest">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>Analyzing content...</span>
          </div>
        )}

        {isFailed && (
          <div className="mb-4 flex items-center justify-between px-3 py-2 bg-red-50 dark:bg-red-900/10 text-red-600 dark:text-red-400 rounded-xl text-[10px] font-black uppercase tracking-widest">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-3 h-3" />
              <span>Failed</span>
            </div>
            <button
              onClick={handleRetry}
              className="px-2 py-0.5 bg-red-100 dark:bg-red-900/30 hover:bg-red-200 dark:hover:bg-red-900/50 rounded-lg transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Title */}
        <h3 className="text-gray-900 dark:text-white font-bold text-lg leading-snug mb-3 line-clamp-2">
          <a
            href={bookmark.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => {
              if (isAuthenticated) {
                trackAccess(bookmark.id)
              }
            }}
            onMouseEnter={() => setTitleHovered(true)}
            onMouseLeave={() => setTitleHovered(false)}
            className="hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
          >
            {title}
          </a>
        </h3>

        {/* Summary */}
        {bookmark.ai_summary && (
          <p className="text-gray-600 dark:text-gray-400 text-sm leading-relaxed mb-5 line-clamp-4 font-medium opacity-90">
            {bookmark.ai_summary}
          </p>
        )}

        {/* Tags - Refined lowercase style */}
        {bookmark.auto_tags && bookmark.auto_tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-4">
            {bookmark.auto_tags.slice(0, 5).map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  onTagClick?.(tag)
                }}
                className="px-2 py-0.5 bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 text-[10px] font-medium lowercase rounded-lg border border-gray-100 dark:border-gray-700 transition-all hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                {tag}
              </button>
            ))}
            {bookmark.auto_tags.length > 5 && (
              <span className="px-2 py-1 text-[9px] font-black text-gray-400 dark:text-gray-500 uppercase tracking-tighter">
                +{bookmark.auto_tags.length - 5}
              </span>
            )}
          </div>
        )}

        {/* Actions Footer */}
        <div className="flex items-center gap-2 pt-5 border-t border-gray-50 dark:border-gray-800/50 mt-auto">
          {isPublicView && !isOwner ? (
            bookmark.is_saved_by_viewer ? (
              <button
                disabled
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-green-600 text-white rounded-xl text-[10px] font-black uppercase tracking-widest cursor-not-allowed opacity-90"
              >
                <Check className="w-4 h-4" /> In Your Collection
              </button>
            ) : (
              <button
                onClick={() => onSave?.(bookmark)}
                disabled={isSaving}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-primary-600 hover:bg-primary-500 disabled:bg-primary-400 text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-lg shadow-primary-600/20 active:scale-95 disabled:cursor-not-allowed"
              >
                {isSaving ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Saving...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" /> Save to Collection
                  </>
                )}
              </button>
            )
          ) : (
            <button
              onClick={handleOpen}
              className="flex-1 flex items-center justify-center gap-2 px-3 sm:px-4 py-3 bg-primary-600 dark:bg-primary-600 hover:bg-primary-500 text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-lg shadow-primary-600/20 active:scale-95"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span className="truncate">Open Link</span>
            </button>
          )}

          <div className="flex items-center gap-1.5 shrink-0">
            {/* Visibility Toggle for Owner */}
            {!isPublicView && isOwner && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onVisibilityToggle?.(bookmark)
                }}
                className={`w-11 h-11 flex items-center justify-center rounded-xl transition-all border shrink-0 ${bookmark.is_public ? 'bg-primary-50 dark:bg-primary-900/10 border-primary-200 dark:border-primary-800 text-primary-600' : 'bg-gray-50 dark:bg-gray-800 border-gray-100 dark:border-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'}`}
                title={bookmark.is_public ? 'Public (shared)' : 'Private (locked)'}
              >
                {bookmark.is_public ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
              </button>
            )}

            <button
              onClick={handleCopy}
              className={`w-11 h-11 flex items-center justify-center rounded-xl transition-all border shrink-0 ${copied ? 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800 text-green-600' : 'bg-gray-50 dark:bg-gray-800 border-gray-100 dark:border-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'}`}
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
