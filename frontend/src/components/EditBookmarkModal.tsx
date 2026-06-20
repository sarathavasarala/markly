import { useEffect, useState } from 'react'
import { X, Loader2, AlertCircle, Folder as FolderIcon } from 'lucide-react'
import { Bookmark } from '../lib/api'
import { useBookmarksStore } from '../stores/bookmarksStore'
import { useFolderStore } from '../stores/folderStore'

interface EditBookmarkModalProps {
    bookmark: Bookmark | null
    onClose: () => void
}

export default function EditBookmarkModal({ bookmark, onClose }: EditBookmarkModalProps) {
    const [editTitle, setEditTitle] = useState('')
    const [editSummary, setEditSummary] = useState('')
    const [editThumbnail, setEditThumbnail] = useState('')
    const [editTags, setEditTags] = useState<string[]>([])
    const [editFolderId, setEditFolderId] = useState<string | null>(null)
    const [newTag, setNewTag] = useState('')
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [error, setError] = useState('')

    const { folders } = useFolderStore()
    const updateBookmark = useBookmarksStore((state) => state.updateBookmark)

    useEffect(() => {
        if (bookmark) {
            setEditTitle(bookmark.clean_title || bookmark.original_title || '')
            setEditSummary(bookmark.ai_summary || '')
            setEditThumbnail(bookmark.thumbnail_url || '')
            setEditTags(bookmark.auto_tags || [])
            setEditFolderId(bookmark.folder_id || null)
        }
    }, [bookmark])

    const handleFinish = async () => {
        if (!bookmark) return
        setIsSubmitting(true)
        setError('')

        const finalTags = [...editTags]
        const tag = newTag.trim().toLowerCase().replace(/\s+/g, '-')
        if (tag && !finalTags.includes(tag)) {
            finalTags.push(tag)
        }

        try {
            await updateBookmark(bookmark.id, {
                clean_title: editTitle,
                ai_summary: editSummary,
                auto_tags: finalTags,
                thumbnail_url: editThumbnail || null,
                folder_id: editFolderId,
            })
            onClose()
        } catch (err: any) {
            setError(err.response?.data?.error || 'Failed to save changes')
            setIsSubmitting(false)
        }
    }

    const addTag = (e?: React.FormEvent) => {
        e?.preventDefault()
        const tag = newTag.trim().toLowerCase().replace(/\s+/g, '-')
        if (tag && !editTags.includes(tag)) {
            setEditTags([...editTags, tag])
            setNewTag('')
        }
    }

    const removeTag = (tagToRemove: string) => {
        setEditTags(editTags.filter(t => t !== tagToRemove))
    }

    if (!bookmark) return null

    const labelClass = "block text-xs font-medium text-slate-500 dark:text-slate-400 mb-2"
    const inputClass = "w-full px-4 py-3 rounded-2xl bg-white/80 ring-1 ring-slate-200 text-slate-900 placeholder-slate-400 outline-none transition focus:ring-2 focus:ring-slate-300 dark:bg-slate-900/60 dark:ring-slate-700 dark:text-slate-100 dark:placeholder-slate-500 dark:focus:ring-slate-700/40"

    return (
        <div className="fixed inset-0 z-50 overflow-y-auto">
            <div className="fixed inset-0 bg-slate-950/40 backdrop-blur-sm transition-opacity" onClick={onClose} />
            <div className="flex min-h-full items-center justify-center p-4">
                <div className="relative w-full max-w-2xl rounded-card bg-surface-light shadow-card-hover ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/10 overflow-hidden p-7 sm:p-8">
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="font-display text-2xl text-slate-950 dark:text-slate-50">Edit bookmark</h2>
                        <button onClick={onClose} className="p-2 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 dark:hover:text-slate-200 dark:hover:bg-slate-800 transition-colors">
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    <div className="space-y-5">
                        <div>
                            <label className={labelClass}>Title</label>
                            <input type="text" value={editTitle} onChange={(e) => setEditTitle(e.target.value)} className={inputClass} />
                        </div>

                        <div>
                            <label className={labelClass}>Summary</label>
                            <textarea value={editSummary} onChange={(e) => setEditSummary(e.target.value)} rows={4} className={`${inputClass} resize-none text-sm leading-relaxed`} />
                        </div>

                        <div>
                            <label className={labelClass}>Folder</label>
                            <div className="relative">
                                <select
                                    value={editFolderId || ''}
                                    onChange={(e) => setEditFolderId(e.target.value || null)}
                                    className={`${inputClass} appearance-none pr-12`}
                                >
                                    <option value="">No folder (unfiled)</option>
                                    {folders.map(f => (
                                        <option key={f.id} value={f.id}>{f.name}</option>
                                    ))}
                                </select>
                                <FolderIcon className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none w-4 h-4 text-slate-400" />
                            </div>

                            {!editFolderId && bookmark.suggested_folder_name && (
                                <div className="mt-2.5 px-3 py-2 rounded-xl bg-slate-100/70 dark:bg-slate-800/60 flex items-center justify-between text-sm">
                                    <span className="text-slate-600 dark:text-slate-300">
                                        Suggested: <span className="text-slate-900 dark:text-slate-100">{bookmark.suggested_folder_name}</span>
                                    </span>
                                    <button
                                        onClick={() => {
                                            const suggested = folders.find(f => f.name === bookmark.suggested_folder_name)
                                            if (suggested) setEditFolderId(suggested.id)
                                        }}
                                        className="text-xs font-medium text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
                                    >
                                        Apply
                                    </button>
                                </div>
                            )}
                        </div>

                        <div>
                            <label className={labelClass}>Topics</label>
                            <div className="flex flex-wrap gap-2 mb-3">
                                {editTags.map(tag => (
                                    <span key={tag} className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium lowercase bg-white text-slate-600 ring-1 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700">
                                        {tag}
                                        <button onClick={() => removeTag(tag)} className="text-slate-400 hover:text-rose-500 transition-colors">
                                            <X className="w-3 h-3" />
                                        </button>
                                    </span>
                                ))}
                            </div>
                            <form onSubmit={addTag} className="flex gap-2">
                                <input
                                    type="text"
                                    value={newTag}
                                    onChange={(e) => setNewTag(e.target.value)}
                                    placeholder="Add a topic…"
                                    className={`${inputClass} py-2.5`}
                                />
                            </form>
                        </div>
                    </div>

                    {error && (
                        <div className="mt-5 px-4 py-3 rounded-2xl bg-rose-50 text-rose-700 text-sm flex items-center gap-2 dark:bg-rose-900/20 dark:text-rose-300">
                            <AlertCircle className="w-4 h-4" />
                            {error}
                        </div>
                    )}

                    <div className="mt-7 flex gap-3 pt-5 border-t border-slate-200/70 dark:border-slate-800/70">
                        <button onClick={onClose} className="flex-1 py-3 rounded-full text-sm font-medium text-slate-600 hover:bg-slate-100/70 dark:text-slate-300 dark:hover:bg-slate-800/60 transition-colors">
                            Cancel
                        </button>
                        <button
                            onClick={handleFinish}
                            disabled={isSubmitting}
                            className="flex-[2] py-3 rounded-full text-sm font-medium bg-slate-900 text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                        >
                            {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save changes'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}
