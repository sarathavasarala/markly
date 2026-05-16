import { X, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useAuthStore } from '../stores/authStore'
import { bookmarksApi, Bookmark } from '../lib/api'

interface SaveToCollectionModalProps {
    isOpen: boolean
    onClose: () => void
    bookmarkToSave: Bookmark | null
    onSaveSuccess?: () => void
}

export default function SaveToCollectionModal({
    isOpen,
    onClose,
    bookmarkToSave,
    onSaveSuccess,
}: SaveToCollectionModalProps) {
    const { signInWithGoogle, isAuthenticated, isLoading } = useAuthStore()
    const [isSaving, setIsSaving] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const handlePostAuthSave = async () => {
            if (!isAuthenticated || !bookmarkToSave || isSaving) return

            const pendingBookmarkId = localStorage.getItem('pendingBookmarkSave')
            if (pendingBookmarkId === bookmarkToSave.id) {
                setIsSaving(true)
                try {
                    await bookmarksApi.savePublic(bookmarkToSave.id)
                    localStorage.removeItem('pendingBookmarkSave')
                    onSaveSuccess?.()
                    onClose()
                } catch (err: any) {
                    setError(err.response?.data?.error || 'Failed to save bookmark')
                } finally {
                    setIsSaving(false)
                }
            }
        }

        handlePostAuthSave()
    }, [isAuthenticated, bookmarkToSave, onSaveSuccess, onClose, isSaving])

    const handleSignIn = async () => {
        if (!bookmarkToSave) return
        localStorage.setItem('pendingBookmarkSave', bookmarkToSave.id)
        try {
            await signInWithGoogle()
        } catch (err) {
            setError('Sign-in failed. Please try again.')
            localStorage.removeItem('pendingBookmarkSave')
        }
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-50 overflow-y-auto">
            <div
                className="fixed inset-0 bg-slate-950/50 backdrop-blur-sm transition-opacity"
                onClick={onClose}
            />

            <div className="flex min-h-full items-center justify-center p-4">
                <div className="relative w-full max-w-md rounded-card bg-surface-light shadow-card-hover ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 overflow-hidden">
                    <button
                        onClick={onClose}
                        className="absolute top-4 right-4 p-2 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 dark:hover:text-slate-200 dark:hover:bg-slate-800 transition-colors z-10"
                    >
                        <X className="w-5 h-5" />
                    </button>

                    <div className="px-8 pt-10 pb-8">
                        <h2 className="font-display text-3xl text-slate-950 dark:text-slate-50 leading-tight">
                            Save this to your library
                        </h2>
                        <p className="mt-3 text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                            Sign in with Google and we'll add this bookmark to your collection. We'll summarize it and make it searchable so you can come back to it any time.
                        </p>

                        {error && (
                            <div className="mt-5 px-4 py-3 rounded-2xl bg-rose-50 text-rose-700 text-sm dark:bg-rose-900/20 dark:text-rose-300">
                                {error}
                            </div>
                        )}

                        <button
                            onClick={handleSignIn}
                            disabled={isLoading || isSaving}
                            className="mt-7 w-full h-12 flex items-center justify-center gap-3 px-6 rounded-full bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white transition-colors disabled:opacity-50"
                        >
                            {isLoading || isSaving ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    <span>{isSaving ? 'Saving…' : 'Signing in…'}</span>
                                </>
                            ) : (
                                <>
                                    <svg className="w-4 h-4" viewBox="0 0 24 24">
                                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1c-3.17 0-5.92 1.83-7.24 4.5l3.66 2.85c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                                    </svg>
                                    <span>Continue with Google</span>
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}
