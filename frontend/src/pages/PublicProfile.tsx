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
    const { user, isAuthenticated, isLoading: isAuthLoading } = useAuthStore()

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
                const response = await fetch(`/api/public/@${username}/bookmarks`, {
                    credentials: 'include'
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
    }, [username])

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
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
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
            <div className="min-h-screen bg-[#eef1ee] dark:bg-[#0b0d11] flex items-center justify-center">
                <Loader2 className="w-6 h-6 text-slate-400 animate-spin" />
            </div>
        )
    }

    return (
        <div className={`${!isOwner ? 'min-h-screen bg-[#eef1ee] dark:bg-[#0b0d11]' : 'bg-transparent'} text-slate-950 dark:text-slate-100 selection:bg-indigo-500/20 flex flex-col transition-colors duration-300`}>
            <div className={`relative z-10 flex-1 max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-10 py-6 sm:py-8 w-full space-y-8`}>
                {/* Hero & Grid Unit */}
                {isLoadingBookmarks ? (
                    <div className="flex justify-center py-32">
                        <Loader2 className="w-8 h-8 text-slate-400 animate-spin" />
                    </div>
                ) : (
                    <>
                        {/* Profile header */}
                        <div className="rounded-card bg-surface-light shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 px-6 py-6 sm:px-8 sm:py-7 flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
                            <div className="flex items-center gap-5 sm:gap-6 min-w-0">
                                <div className="shrink-0">
                                    {profileMetadata?.avatar_url ? (
                                        <img
                                            src={profileMetadata.avatar_url}
                                            alt={fullName}
                                            className="w-16 h-16 sm:w-20 sm:h-20 aspect-square rounded-2xl object-cover object-center ring-1 ring-slate-200 dark:ring-slate-800"
                                            onError={(e) => {
                                                (e.target as HTMLImageElement).src = `https://ui-avatars.com/api/?name=${fullName}&background=0f172a&color=fff&size=200`
                                            }}
                                        />
                                    ) : (
                                        <div className="w-16 h-16 sm:w-20 sm:h-20 aspect-square rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-500 dark:text-slate-400">
                                            <Mail className="w-7 h-7" />
                                        </div>
                                    )}
                                </div>

                                <div className="min-w-0">
                                    <h1 className="font-display text-3xl sm:text-4xl text-slate-950 dark:text-slate-50 leading-tight">
                                        {firstName}'s reading list
                                    </h1>
                                    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                                        Curated by <span className="text-slate-900 dark:text-slate-100">{fullName}</span>
                                    </p>
                                    <div className="mt-3 flex items-center gap-5 text-sm text-slate-500 dark:text-slate-400">
                                        <span><span className="font-medium text-slate-900 dark:text-slate-100">{totalCount}</span> picks</span>
                                        {isOwner && (
                                            <button
                                                onClick={() => setIsSubscribersModalOpen(true)}
                                                className="hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
                                                title="View your subscribers"
                                            >
                                                <span className="font-medium text-slate-900 dark:text-slate-100">{subscriberCount}</span> subscribers
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </div>

                            <div className="flex flex-col gap-3 md:items-end shrink-0">
                                {isOwner ? (
                                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                                        <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/80 ring-1 ring-slate-200 text-sm text-slate-600 truncate max-w-xs dark:bg-slate-900/60 dark:ring-slate-700 dark:text-slate-300">
                                            <span className="truncate">{window.location.origin}/@{username}</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <button
                                                onClick={handleCopyProfileLink}
                                                className="px-4 py-2 rounded-full bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white transition-colors flex items-center gap-2"
                                            >
                                                {isCopied ? (
                                                    <>
                                                        <Check className="w-4 h-4" />
                                                        Copied
                                                    </>
                                                ) : (
                                                    <>
                                                        <Copy className="w-4 h-4" />
                                                        Copy link
                                                    </>
                                                )}
                                            </button>

                                            <div className="relative">
                                                <button
                                                    onClick={() => setIsMenuOpen(!isMenuOpen)}
                                                    className="p-2 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 dark:hover:text-slate-200 dark:hover:bg-slate-800 transition-colors"
                                                >
                                                    <MoreVertical className="w-5 h-5" />
                                                </button>
                                                {isMenuOpen && (
                                                    <>
                                                        <div className="fixed inset-0 z-10" onClick={() => setIsMenuOpen(false)} />
                                                        <div className="absolute right-0 mt-2 w-52 rounded-2xl bg-white shadow-card ring-1 ring-slate-200/70 dark:bg-slate-900 dark:ring-slate-800 z-20 overflow-hidden animate-in fade-in zoom-in duration-200 origin-top-right">
                                                            <div className="p-1.5">
                                                                <button
                                                                    onClick={() => {
                                                                        setIsMenuOpen(false)
                                                                        handleDeleteAccount()
                                                                    }}
                                                                    className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-900/20 transition-colors"
                                                                >
                                                                    <AlertTriangle className="w-4 h-4" />
                                                                    Delete account
                                                                </button>
                                                            </div>
                                                        </div>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ) : !isSubscribed ? (
                                    <form onSubmit={handleSubscribe} className="flex flex-col sm:flex-row gap-2 w-full md:w-auto">
                                        <div className="relative flex-1 sm:w-72 group">
                                            <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 group-focus-within:text-indigo-700 dark:group-focus-within:text-indigo-300 transition-colors" />
                                            <input
                                                type="email"
                                                value={email}
                                                onChange={(e) => setEmail(e.target.value)}
                                                placeholder="Your email"
                                                className="w-full pl-11 pr-4 py-2.5 rounded-full bg-white/80 ring-1 ring-slate-200 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:ring-2 focus:ring-indigo-300 dark:bg-slate-900/60 dark:ring-slate-700 dark:text-slate-100 dark:placeholder-slate-500 dark:focus:ring-indigo-500/40"
                                                required
                                            />
                                        </div>
                                        <button
                                            type="submit"
                                            disabled={isLoading}
                                            className="px-5 py-2.5 rounded-full bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                                        >
                                            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Subscribe'}
                                        </button>
                                    </form>
                                ) : (
                                    <div className="flex items-center gap-4">
                                        <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-400 text-sm">
                                            <CheckCircle className="w-4 h-4" />
                                            Subscribed
                                        </div>
                                        <button
                                            onClick={handleUnsubscribe}
                                            className="text-sm text-slate-500 hover:text-rose-600 transition-colors"
                                        >
                                            Unsubscribe
                                        </button>
                                    </div>
                                )}
                            </div>
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
                            <div className="rounded-card bg-surface-light shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 py-16 text-center">
                                <p className="font-display text-xl text-slate-950 dark:text-slate-50">Profile not found</p>
                                <button onClick={() => navigate('/')} className="mt-3 text-sm text-indigo-700 dark:text-indigo-300 hover:underline">Go home</button>
                            </div>
                        ) : bookmarks.length === 0 ? (
                            <div className="rounded-card bg-surface-light shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 py-16 text-center">
                                <p className="text-sm text-slate-500 dark:text-slate-400">No bookmarks shared yet</p>
                            </div>
                        ) : (
                            <div className="space-y-5">
                                {selectedTags.length > 0 && (
                                    <div className="flex items-center justify-between">
                                        <h2 className="text-sm text-slate-500 dark:text-slate-400">
                                            Filtering by {selectedTags.map(t => `#${t}`).join(', ')} · {filteredBookmarks.length} {filteredBookmarks.length === 1 ? 'result' : 'results'}
                                        </h2>
                                        <button
                                            onClick={clearFilters}
                                            className="text-sm text-indigo-700 hover:text-indigo-900 dark:text-indigo-300 dark:hover:text-indigo-200 transition-colors"
                                        >
                                            Clear filters
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
                                    <div className="rounded-card bg-surface-light shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 py-16 text-center">
                                        <p className="text-sm text-slate-500 dark:text-slate-400">No bookmarks match these topics</p>
                                        <button onClick={clearFilters} className="mt-3 text-sm text-indigo-700 dark:text-indigo-300 hover:underline">Clear filters</button>
                                    </div>
                                )}
                            </div>
                        )}
                    </>
                )}

                {/* Footer */}
                <div className="text-center mt-16 pt-8 border-t border-slate-200/70 dark:border-slate-800/70">
                    <a href="/" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 transition-colors">
                        Made with <span className="font-display text-base text-slate-900 dark:text-slate-100">markly</span>
                    </a>
                </div>
            </div>

            {/* Success Toast */}
            {saveSuccess && (
                <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-4 fade-in duration-300">
                    <div className="px-5 py-3 rounded-full bg-slate-900 text-white text-sm shadow-card-hover flex items-center gap-2 dark:bg-slate-100 dark:text-slate-950">
                        <CheckCircle className="w-4 h-4" />
                        Saved to your library
                    </div>
                </div>
            )}

            {/* Error/Info Toast with Retry */}
            {error && (
                <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-4 fade-in duration-300">
                    <div className={`px-5 py-3 rounded-2xl shadow-card-hover text-sm ${error?.includes('already in your collection')
                        ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-950'
                        : 'bg-rose-600 text-white'
                        }`}>
                        <div className="flex items-start gap-2">
                            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                            <div className="flex-1">
                                <p>{error}</p>
                                {retryBookmark && (
                                    <button
                                        onClick={handleRetry}
                                        className="mt-2 px-3 py-1.5 rounded-full bg-white/15 hover:bg-white/25 text-xs font-medium transition-colors"
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
