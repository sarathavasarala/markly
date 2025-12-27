import { useEffect, useState } from 'react'
import { X, Loader2, CheckCircle2, Plus, AlertCircle } from 'lucide-react'
import { Bookmark } from '../lib/api'
import { useBookmarksStore } from '../stores/bookmarksStore'

interface EditBookmarkModalProps {
    bookmark: Bookmark | null
    onClose: () => void
}

export default function EditBookmarkModal({ bookmark, onClose }: EditBookmarkModalProps) {
    const [editTitle, setEditTitle] = useState('')
    const [editSummary, setEditSummary] = useState('')
    const [editThumbnail, setEditThumbnail] = useState('')
    const [editTags, setEditTags] = useState<string[]>([])
    const [newTag, setNewTag] = useState('')
    const [isSubmitting, setIsSubmitting] = useState(false)
    const [error, setError] = useState('')

    const updateBookmark = useBookmarksStore((state) => state.updateBookmark)

    useEffect(() => {
        if (bookmark) {
            setEditTitle(bookmark.clean_title || bookmark.original_title || '')
            setEditSummary(bookmark.ai_summary || '')
            setEditThumbnail(bookmark.thumbnail_url || '')
            setEditTags(bookmark.auto_tags || [])
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
                            />
                        </div>

                        <div>
                            <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Thumbnail URL</label>
                            <div className="flex gap-3">
                                <input
                                    type="text"
                                    value={editThumbnail}
                                    onChange={(e) => setEditThumbnail(e.target.value)}
                                    placeholder="https://example.com/image.jpg"
                                    className="flex-1 px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 outline-none transition-all text-sm"
                                />
                                {editThumbnail && (
                                    <div className="w-12 h-12 rounded-lg bg-gray-100 dark:bg-gray-800 overflow-hidden border border-gray-200 dark:border-gray-700 flex-shrink-0">
                                        <img src={editThumbnail} alt="" className="w-full h-full object-cover" />
                                    </div>
                                )}
                            </div>
                        </div>

                        <div>
                            <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Tags / Topics</label>
                            <div className="flex flex-wrap gap-2 mb-3">
                                {editTags.map(tag => (
                                    <span key={tag} className="inline-flex items-center gap-1 px-3 py-1 bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400 rounded-full text-xs font-bold border border-primary-100 dark:border-primary-800/50 group">
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
                                <button type="submit" className="p-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg text-gray-500 dark:text-gray-400 transition-colors">
                                    <Plus className="w-5 h-5" />
                                </button>
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
                        <button
                            onClick={onClose}
                            className="flex-1 px-6 py-4 text-gray-600 dark:text-gray-400 font-bold hover:bg-gray-50 dark:hover:bg-gray-800 rounded-xl transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleFinish}
                            disabled={isSubmitting}
                            className="flex-[2] py-4 bg-primary-600 text-white rounded-xl font-bold transition-all shadow-xl hover:shadow-primary-500/20 active:scale-[0.98] flex items-center justify-center gap-2"
                        >
                            {isSubmitting ? (
                                <Loader2 className="w-5 h-5 animate-spin" />
                            ) : (
                                <>
                                    <CheckCircle2 className="w-5 h-5" />
                                    Save Changes
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}
