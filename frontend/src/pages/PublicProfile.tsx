import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Mail, CheckCircle, Loader2, Copy, Check, AlertTriangle, MoreVertical } from 'lucide-react'
import { publicApi, bookmarksApi } from '../lib/api'
import { useAuthStore } from '../stores/authStore'
import SubscribersModal from '../components/SubscribersModal'
import SaveToCollectionModal from '../components/SaveToCollectionModal'
import BookmarkCard from '../components/BookmarkCard'
import { Bookmark } from '../lib/api'

interface PublicProfileProps {
    username?: string
}

export default function PublicProfile({ username = 'sarath' }: PublicProfileProps) {
    const navigate = useNavigate()
    const { user, isAuthenticated, token } = useAuthStore()

    const [email, setEmail] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [isSubscribed, setIsSubscribed] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [subscriberCount, setSubscriberCount] = useState(0)
    const [totalCount, setTotalCount] = useState(0)
    const [bookmarks, setBookmarks] = useState<Bookmark[]>([])
    const [isLoadingBookmarks, setIsLoadingBookmarks] = useState(true)
    const [backendIsOwner, setBackendIsOwner] = useState(false)
    const [profileNotFound, setProfileNotFound] = useState(false)
    const [profileMetadata, setProfileMetadata] = useState<{ avatar_url?: string, full_name?: string } | null>(null)
    const [isCopied, setIsCopied] = useState(false)
    const [isSubscribersModalOpen, setIsSubscribersModalOpen] = useState(false)
    const [isMenuOpen, setIsMenuOpen] = useState(false)
    const [saveModalOpen, setSaveModalOpen] = useState(false)
    const [bookmarkToSave, setBookmarkToSave] = useState<Bookmark | null>(null)
    const [saveSuccess, setSaveSuccess] = useState(false)
    const [savingBookmarkId, setSavingBookmarkId] = useState<string | null>(null)
    const [retryBookmark, setRetryBookmark] = useState<Bookmark | null>(null)

    // Check if current user is the owner of this profile locally
    const currentUserUsername = user?.email?.split('@')[0]?.toLowerCase()
    const isOwner = (isAuthenticated && currentUserUsername === username?.toLowerCase()) || backendIsOwner

    // Get full name and first name for display
    const fullName = profileMetadata?.full_name || username || ''
    const firstName = fullName.split(' ')[0] || username || ''

    useEffect(() => {
        if (!username) return

        const fetchCount = async () => {
            try {
                const response = await fetch(`/api/public/@${username}/subscribers/count`)
                if (response.ok) {
                    const data = await response.json()
                    setSubscriberCount(data.count || 0)
                }
            } catch (err) {
                console.error('Error fetching subscriber count:', err)
            }
        }
        fetchCount()
    }, [username])

    // Fetch bookmarks
    useEffect(() => {
        const fetchBookmarks = async () => {
            setIsLoadingBookmarks(true)
            try {
                const headers: Record<string, string> = {}
                if (token) {
                    headers['Authorization'] = `Bearer ${token}`
                }

                const response = await fetch(`/api/public/@${username}/bookmarks`, {
                    headers
                })
                if (response.ok) {
                    const data = await response.json()
                    setBookmarks(data.bookmarks || [])
                    setProfileMetadata(data.profile || null)
                    setTotalCount(data.total_count || 0)
                    if (data.is_owner) {
                        setBackendIsOwner(true)
                    }
                } else if (response.status === 404) {
                    setProfileNotFound(true)
                }
            } catch (err) {
                console.error('Error fetching bookmarks:', err)
            } finally {
                setIsLoadingBookmarks(false)
            }
        }
        if (username) {
            fetchBookmarks()
        }
    }, [username, token])

    const handleSubscribe = async (e: React.FormEvent) => {
        e.preventDefault()
        setError(null)
        setIsLoading(true)

        if (!email || !email.includes('@')) {
            setError('Please enter a valid email address')
            setIsLoading(false)
            return
        }

        try {
            const response = await fetch(`/api/public/@${username}/subscribe`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email.toLowerCase().trim() })
            })

            const data = await response.json()

            if (response.ok) {
                setIsSubscribed(true)
                if (isOwner) setSubscriberCount(prev => prev + 1)
            } else {
                setError(data.error || 'Failed to subscribe')
            }
        } catch (err) {
            console.error('Subscribe error:', err)
            setError('Something went wrong. Please try again.')
        } finally {
            setIsLoading(false)
        }
    }

    const handleCopyProfileLink = () => {
        const url = window.location.href
        navigator.clipboard.writeText(url)
        setIsCopied(true)
        setTimeout(() => setIsCopied(false), 2000)
    }

    const handleUnsubscribe = async () => {
        if (!window.confirm(`Stop receiving updates from ${firstName}?`)) return
        setIsLoading(true)
        try {
            await publicApi.unsubscribe(username!)
            setIsSubscribed(false)
            setSubscriberCount(prev => Math.max(0, prev - 1))
        } catch (err) {
            console.error('Unsubscribe error:', err)
            setError('Failed to unsubscribe. Please try again.')
        } finally {
            setIsLoading(false)
        }
    }

    const handleDeleteAccount = async () => {
        const confirmed = window.confirm("CRITICAL ACTION: This will permanently delete your Markly account, all your bookmarks, search history, and followers. This cannot be undone.\n\nAre you absolutely sure?")
        if (!confirmed) return

        const doubleConfirmed = window.prompt("To confirm, please type 'DELETE MY ACCOUNT' below:")
        if (doubleConfirmed !== 'DELETE MY ACCOUNT') return

        setIsLoading(true)
        try {
            const { bookmarksApi } = await import('../lib/api')
            await bookmarksApi.deleteAccount()
            const { logout } = useAuthStore.getState()
            logout()
            navigate('/login')
        } catch (err) {
            console.error('Account deletion error:', err)
            setError('Failed to delete account. Please contact support.')
        } finally {
            setIsLoading(false)
        }
    }

    // Check subscription status
    useEffect(() => {
        if (isAuthenticated && username && !isOwner) {
            const checkSub = async () => {
                try {
                    const res = await publicApi.checkSubscription(username)
                    setIsSubscribed(res.data.is_subscribed)
                } catch (err) {
                    console.error('Check sub error:', err)
                }
            }
            checkSub()
        }
    }, [isAuthenticated, username, isOwner])

    const toggleBookmarkVisibility = async (bookmark: Bookmark) => {
        if (!isOwner) return

        try {
            const response = await fetch(`/api/public/bookmarks/${bookmark.id}/visibility`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ is_public: !bookmark.is_public })
            })

            if (response.ok) {
                setBookmarks(prev => prev.map(b =>
                    b.id === bookmark.id ? { ...b, is_public: !b.is_public } : b
                ))
            }
        } catch (err) {
            console.error('Error toggling visibility:', err)
        }
    }

    const handleSaveBookmark = async (bookmark: Bookmark) => {
        if (!isAuthenticated) {
            // Open modal instead of redirecting
            setBookmarkToSave(bookmark)
            setSaveModalOpen(true)
            return
        }

        // Authenticated users save directly
        setSavingBookmarkId(bookmark.id)
        setError(null)
        setRetryBookmark(null)

        try {
            const response = await bookmarksApi.savePublic(bookmark.id)

            // Check if it's a duplicate
            if (response.data.already_exists) {
                // Show info message
                setError('This bookmark is already in your collection')
                setTimeout(() => setError(null), 3000)

                // Update the bookmark state to show it's saved
                setBookmarks(prev => prev.map(b =>
                    b.id === bookmark.id ? { ...b, is_saved_by_viewer: true } : b
                ))
            } else {
                // New save - show success
                setSaveSuccess(true)
                setTimeout(() => setSaveSuccess(false), 3000)

                // Update the bookmark state
                setBookmarks(prev => prev.map(b =>
                    b.id === bookmark.id ? { ...b, is_saved_by_viewer: true } : b
                ))
            }
        } catch (err: any) {
            console.error('Failed to save public bookmark:', err)

            // Store bookmark for retry
            setRetryBookmark(bookmark)

            // Show error with specific message
            if (err.response?.status === 404) {
                setError('This bookmark is no longer available')
            } else if (err.code === 'ERR_NETWORK') {
                setError('Network error. Check your connection and try again.')
            } else {
                setError('Failed to save bookmark. Please try again.')
            }

            // Auto-clear error after 5 seconds
            setTimeout(() => {
                setError(null)
                setRetryBookmark(null)
            }, 5000)
        } finally {
            setSavingBookmarkId(null)
        }
    }

    const handleRetry = () => {
        if (retryBookmark) {
            handleSaveBookmark(retryBookmark)
        }
    }

    const handleSaveSuccess = () => {
        setSaveSuccess(true)
        setTimeout(() => setSaveSuccess(false), 3000)
    }

    useEffect(() => {
        if (username) {
            document.title = `${firstName}'s Reading List - Markly`
        }
        return () => {
            document.title = 'Markly - Never lose a great link again'
        }
    }, [username, fullName])

    return (
        <div className={`${!isOwner ? 'dark min-h-screen bg-gray-950 px-6' : 'bg-transparent'} text-gray-900 dark:text-gray-200 selection:bg-primary-500/30 flex flex-col transition-colors duration-300`}>
            {/* Background effects - Simplified for single surface look */}
            {!isOwner && (
                <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
                    <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-[600px] bg-gradient-to-b from-primary-950/20 to-transparent" />
                    <div className="absolute top-[10%] left-[10%] w-[500px] h-[500px] bg-primary-600/5 rounded-full blur-[128px]" />
                </div>
            )}

            <div className={`relative z-10 flex-1 max-w-full lg:max-w-screen-2xl mx-auto ${!isOwner ? 'py-8 sm:py-16' : 'px-6 py-8 sm:py-16'} w-full`}>
                {/* Top Right Menu for Owner */}
                {isOwner && (
                    <div className="absolute top-8 right-6 z-30">
                        <button
                            onClick={() => setIsMenuOpen(!isMenuOpen)}
                            className="p-2 text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-900/50 rounded-xl transition-all"
                            title="More options"
                        >
                            <MoreVertical className="w-5 h-5" />
                        </button>

                        {isMenuOpen && (
                            <>
                                <div
                                    className="fixed inset-0 z-10"
                                    onClick={() => setIsMenuOpen(false)}
                                />
                                <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-2xl shadow-2xl z-20 overflow-hidden animate-in fade-in zoom-in duration-200 origin-top-right">
                                    <div className="p-2">
                                        <button
                                            onClick={() => {
                                                setIsMenuOpen(false)
                                                handleDeleteAccount()
                                            }}
                                            className="w-full flex items-center gap-3 px-4 py-3 text-red-500 hover:bg-red-500/10 rounded-xl text-xs font-black uppercase tracking-widest transition-colors group"
                                        >
                                            <AlertTriangle className="w-4 h-4" />
                                            <span>Delete Account</span>
                                        </button>
                                    </div>
                                </div>
                            </>
                        )}
                    </div>
                )}

                {/* Hero Curation Unit */}
                {isLoadingBookmarks ? (
                    <div className="flex justify-center py-20">
                        <Loader2 className="w-10 h-10 text-primary-500 animate-spin" />
                    </div>
                ) : (
                    <div className="flex flex-col items-center text-center mb-10 sm:mb-20">
                        {/* Profile Identity Section */}
                        <div className="flex flex-col items-center mb-8 sm:mb-10">
                            <div className="relative group mb-6">
                                <div className="absolute -inset-1.5 bg-gradient-to-tr from-primary-500 to-blue-500 rounded-2xl blur opacity-25 group-hover:opacity-40 transition duration-1000 group-hover:duration-200"></div>
                                {profileMetadata?.avatar_url ? (
                                    <img
                                        src={profileMetadata.avatar_url}
                                        alt={fullName}
                                        className="relative w-20 h-20 sm:w-28 sm:h-28 aspect-square rounded-2xl object-cover object-center border-2 border-white dark:border-gray-950 shadow-xl dark:shadow-2xl transition-transform duration-500 group-hover:scale-[1.02]"
                                        onError={(e) => {
                                            (e.target as HTMLImageElement).src = `https://ui-avatars.com/api/?name=${fullName}&background=6366f1&color=fff&size=128`
                                        }}
                                    />
                                ) : (
                                    <div className="relative w-20 h-20 sm:w-28 sm:h-28 aspect-square bg-gray-100 dark:bg-gray-900 rounded-2xl flex items-center justify-center border-2 border-white dark:border-gray-950 shadow-xl dark:shadow-2xl">
                                        <Mail className="w-10 h-10 sm:w-12 sm:h-12 text-primary-500" />
                                    </div>
                                )}
                            </div>

                            <h1 className="text-3xl sm:text-6xl font-black text-gray-900 dark:text-white tracking-tight mb-4">
                                {firstName}'s Reading List
                            </h1>

                            <p className="text-gray-500 dark:text-gray-400 text-xs sm:text-base font-medium max-w-xl mx-auto leading-relaxed px-4">
                                Curated by <span className="text-gray-900 dark:text-white font-bold">{fullName}</span>
                            </p>
                        </div>

                        {/* Integrated Stats & Notify Bar */}
                        <div className="w-full max-w-5xl bg-white dark:bg-gray-900/40 backdrop-blur-2xl border border-gray-200 dark:border-gray-800 rounded-2xl p-2 sm:p-2 sm:pl-8 shadow-[0_20px_50px_rgba(0,0,0,0.1)] dark:shadow-[0_20px_50px_rgba(0,0,0,0.5)] flex flex-col sm:flex-row items-center gap-4 sm:gap-10">
                            {/* High-Impact Stats */}
                            <div className="flex items-center justify-around sm:justify-start w-full sm:w-auto gap-6 sm:gap-10 py-4 sm:py-0 px-4 sm:px-0 border-b sm:border-b-0 border-gray-100 dark:border-gray-800/50">
                                <div className="flex flex-col items-center sm:items-start min-w-[60px]">
                                    <span className="text-xl sm:text-2xl font-black text-gray-900 dark:text-white leading-none">{totalCount}</span>
                                    <span className="text-[9px] sm:text-[10px] uppercase tracking-[0.2em] text-gray-400 dark:text-gray-500 font-black mt-2">Picks</span>
                                </div>
                                <div className="w-px h-8 bg-gray-100 dark:bg-gray-800 hidden sm:block" />
                                <div
                                    className={`flex flex-col items-center sm:items-start min-w-[80px] ${isOwner ? 'cursor-pointer hover:opacity-80 transition-opacity' : ''}`}
                                    onClick={() => isOwner && setIsSubscribersModalOpen(true)}
                                    title={isOwner ? "View your subscribers" : undefined}
                                >
                                    <span className="text-xl sm:text-2xl font-black text-gray-900 dark:text-white leading-none">{subscriberCount}</span>
                                    <span className="text-[9px] sm:text-[10px] uppercase tracking-[0.2em] text-gray-400 dark:text-gray-500 font-black mt-2">Subscribers</span>
                                </div>
                            </div>

                            {/* Integrated Action Area */}
                            <div className="flex-1 w-full flex items-center sm:border-l border-gray-200 dark:border-gray-800/50">
                                {isOwner ? (
                                    <div className="flex-1 flex flex-col sm:flex-row items-center justify-between p-2 sm:p-1 sm:pl-8 gap-4 sm:gap-0">
                                        <div className="flex flex-col items-center sm:items-start truncate w-full sm:w-auto">
                                            <span className="text-[9px] sm:text-[10px] font-black uppercase tracking-widest text-primary-500 mb-0.5">Your Public Link</span>
                                            <span className="text-xs sm:text-sm font-bold text-gray-400 truncate max-w-full">{window.location.origin}/@{username}</span>
                                        </div>
                                        <button
                                            onClick={handleCopyProfileLink}
                                            className="w-full sm:w-auto h-12 px-8 bg-gray-800 hover:bg-gray-700 text-white font-black uppercase tracking-widest text-[10px] rounded-xl transition-all flex items-center justify-center gap-2 active:scale-95"
                                        >
                                            {isCopied ? (
                                                <>
                                                    <Check className="w-4 h-4 text-green-400" />
                                                    <span className="text-green-400">Copied</span>
                                                </>
                                            ) : (
                                                <>
                                                    <Copy className="w-4 h-4" />
                                                    <span>Copy Link</span>
                                                </>
                                            )}
                                        </button>
                                    </div>
                                ) : !isSubscribed ? (
                                    <form onSubmit={handleSubscribe} className="flex flex-1 flex-col sm:flex-row items-center p-1 w-full gap-2 sm:gap-0">
                                        <div className="flex-1 flex items-center px-4 w-full">
                                            <Mail className="w-4 h-4 text-gray-400 dark:text-gray-600 mr-3 shrink-0" />
                                            <input
                                                type="email"
                                                value={email}
                                                onChange={(e) => setEmail(e.target.value)}
                                                placeholder="Enter email to stay updated"
                                                className="w-full bg-transparent border-none text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-0 text-sm font-bold py-3 sm:py-0"
                                                required
                                            />
                                        </div>
                                        <button
                                            type="submit"
                                            disabled={isLoading}
                                            className="w-full sm:w-auto h-12 px-8 bg-primary-600 hover:bg-primary-500 text-white font-black uppercase tracking-widest text-[10px] rounded-xl transition-all shadow-lg shadow-primary-600/20 active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2"
                                        >
                                            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Notify Me'}
                                        </button>
                                    </form>
                                ) : (
                                    <div className="flex-1 h-12 flex items-center justify-between px-8 text-green-400">
                                        <div className="flex items-center gap-3">
                                            <CheckCircle className="w-4 h-4" />
                                            <span className="text-[11px] font-black uppercase tracking-widest">You're on the list!</span>
                                        </div>
                                        <button
                                            onClick={handleUnsubscribe}
                                            className="text-[10px] font-black uppercase tracking-widest text-gray-500 hover:text-red-400 transition-colors"
                                        >
                                            Unsubscribe
                                        </button>
                                    </div>
                                )}
                            </div>
                        </div>

                        {error && <p className="text-red-400 text-[10px] mt-4 font-black uppercase tracking-widest animate-pulse">{error}</p>}
                    </div>
                )}

                {/* Masonry Grid */}
                {isLoadingBookmarks ? (
                    <div className="flex justify-center py-20">
                        <Loader2 className="w-10 h-10 text-primary-500 animate-spin" />
                    </div>
                ) : profileNotFound ? (
                    <div className="text-center py-20 bg-gray-900/20 rounded-3xl border border-dashed border-gray-800">
                        <p className="text-gray-400 text-xl font-medium">Profile not found</p>
                        <button onClick={() => navigate('/')} className="mt-4 text-primary-400 font-bold hover:underline">Go Home</button>
                    </div>
                ) : bookmarks.length === 0 ? (
                    <div className="text-center py-20 bg-gray-900/20 rounded-3xl border border-dashed border-gray-800">
                        <p className="text-gray-500 font-medium">No bookmarks shared yet</p>
                    </div>
                ) : (
                    <div className="columns-1 sm:columns-2 xl:columns-3 2xl:columns-4 3xl:columns-5 gap-6 space-y-6 max-w-full">
                        {bookmarks.map((bookmark) => (
                            <BookmarkCard
                                key={bookmark.id}
                                bookmark={bookmark}
                                isOwner={isOwner}
                                isPublicView={!isOwner}
                                onVisibilityToggle={toggleBookmarkVisibility}
                                onSave={handleSaveBookmark}
                                isSaving={savingBookmarkId === bookmark.id}
                            />
                        ))}
                    </div>
                )}

                {/* Footer */}
                <div className="text-center mt-20 pt-10 border-t border-gray-100 dark:border-gray-800">
                    <a href="/" className="inline-flex items-center gap-2 text-gray-400 dark:text-gray-600 hover:text-primary-500 text-xs font-black uppercase tracking-[0.2em] transition-all">
                        Powered by <Mail className="w-4 h-4 shrink-0" /> Markly
                    </a>
                </div>
            </div>

            {/* Success Toast */}
            {saveSuccess && (
                <div className="fixed bottom-8 right-8 z-50 animate-in slide-in-from-bottom-4 fade-in duration-300">
                    <div className="bg-green-600 text-white px-6 py-4 rounded-xl shadow-2xl flex items-center gap-3 border border-green-500">
                        <CheckCircle className="w-5 h-5" />
                        <span className="font-bold">Saved to your collection</span>
                    </div>
                </div>
            )}

            {/* Error/Info Toast with Retry */}
            {error && (
                <div className="fixed bottom-8 right-8 z-50 animate-in slide-in-from-bottom-4 fade-in duration-300">
                    <div className={`px-6 py-4 rounded-xl shadow-2xl border ${error.includes('already in your collection')
                        ? 'bg-blue-600 border-blue-500'
                        : 'bg-red-600 border-red-500'
                        } text-white`}>
                        <div className="flex items-start gap-3">
                            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                            <div className="flex-1">
                                <p className="font-bold mb-2">{error}</p>
                                {retryBookmark && (
                                    <button
                                        onClick={handleRetry}
                                        className="w-full px-4 py-2 bg-white text-red-600 rounded-lg font-bold text-sm hover:bg-gray-100 transition-colors"
                                    >
                                        Retry
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {isOwner && (
                <SubscribersModal
                    isOpen={isSubscribersModalOpen}
                    onClose={() => setIsSubscribersModalOpen(false)}
                    username={username}
                />
            )}

            <SaveToCollectionModal
                isOpen={saveModalOpen}
                onClose={() => {
                    setSaveModalOpen(false)
                    setBookmarkToSave(null)
                }}
                bookmarkToSave={bookmarkToSave}
                onSaveSuccess={handleSaveSuccess}
            />
        </div>
    )
}
