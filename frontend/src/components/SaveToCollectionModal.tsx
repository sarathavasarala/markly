import { X, Loader2, Sparkles, Search, Layers } from 'lucide-react'
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

    // Handle post-authentication save
    useEffect(() => {
        const handlePostAuthSave = async () => {
            if (!isAuthenticated || !bookmarkToSave || isSaving) return

            // Check if we just authenticated and need to save
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

        // Store bookmark ID for post-auth save
        localStorage.setItem('pendingBookmarkSave', bookmarkToSave.id)

        try {
            await signInWithGoogle()
        } catch (err) {
            setError('Authentication failed. Please try again.')
            localStorage.removeItem('pendingBookmarkSave')
        }
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-50 overflow-y-auto">
            <div
                className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity"
                onClick={onClose}
            />

            <div className="flex min-h-full items-center justify-center p-4">
                <div className="relative w-full max-w-5xl bg-gradient-to-br from-gray-900 to-gray-950 rounded-3xl shadow-2xl overflow-hidden border border-gray-800">
                    {/* Close button */}
                    <button
                        onClick={onClose}
                        className="absolute top-6 right-6 p-2 text-gray-400 hover:text-white transition-colors z-10 hover:bg-gray-800 rounded-lg"
                    >
                        <X className="w-6 h-6" />
                    </button>

                    {/* Two Column Layout - Desktop, Single Column - Mobile */}
                    <div className="flex flex-col md:flex-row">
                        {/* Left Column - Value Proposition */}
                        <div className="flex-1 p-8 sm:p-12 border-b md:border-b-0 md:border-r border-gray-800">
                            <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-primary-500 to-primary-700 rounded-2xl mb-6 shadow-xl shadow-primary-500/30">
                                <Sparkles className="w-8 h-8 text-white" />
                            </div>

                            <h2 className="text-3xl sm:text-4xl font-black text-white mb-4 tracking-tight">
                                Save this to your collection
                            </h2>

                            <p className="text-gray-400 text-base font-medium mb-10 leading-relaxed">
                                Build your own smart bookmark library. Organize, search, and rediscover great content, all powered by AI.
                            </p>

                            {/* Benefits */}
                            <div className="space-y-5">
                                <div className="flex items-start gap-4">
                                    <div className="w-10 h-10 bg-blue-500/10 rounded-lg flex items-center justify-center shrink-0">
                                        <Layers className="w-5 h-5 text-blue-400" />
                                    </div>
                                    <div>
                                        <h3 className="text-white font-bold mb-1">Organize effortlessly</h3>
                                        <p className="text-gray-400 text-sm">AI auto-tags and summarizes every bookmark</p>
                                    </div>
                                </div>

                                <div className="flex items-start gap-4">
                                    <div className="w-10 h-10 bg-amber-500/10 rounded-lg flex items-center justify-center shrink-0">
                                        <Search className="w-5 h-5 text-amber-400" />
                                    </div>
                                    <div>
                                        <h3 className="text-white font-bold mb-1">Find anything instantly</h3>
                                        <p className="text-gray-400 text-sm">Semantic search understands what you're looking for</p>
                                    </div>
                                </div>

                                <div className="flex items-start gap-4">
                                    <div className="w-10 h-10 bg-primary-500/10 rounded-lg flex items-center justify-center shrink-0">
                                        <Sparkles className="w-5 h-5 text-primary-400" />
                                    </div>
                                    <div>
                                        <h3 className="text-white font-bold mb-1">Share your picks</h3>
                                        <p className="text-gray-400 text-sm">Create your own public profile like this one</p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Right Column - Sign In */}
                        <div className="w-full md:w-[400px] p-8 sm:p-12 flex flex-col justify-center bg-gray-900/50">
                            <div className="space-y-6">
                                <div>
                                    <h3 className="text-xl font-bold text-white mb-2">Get started</h3>
                                    <p className="text-gray-400 text-sm">Sign in to save this bookmark and start building your collection</p>
                                </div>

                                {/* Error message */}
                                {error && (
                                    <div className="p-4 bg-red-900/20 border border-red-900/30 rounded-xl text-red-400 text-sm">
                                        {error}
                                    </div>
                                )}

                                {/* CTA Button */}
                                <button
                                    onClick={handleSignIn}
                                    disabled={isLoading || isSaving}
                                    className="w-full h-14 flex items-center justify-center gap-3 px-6 bg-white hover:bg-gray-100 text-gray-900 rounded-xl transition-all duration-200 font-bold shadow-xl active:scale-[0.98] disabled:opacity-50 group"
                                >
                                    {isLoading || isSaving ? (
                                        <>
                                            <Loader2 className="w-5 h-5 animate-spin" />
                                            <span>{isSaving ? 'Saving...' : 'Signing in...'}</span>
                                        </>
                                    ) : (
                                        <>
                                            <svg className="w-5 h-5 group-hover:rotate-12 transition-transform" viewBox="0 0 24 24">
                                                <path
                                                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                                                    fill="#4285F4"
                                                />
                                                <path
                                                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                                                    fill="#34A853"
                                                />
                                                <path
                                                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                                                    fill="#FBBC05"
                                                />
                                                <path
                                                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1c-3.17 0-5.92 1.83-7.24 4.5l3.66 2.85c.87-2.6 3.3-4.53 6.16-4.53z"
                                                    fill="#EA4335"
                                                />
                                            </svg>
                                            <span>Continue with Google</span>
                                        </>
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
