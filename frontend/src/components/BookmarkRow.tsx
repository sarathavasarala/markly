import { ExternalLink, MoreVertical, Trash2, Edit2, BookMarked, Folder as FolderIcon } from 'lucide-react'
import MoveToFolderModal from './MoveToFolderModal'
import { useState } from 'react'
import { Bookmark } from '../lib/api'
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
        <div className="group flex items-center gap-4 px-4 py-3 bg-white dark:bg-gray-900 border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
            {/* Favicon */}
            <div className="w-8 h-8 rounded-lg bg-gray-50 dark:bg-gray-800 flex items-center justify-center flex-shrink-0 overflow-hidden">
                <img
                    src={bookmark.favicon_url || `https://www.google.com/s2/favicons?domain=${bookmark.domain}&sz=64`}
                    alt=""
                    className="w-5 h-5 object-contain"
                    onError={(e) => {
                        const target = e.target as HTMLImageElement;
                        // BookMarked fallback is handled by assigning a default icon URL if Google also fails
                        // or just sticking with Google. Google API is very reliable.
                        target.src = `https://www.google.com/s2/favicons?domain=${bookmark.domain}&sz=64`;
                    }}
                />
            </div>

            {/* Title & Domain */}
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <a
                        href={bookmark.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-semibold text-gray-900 dark:text-white truncate hover:text-primary-600 transition-colors"
                    >
                        {title}
                    </a>
                    <span className="text-[10px] font-bold text-gray-400 uppercase tracking-tight">{bookmark.domain}</span>
                </div>
            </div>

            {/* Tags */}
            <div className="hidden md:flex items-center gap-2 max-w-[30%] overflow-hidden">
                {bookmark.auto_tags?.slice(0, 3).map(tag => (
                    <button
                        key={tag}
                        onClick={() => onTagClick?.(tag)}
                        className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 text-[10px] font-medium lowercase rounded-md hover:bg-primary-50 dark:hover:bg-primary-900/20 hover:text-primary-600 transition-colors"
                    >
                        {tag}
                    </button>
                ))}
            </div>

            {/* Date */}
            <div className="hidden sm:block text-[10px] font-bold text-gray-400 w-16 text-right">
                {date}
            </div>

            {/* Actions */}
            <div className="relative">
                <button
                    onClick={() => setShowMenu(!showMenu)}
                    className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-white dark:hover:bg-gray-700 shadow-sm transition-all"
                >
                    <MoreVertical className="w-4 h-4" />
                </button>

                {showMenu && (
                    <>
                        <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
                        <div className="absolute right-0 top-10 z-20 w-48 bg-white dark:bg-gray-800 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 py-2 animate-in fade-in zoom-in duration-200">
                            <button
                                onClick={() => {
                                    window.open(bookmark.url, '_blank')
                                    setShowMenu(false)
                                }}
                                className="w-full text-left px-4 py-2 text-xs font-bold text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2"
                            >
                                <ExternalLink className="w-3.5 h-3.5" /> OPEN LINK
                            </button>
                            <button
                                onClick={() => {
                                    setEditingBookmark(bookmark)
                                    setShowMenu(false)
                                }}
                                className="w-full text-left px-4 py-2 text-xs font-bold text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2"
                            >
                                <Edit2 className="w-3.5 h-3.5" /> EDIT
                            </button>

                            <button
                                onClick={() => {
                                    setShowFolderModal(true)
                                    setShowMenu(false)
                                }}
                                className="w-full text-left px-4 py-2 text-xs font-bold text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2"
                            >
                                <FolderIcon className="w-3.5 h-3.5" /> MOVE TO FOLDER
                            </button>

                            <div className="h-px bg-gray-100 dark:bg-gray-700 my-1" />
                            <button
                                onClick={async () => {
                                    if (window.confirm('Delete bookmark?')) {
                                        await deleteBookmark(bookmark.id)
                                        onDeleted?.(bookmark.id)
                                    }
                                    setShowMenu(false)
                                }}
                                className="w-full text-left px-4 py-2 text-xs font-bold text-red-600 hover:bg-red-50 dark:hover:bg-red-900/10 flex items-center gap-2"
                            >
                                <Trash2 className="w-3.5 h-3.5" /> DELETE
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
