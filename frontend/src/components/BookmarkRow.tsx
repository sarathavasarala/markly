import { ExternalLink, MoreVertical, Trash2, Edit2, Folder as FolderIcon, Loader2, BookOpen, RefreshCw } from 'lucide-react'
import MoveToFolderModal from './MoveToFolderModal'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bookmark, bookmarksApi } from '../lib/api'
import { useBookmarksStore } from '../stores/bookmarksStore'
import { useUIStore } from '../stores/uiStore'

interface BookmarkRowProps {
    bookmark: Bookmark
    onDeleted?: (id: string) => void
    onTagClick?: (tag: string) => void
}

export default function BookmarkRow({ bookmark, onDeleted, onTagClick }: BookmarkRowProps) {
    const [showMenu, setShowMenu] = useState(false)
    const [showFolderModal, setShowFolderModal] = useState(false)
    const navigate = useNavigate()
    const { deleteBookmark, updateBookmark } = useBookmarksStore()
    const setEditingBookmark = useUIStore((state) => state.setEditingBookmark)

    const title = bookmark.clean_title || bookmark.original_title || bookmark.url
    const date = new Date(bookmark.created_at).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric'
    })

    const handleMove = async (folderId: string | null) => {
        try {
            await updateBookmark(bookmark.id, { folder_id: folderId })
        } catch (err) {
            console.error(err)
        }
    }

    return (
        <div className="group flex items-center gap-4 border-b border-slate-200/70 px-4 py-3 transition-colors hover:bg-white/60 dark:border-slate-800/80 dark:hover:bg-slate-900/60">
            {/* Favicon */}
            <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-white shadow-inner dark:border-slate-700 dark:bg-slate-800">
                <img
                    src={bookmark.favicon_url || `https://www.google.com/s2/favicons?domain=${bookmark.domain}&sz=64`}
                    alt=""
                    className="h-4 w-4 object-contain"
                    onError={(e) => {
                        const target = e.target as HTMLImageElement;
                        target.src = `https://www.google.com/s2/favicons?domain=${bookmark.domain}&sz=64`;
                    }}
                />
            </div>

            {/* Title & Domain */}
            <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2">
                    <a
                        href={bookmark.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="truncate font-display text-base font-normal text-slate-950 transition-colors hover:text-indigo-700 dark:text-slate-50 dark:hover:text-indigo-300"
                    >
                        {title}
                    </a>
                    <span className="shrink-0 text-xs text-slate-500 dark:text-slate-400">{bookmark.domain}</span>
                    {(bookmark.archive_status === 'pending' || bookmark.archive_status === 'processing') && (
                        <span className="flex items-center gap-1 text-[11px] text-indigo-500 dark:text-indigo-400 ml-2">
                            <Loader2 className="h-2.5 w-2.5 animate-spin" /> Saving copy...
                        </span>
                    )}
                </div>
            </div>

            {/* Tags */}
            <div className="hidden max-w-[30%] items-center gap-1.5 overflow-hidden md:flex">
                {bookmark.auto_tags?.slice(0, 3).map(tag => (
                    <button
                        key={tag}
                        onClick={() => onTagClick?.(tag)}
                        className="rounded-full bg-white px-2.5 py-1 text-xs font-medium lowercase text-slate-500 ring-1 ring-slate-200 transition-all hover:text-slate-800 hover:ring-slate-300 dark:bg-slate-800 dark:text-slate-400 dark:ring-slate-700 dark:hover:text-slate-200"
                    >
                        {tag}
                    </button>
                ))}
            </div>

            {/* Date */}
            <div className="hidden w-16 text-right text-xs text-slate-400 dark:text-slate-500 sm:block">
                {date}
            </div>

            {/* Actions */}
            <div className="relative">
                <button
                    onClick={() => setShowMenu(!showMenu)}
                    className="rounded-full p-2 text-slate-400 opacity-0 transition-all hover:bg-white hover:text-slate-700 group-hover:opacity-100 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                >
                    <MoreVertical className="h-4 w-4" />
                </button>

                {showMenu && (
                    <>
                        <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
                        <div className="absolute right-0 top-10 z-20 w-48 overflow-hidden rounded-2xl border border-slate-200 bg-white py-2 shadow-xl animate-in fade-in zoom-in duration-200 dark:border-slate-700 dark:bg-slate-800">
                            {bookmark.archive_status === 'completed' && (
                                <button
                                    onClick={() => {
                                        navigate(`/bookmarks/${bookmark.id}/read`)
                                        setShowMenu(false)
                                    }}
                                    className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-700"
                                >
                                    <BookOpen className="h-3.5 w-3.5" /> Read saved copy
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
                                    className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-700"
                                >
                                    <RefreshCw className="h-3.5 w-3.5" /> Retry saved copy
                                </button>
                            )}
                            <button
                                onClick={() => {
                                    window.open(bookmark.url, '_blank')
                                    setShowMenu(false)
                                }}
                                className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-700"
                            >
                                <ExternalLink className="h-3.5 w-3.5" /> Open link
                            </button>
                            <button
                                onClick={() => {
                                    setEditingBookmark(bookmark)
                                    setShowMenu(false)
                                }}
                                className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-700"
                            >
                                <Edit2 className="h-3.5 w-3.5" /> Edit
                            </button>

                            <button
                                onClick={() => {
                                    setShowFolderModal(true)
                                    setShowMenu(false)
                                }}
                                className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-700"
                            >
                                <FolderIcon className="h-3.5 w-3.5" /> Move to folder
                            </button>

                            <div className="my-1 h-px bg-slate-100 dark:bg-slate-700" />
                            <button
                                onClick={async () => {
                                    if (window.confirm('Delete bookmark?')) {
                                        await deleteBookmark(bookmark.id)
                                        onDeleted?.(bookmark.id)
                                    }
                                    setShowMenu(false)
                                }}
                                className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-xs font-medium text-red-600 transition-colors hover:bg-red-50 dark:hover:bg-red-900/20"
                            >
                                <Trash2 className="h-3.5 w-3.5" /> Delete
                            </button>
                        </div>
                    </>
                )}
            </div>
            <MoveToFolderModal
                isOpen={showFolderModal}
                onClose={() => setShowFolderModal(false)}
                currentFolderId={bookmark.folder_id}
                onSelect={handleMove}
            />
        </div>
    )
}
