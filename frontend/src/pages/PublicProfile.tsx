import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Mail, CheckCircle, Loader2, Copy, Check, AlertTriangle, MoreVertical } from 'lucide-react'
import { publicApi, bookmarksApi } from '../lib/api'
import { useAuthStore } from '../stores/authStore'
import SubscribersModal from '../components/SubscribersModal'
import SaveToCollectionModal from '../components/SaveToCollectionModal'
import BookmarkCard from '../components/BookmarkCard'
import MasonryGrid from '../components/MasonryGrid'
import TopicsBox from '../components/TopicsBox'
import { Bookmark } from '../lib/api'

interface PublicProfileProps {
    username?: string
}

export default function PublicProfile({ username = 'sarath' }: PublicProfileProps) {
    const navigate = useNavigate()
    const { user, isAuthenticated, token, isLoading: isAuthLoading } = useAuthStore()

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
    const [topTags, setTopTags] = useState<{ tag: string; count: number }[]>([])
    const [selectedTags, setSelectedTags] = useState<string[]>([])
    const [isLoadingTags, setIsLoadingTags] = useState(false)

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

    // Fetch tags
    useEffect(() => {
        const fetchTags = async () => {
            if (!username) return
            setIsLoadingTags(true)
            try {
                const response = await publicApi.getTags(username)
                setTopTags(response.data.tags || [])
            } catch (err) {
                console.error('Error fetching tags:', err)
            } finally {
                setIsLoadingTags(false)
            }
        }
        fetchTags()
    }, [username])

    const toggleTag = (tag: string) => {
        setSelectedTags(prev =>
            prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
        )
    }

    const clearFilters = () => {
        setSelectedTags([])
    }

    // Filtered bookmarks
    const filteredBookmarks = selectedTags.length > 0
        ? bookmarks.filter(b => selectedTags.every(tag => b.auto_tags?.includes(tag)))
        : bookmarks

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
                // Optimistically update subscriber count for everyone
                setSubscriberCount(prev => prev + 1)
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
        const confirmed = window.confirm("CRITICAL ACTION: This will permanently delete your markly account, all your bookmarks, search history, and followers. This cannot be undone.\n\nAre you absolutely sure?")
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
            document.title = `${firstName}'s Reading List - markly`
        }
        return () => {
            document.title = 'markly - Never lose a great link again'
        }
    }, [username, fullName, firstName])

    if (isAuthLoading) {
        return (
            <div className="min-h-screen bg-gray-950 flex items-center justify-center">
                <Loader2 className="w-8 h-8 text-primary-500 animate-spin" />
            </div>
        )
    }

    return (
        <div className={`${!isOwner ? 'min-h-screen bg-gray-50 dark:bg-gray-950' : 'bg-transparent'} text-gray-900 dark:text-gray-100 selection:bg-primary-500/30 flex flex-col transition-colors duration-300`}>
            {/* Background effects */}
            {!isOwner && (
                <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
                    <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-[600px] bg-gradient-to-b from-primary-500/5 to-transparent dark:from-primary-500/10" />
                </div>
            )}

            <div className={`relative z-10 flex-1 max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-10 ${!isOwner ? 'py-4 sm:py-6' : 'py-4 sm:py-6'} w-full space-y-8 sm:space-y-10`}>
                {/* Hero & Grid Unit */}
                {isLoadingBookmarks ? (
                    <div className="flex justify-center py-32">
                        <Loader2 className="w-10 h-10 text-primary-500 animate-spin" />
                    </div>
                ) : (
                    <>
                        {/* Profile Header section */}
                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 relative">
                            {/* Profile Identity Section */}
                            <div className="flex items-center gap-5 sm:gap-8">
                                <div className="relative group shrink-0">
                                    <div className="absolute -inset-1.5 bg-gradient-to-tr from-primary-500 to-blue-500 rounded-2xl blur opacity-25 group-hover:opacity-40 transition duration-1000 group-hover:duration-200"></div>
                                    {profileMetadata?.avatar_url ? (
                                        <img
                                            src={profileMetadata.avatar_url}
                                            alt={fullName}
                                            className="relative w-16 h-16 sm:w-20 sm:h-20 aspect-square rounded-2xl object-cover object-center border-2 border-white dark:border-gray-950 shadow-2xl transition-transform duration-500 group-hover:scale-[1.05]"
                                            onError={(e) => {
                                                (e.target as HTMLImageElement).src = `https://ui-avatars.com/api/?name=${fullName}&background=6366f1&color=fff&size=200`
                                            }}
                                        />
                                    ) : (
                                        <div className="relative w-16 h-16 sm:w-20 sm:h-20 aspect-square bg-gray-100 dark:bg-gray-900 rounded-2xl flex items-center justify-center border-2 border-white dark:border-gray-950 shadow-2xl">
                                            <Mail className="w-8 h-8 sm:w-10 sm:h-10 text-primary-500" />
                                        </div>
                                    )}
                                </div>

                                <div className="flex flex-col">
                                    <h1 className="text-2xl sm:text-3xl font-black text-gray-900 dark:text-white tracking-tight leading-none mb-2">
                                        {firstName}'s Reading List
                                    </h1>
                                    <p className="text-gray-500 dark:text-gray-400 text-xs sm:text-sm font-bold uppercase tracking-[0.15em]">
                                        Curated by <span className="text-gray-900 dark:text-white">{fullName}</span>
                                    </p>
                                </div>
                            </div>

                            {/* Integrated Stats & Notify Bar */}
                            <div className={`${!isOwner ? 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 shadow-xl' : 'bg-white dark:bg-gray-900/40 border border-gray-200 dark:border-gray-800 shadow-2xl'} backdrop-blur-3xl rounded-[2rem] p-2 flex flex-col xl:flex-row items-stretch xl:items-center gap-4 xl:gap-0 relative transition-colors`}>
                                {/* High-Impact Stats */}
                                <div className="flex items-center gap-6 sm:gap-10 px-6 py-2 xl:px-8">
                                    <div className="flex flex-col">
                                        <span className="text-2xl sm:text-3xl font-black text-gray-900 dark:text-white leading-none">{totalCount}</span>
                                        <span className="text-[10px] uppercase tracking-[0.2em] text-gray-400 dark:text-gray-500 font-black mt-2">Picks</span>
                                    </div>
                                    <div className="w-px h-10 bg-gray-100 dark:bg-gray-800 hidden sm:block" />
                                    <div
                                        className={`flex flex-col ${isOwner ? 'cursor-pointer hover:opacity-80 transition-all' : ''}`}
                                        onClick={() => isOwner && setIsSubscribersModalOpen(true)}
                                        title={isOwner ? "View your subscribers" : undefined}
                                    >
                                        <span className="text-2xl sm:text-3xl font-black text-gray-900 dark:text-white leading-none">{subscriberCount}</span>
                                        <span className="text-[10px] uppercase tracking-[0.2em] text-gray-400 dark:text-gray-500 font-black mt-2">Subscribers</span>
                                    </div>
                                </div>

                                {/* Integrated Action Area */}
                                <div className="flex-1 flex items-center border-t xl:border-t-0 xl:border-l border-gray-100 dark:border-gray-800 pt-4 xl:pt-0 xl:pl-8 px-4 xl:px-6">
                                    {isOwner ? (
                                        <div className="flex items-center justify-between xl:justify-start gap-6 w-full">
                                            <div className="flex flex-col gap-1 min-w-0">
                                                <span className="text-[10px] font-black uppercase tracking-[0.2em] text-primary-500">Your Public Link</span>
                                                <span className="text-sm font-medium text-gray-400 truncate max-w-[180px] sm:max-w-xs transition-colors hover:text-gray-300">
                                                    {window.location.origin}/@{username}
                                                </span>
                                            </div>

                                            <div className="flex items-center gap-3 shrink-0">
                                                <button
                                                    onClick={handleCopyProfileLink}
                                                    className="h-12 px-6 bg-gray-800 hover:bg-gray-700 text-white font-black uppercase tracking-widest text-[10px] rounded-2xl transition-all flex items-center gap-3 active:scale-95 shadow-lg shadow-black/10 border border-gray-700/50"
                                                >
                                                    {isCopied ? (
                                                        <>
                                                            <Check className="w-4 h-4 text-green-400" />
                                                            <span className="text-green-400">Copied</span>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <Copy className="w-4 h-4 text-gray-400" />
                                                            <span className="whitespace-nowrap">Copy Link</span>
                                                        </>
                                                    )}
                                                </button>

                                                <div className="relative">
                                                    <button
                                                        onClick={() => setIsMenuOpen(!isMenuOpen)}
                                                        className="p-3 text-gray-500 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800/50 rounded-2xl transition-all border border-transparent hover:border-gray-700/30"
                                                    >
                                                        <MoreVertical className="w-5 h-5" />
                                                    </button>
                                                    {isMenuOpen && (
                                                        <>
                                                            <div className="fixed inset-0 z-10" onClick={() => setIsMenuOpen(false)} />
                                                            <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-gray-900 border border-gray-100 dark:border-gray-800 rounded-2xl shadow-2xl z-20 overflow-hidden animate-in fade-in zoom-in duration-200 origin-top-right">
                                                                <div className="p-2">
                                                                    <button
                                                                        onClick={() => {
                                                                            setIsMenuOpen(false)
                                                                            handleDeleteAccount()
                                                                        }}
                                                                        className="w-full flex items-center gap-3 px-4 py-3 text-red-500 hover:bg-red-500/10 rounded-xl text-[10px] font-black uppercase tracking-widest transition-colors"
                                                                    >
                                                                        <AlertTriangle className="w-4 h-4" />
                                                                        <span>Delete Account</span>
                                                                    </button>
                                                                </div>
                                                            </div>
                                                        </>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    ) : !isSubscribed ? (
                                        <form onSubmit={handleSubscribe} className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full py-2">
                                            <div className="relative flex-1 group min-w-0">
                                                <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
                                                    <Mail className="w-4 h-4 text-gray-500 group-focus-within:text-primary-500 transition-colors" />
                                                </div>
                                                <input
                                                    type="email"
                                                    value={email}
                                                    onChange={(e) => setEmail(e.target.value)}
                                                    placeholder="Enter email to join the list"
                                                    className={`w-full xl:w-72 ${!isOwner ? 'bg-gray-100/50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700 text-gray-900 dark:text-white' : 'bg-gray-950/40 border-gray-800/80 text-white'} rounded-2xl py-3.5 pl-12 pr-4 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500/30 transition-all font-medium`}
                                                    required
                                                />
                                            </div>
                                            <button
                                                type="submit"
                                                disabled={isLoading}
                                                className="h-[52px] px-8 bg-primary-600 hover:bg-primary-500 text-white font-black uppercase tracking-widest text-[10px] rounded-2xl transition-all shadow-xl shadow-primary-600/20 active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2 shrink-0"
                                            >
                                                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Keep me updated'}
                                            </button>
                                        </form>
                                    ) : (
                                        <div className="flex items-center justify-between sm:justify-start gap-8 text-green-400 w-full py-2">
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 bg-green-500/10 rounded-xl flex items-center justify-center border border-green-500/20">
                                                    <CheckCircle className="w-5 h-5" />
                                                </div>
                                                <span className="text-[10px] font-black uppercase tracking-[0.2em]">Subscribed</span>
                                            </div>
                                            <button
                                                onClick={handleUnsubscribe}
                                                className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500 hover:text-red-400 transition-colors py-2"
                                            >
                                                Unsubscribe
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                            {error && <p className="absolute -bottom-8 left-0 text-red-400 text-[10px] font-black uppercase tracking-widest animate-pulse">{error}</p>}
                        </div>

                        <TopicsBox
                            tags={topTags}
                            selectedTags={selectedTags}
                            isLoading={isLoadingTags}
                            onTagClick={toggleTag}
                            onClearFilters={clearFilters}
                        />

                        {/* Masonry Grid Section */}
                        {profileNotFound ? (
                            <div className="text-center py-20 bg-gray-900/20 rounded-3xl border border-dashed border-gray-800">
                                <p className="text-gray-400 text-xl font-medium">Profile not found</p>
                                <button onClick={() => navigate('/')} className="mt-4 text-primary-400 font-bold hover:underline">Go Home</button>
                            </div>
                        ) : bookmarks.length === 0 ? (
                            <div className="text-center py-20 bg-gray-900/20 rounded-3xl border border-dashed border-gray-800">
                                <p className="text-gray-500 font-medium">No bookmarks shared yet</p>
                            </div>
                        ) : (
                            <div className="space-y-6">
                                {selectedTags.length > 0 && (
                                    <div className="flex items-center justify-between">
                                        <h2 className="text-sm font-bold uppercase tracking-[0.2em] text-gray-400">
                                            Results for {selectedTags.map(t => `#${t}`).join(', ')} ({filteredBookmarks.length})
                                        </h2>
                                        <button
                                            onClick={clearFilters}
                                            className="text-[10px] font-black uppercase tracking-widest text-primary-600 hover:text-primary-700 transition-colors"
                                        >
                                            Clear all filters
                                        </button>
                                    </div>
                                )}
                                <MasonryGrid
                                    items={filteredBookmarks}
                                    renderItem={(bookmark: Bookmark) => (
                                        <BookmarkCard
                                            key={bookmark.id}
                                            bookmark={bookmark}
                                            isOwner={isOwner}
                                            isPublicView={!isOwner}
                                            onVisibilityToggle={toggleBookmarkVisibility}
                                            onSave={handleSaveBookmark}
                                            onTagClick={toggleTag}
                                            isSaving={savingBookmarkId === bookmark.id}
                                        />
                                    )}
                                    breakpoints={{ 0: 1, 640: 2, 1024: 3, 1280: 4 }}
                                />
                                {filteredBookmarks.length === 0 && (
                                    <div className="text-center py-20 bg-gray-50 dark:bg-gray-900/20 rounded-3xl border border-dashed border-gray-100 dark:border-gray-800">
                                        <p className="text-gray-500 font-medium">No bookmarks match these topics</p>
                                        <button onClick={clearFilters} className="mt-4 text-primary-600 font-bold hover:underline">Clear all filters</button>
                                    </div>
                                )}
                            </div>
                        )}
                    </>
                )}

                {/* Footer */}
                <div className="text-center mt-20 pt-10 border-t border-gray-100 dark:border-gray-800">
                    <a href="/" className="inline-flex items-center gap-2 text-gray-400 dark:text-gray-600 hover:text-primary-500 text-xs font-black uppercase tracking-[0.2em] transition-all">
                        Powered by <Mail className="w-4 h-4 shrink-0" /> markly
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
                    <div className={`px-6 py-4 rounded-xl shadow-2xl border ${error?.includes('already in your collection')
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
