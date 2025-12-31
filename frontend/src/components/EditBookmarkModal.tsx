import { useEffect, useState } from 'react'
import { X, Loader2, CheckCircle2, AlertCircle, Folder as FolderIcon, Sparkles } from 'lucide-react'
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

    return (
        <div className="fixed inset-0 z-50 overflow-y-auto">
            <div className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity" onClick={onClose} />
            <div className="flex min-h-full items-center justify-center p-4">
                <div className="relative w-full max-w-2xl bg-white dark:bg-gray-900 rounded-2xl shadow-2xl overflow-hidden p-8">
                    <div className="flex items-center justify-between mb-8">
                        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Edit Bookmark</h2>
                        <button onClick={onClose} className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors">
                            <X className="w-6 h-6" />
                        </button>
                    </div>

                    <div className="space-y-6">
                        <div>
                            <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Title</label>
                            <input
                                type="text"
                                value={editTitle}
                                onChange={(e) => setEditTitle(e.target.value)}
                                className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 outline-none transition-all font-medium"
                            />
                        </div>

                        <div>
                            <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Summary</label>
                            <textarea
                                value={editSummary}
                                onChange={(e) => setEditSummary(e.target.value)}
                                rows={4}
                                className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 outline-none transition-all resize-none text-sm leading-relaxed"
                            ></textarea>
                        </div>

                        <div>
                            <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Folder</label>
                            <div className="relative">
                                <select
                                    value={editFolderId || ''}
                                    onChange={(e) => setEditFolderId(e.target.value || null)}
                                    className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 outline-none transition-all appearance-none font-medium"
                                >
                                    <option value="">No Folder (Unfiled)</option>
                                    {folders.map(f => (
                                        <option key={f.id} value={f.id}>{f.name}</option>
                                    ))}
                                </select>
                                <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">
                                    <FolderIcon className="w-5 h-5" />
                                </div>
                            </div>

                            {!editFolderId && bookmark.suggested_folder_name && (
                                <div className="mt-3 p-3 bg-primary-50/50 dark:bg-primary-900/10 border border-primary-100 dark:border-primary-900/20 rounded-xl flex items-center justify-between">
                                    <div className="flex items-center gap-2 text-sm">
                                        <Sparkles className="w-4 h-4 text-primary-500" />
                                        <span className="text-gray-600 dark:text-gray-300">
                                            AI suggests: <span className="font-bold text-primary-700 dark:text-primary-400">{bookmark.suggested_folder_name}</span>
                                        </span>
                                    </div>
                                    <button
                                        onClick={() => {
                                            const suggested = folders.find(f => f.name === bookmark.suggested_folder_name)
                                            if (suggested) setEditFolderId(suggested.id)
                                        }}
                                        className="text-xs font-bold text-primary-600 hover:text-primary-700 underline"
                                    >
                                        Apply
                                    </button>
                                </div>
                            )}
                        </div>

                        <div>
                            <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Tags / Topics</label>
                            <div className="flex flex-wrap gap-2 mb-3">
                                {editTags.map(tag => (
                                    <span key={tag} className="inline-flex items-center gap-1 px-3 py-1 bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400 rounded-full text-xs font-bold border border-primary-100 dark:border-primary-800/50">
                                        {tag}
                                        <button onClick={() => removeTag(tag)} className="hover:text-red-500 transition-colors">
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
                                    placeholder="Add a custom tag..."
                                    className="flex-1 px-4 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm outline-none focus:ring-2 focus:ring-primary-500"
                                />
                            </form>
                        </div>
                    </div>

                    {error && (
                        <div className="mt-6 p-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm rounded-xl border border-red-100 dark:border-red-900/30 flex items-center gap-2">
                            <AlertCircle className="w-5 h-5" />
                            {error}
                        </div>
                    )}

                    <div className="mt-8 flex gap-4 pt-6 border-t border-gray-100 dark:border-gray-800">
                        <button onClick={onClose} className="flex-1 px-6 py-4 text-gray-600 dark:text-gray-400 font-bold hover:bg-gray-50 dark:hover:bg-gray-800 rounded-xl transition-colors">
                            Cancel
                        </button>
                        <button
                            onClick={handleFinish}
                            disabled={isSubmitting}
                            className="flex-[2] py-4 bg-primary-600 text-white rounded-xl font-bold transition-all shadow-xl hover:shadow-primary-500/20 active:scale-[0.98] flex items-center justify-center gap-2"
                        >
                            {isSubmitting ? <Loader2 className="w-5 h-5 animate-spin" /> : <><CheckCircle2 className="w-5 h-5" /> Save Changes</>}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}
