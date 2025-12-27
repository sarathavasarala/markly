import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookMarked, Mail, CheckCircle, Loader2, ExternalLink, Bookmark, Eye, EyeOff, Plus, Copy, Check } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'

interface Bookmark {
    id: string
    url: string
    original_title: string
    clean_title: string
    user_description?: string
    ai_summary?: string
    auto_tags?: string[]
    domain?: string
    favicon_url?: string
    created_at: string
    is_public: boolean
}

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

    // Check if current user is the owner of this profile locally
    const currentUserUsername = user?.email?.split('@')[0]?.toLowerCase()
    const isOwner = (isAuthenticated && currentUserUsername === username?.toLowerCase()) || backendIsOwner

    // Get full name and first name for display
    const fullName = profileMetadata?.full_name || username || ''
    const firstName = fullName.split(' ')[0] || username || ''

    const formatDate = (dateStr: string | null | undefined) => {
        if (!dateStr) return '—'
        const d = new Date(dateStr)
        if (Number.isNaN(d.getTime())) return '—'
        const now = new Date()

        // Normalize dates to midnight to compare calendar days
        const d1 = new Date(d.getFullYear(), d.getMonth(), d.getDate())
        const d2 = new Date(now.getFullYear(), now.getMonth(), now.getDate())

        const diffMs = d2.getTime() - d1.getTime()
        const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24))

        if (diffDays === 0) return 'Added today'
        if (diffDays === 1) return 'Added yesterday'
        if (diffDays < 7) return `Added ${diffDays} days ago`
        return `Added ${d.toLocaleDateString()}`
    }

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

    useEffect(() => {
        if (username) {
            document.title = `${firstName}'s Reads on Markly`
        }
        return () => {
            document.title = 'Markly'
        }
    }, [username, firstName])

    return (
        <div className="min-h-screen bg-gray-950 text-gray-200 selection:bg-primary-500/30">
            {/* Background effects */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-[400px] bg-gradient-to-b from-primary-950/20 to-transparent" />
                <div className="absolute top-[5%] left-[5%] w-96 h-96 bg-primary-600/5 rounded-full blur-[128px]" />
                <div className="absolute top-[10%] right-[5%] w-96 h-96 bg-blue-600/5 rounded-full blur-[128px]" />
            </div>

            <div className="relative max-w-[1600px] mx-auto px-6 py-8 sm:py-16">
                {/* Hero Curation Unit */}
                <div className="flex flex-col items-center text-center mb-12 sm:mb-20">
                    {/* Profile Identity Section */}
                    <div className="flex flex-col items-center mb-10">
                        <div className="relative group mb-6">
                            <div className="absolute -inset-1.5 bg-gradient-to-tr from-primary-500 to-blue-500 rounded-3xl blur opacity-25 group-hover:opacity-40 transition duration-1000 group-hover:duration-200"></div>
                            {profileMetadata?.avatar_url ? (
                                <img
                                    src={profileMetadata.avatar_url}
                                    alt={fullName}
                                    className="relative w-20 h-20 sm:w-24 h-24 rounded-3xl object-cover border-2 border-gray-950 shadow-2xl transition-transform duration-500 group-hover:scale-[1.02]"
                                    onError={(e) => {
                                        (e.target as HTMLImageElement).src = `https://ui-avatars.com/api/?name=${fullName}&background=6366f1&color=fff&size=128`
                                    }}
                                />
                            ) : (
                                <div className="relative w-20 h-20 sm:w-24 h-24 bg-gray-900 rounded-3xl flex items-center justify-center border-2 border-gray-950 shadow-2xl">
                                    <BookMarked className="w-10 h-10 text-primary-500" />
                                </div>
                            )}
                        </div>

                        <h1 className="text-4xl sm:text-5xl font-black text-white tracking-tight mb-4">
                            {firstName}'s Reads
                        </h1>

                        <p className="text-gray-400 text-sm sm:text-base font-medium max-w-xl mx-auto leading-relaxed">
                            A collection of interesting reads, curated by <span className="text-white font-bold">{fullName}.</span>
                        </p>
                    </div>

                    {/* Integrated Stats & Notify Bar */}
                    <div className="w-full max-w-4xl bg-gray-900/40 backdrop-blur-2xl border border-gray-800 rounded-2xl p-2 sm:p-2 sm:pl-8 shadow-[0_20px_50px_rgba(0,0,0,0.5)] flex flex-col sm:flex-row items-center gap-6 sm:gap-10">
                        {/* High-Impact Stats */}
                        <div className="flex items-center gap-10 py-3 sm:py-0 px-8 sm:px-0">
                            <div className="flex flex-col items-center sm:items-start min-w-[60px]">
                                <span className="text-xl font-black text-white leading-none">{totalCount}</span>
                                <span className="text-[10px] uppercase tracking-[0.2em] text-gray-500 font-black mt-2">Reads</span>
                            </div>
                            <div className="w-px h-8 bg-gray-800 hidden sm:block" />
                            <div className="flex flex-col items-center sm:items-start min-w-[80px]">
                                <span className="text-xl font-black text-white leading-none">{subscriberCount}</span>
                                <span className="text-[10px] uppercase tracking-[0.2em] text-gray-500 font-black mt-2">Subscribers</span>
                            </div>
                        </div>

                        {/* Integrated Action Area */}
                        <div className="flex-1 w-full flex items-center border-t sm:border-t-0 sm:border-l border-gray-800">
                            {isOwner ? (
                                <div className="flex-1 flex items-center justify-between p-1 pl-8">
                                    <div className="flex flex-col items-start">
                                        <span className="text-[10px] font-black uppercase tracking-widest text-primary-500 mb-0.5">Your Public Link</span>
                                        <span className="text-sm font-bold text-gray-400 truncate max-w-[250px] sm:max-w-md">{window.location.origin}/@{username}</span>
                                    </div>
                                    <button
                                        onClick={handleCopyProfileLink}
                                        className="h-12 px-6 bg-gray-800 hover:bg-gray-700 text-white font-black uppercase tracking-widest text-[10px] rounded-xl transition-all flex items-center gap-2 active:scale-95"
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
                                <form onSubmit={handleSubscribe} className="flex flex-1 items-center p-1">
                                    <div className="flex-1 flex items-center px-4">
                                        <Mail className="w-4 h-4 text-gray-600 mr-3 hidden sm:block" />
                                        <input
                                            type="email"
                                            value={email}
                                            onChange={(e) => setEmail(e.target.value)}
                                            placeholder="Enter email to stay updated"
                                            className="w-full bg-transparent border-none text-white placeholder-gray-500 focus:outline-none focus:ring-0 text-sm font-bold"
                                            required
                                        />
                                    </div>
                                    <button
                                        type="submit"
                                        disabled={isLoading}
                                        className="h-12 px-8 bg-primary-600 hover:bg-primary-500 text-white font-black uppercase tracking-widest text-[10px] rounded-xl transition-all shadow-lg shadow-primary-600/20 active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2"
                                    >
                                        {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Notify Me'}
                                    </button>
                                </form>
                            ) : (
                                <div className="flex-1 h-12 flex items-center justify-center sm:justify-start px-8 gap-3 text-green-400">
                                    <CheckCircle className="w-4 h-4" />
                                    <span className="text-[11px] font-black uppercase tracking-widest">You're on the list!</span>
                                </div>
                            )}
                        </div>
                    </div>
                    {error && <p className="text-red-400 text-[10px] mt-4 font-black uppercase tracking-widest animate-pulse">{error}</p>}
                </div>

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
                    <div className="columns-1 sm:columns-2 lg:columns-3 xl:columns-4 2xl:columns-5 gap-6 space-y-6 max-w-full">
                        {bookmarks.map((bookmark) => (
                            <div key={bookmark.id} className="break-inside-avoid">
                                <div className={`group bg-gray-900/40 border-2 border-gray-800 hover:border-primary-500/50 rounded-2xl overflow-hidden transition-all duration-300 hover:shadow-2xl hover:shadow-primary-500/10 ${!bookmark.is_public && isOwner ? 'opacity-60 bg-gray-900/20 border-dashed' : ''}`}>
                                    <div className="p-6">
                                        <div className="flex items-center justify-between mb-4">
                                            <div className="flex items-center gap-3 min-w-0">
                                                <div className="w-10 h-10 bg-gray-800 rounded-xl flex items-center justify-center shrink-0 shadow-inner">
                                                    {bookmark.favicon_url ? (
                                                        <img src={bookmark.favicon_url} alt="" className="w-6 h-6 object-contain" />
                                                    ) : (
                                                        <BookMarked className="w-5 h-5 text-gray-500" />
                                                    )}
                                                </div>
                                                <div className="min-w-0">
                                                    <p className="text-gray-500 text-[10px] font-black uppercase tracking-widest truncate">{bookmark.domain}</p>
                                                    <p className="text-gray-600 text-[9px] font-bold mt-0.5">{formatDate(bookmark.created_at)}</p>
                                                </div>
                                            </div>
                                            {isOwner && (
                                                <button
                                                    onClick={() => toggleBookmarkVisibility(bookmark)}
                                                    className={`p-2 rounded-lg transition-colors ${bookmark.is_public ? 'text-primary-400 hover:bg-primary-400/10' : 'text-gray-600 hover:bg-gray-600/10'}`}
                                                    title={bookmark.is_public ? 'Public' : 'Private'}
                                                >
                                                    {bookmark.is_public ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                                                </button>
                                            )}
                                        </div>

                                        <h3 className="text-white font-bold text-xl leading-snug mb-3 group-hover:text-primary-400 transition-colors line-clamp-2">
                                            <a href={bookmark.url} target="_blank" rel="noopener noreferrer">
                                                {bookmark.clean_title || bookmark.original_title || 'Untitled'}
                                            </a>
                                        </h3>

                                        {bookmark.ai_summary && (
                                            <p className="text-gray-400 text-sm leading-relaxed mb-6 line-clamp-4 font-medium opacity-80">
                                                {bookmark.ai_summary}
                                            </p>
                                        )}

                                        {bookmark.auto_tags && bookmark.auto_tags.length > 0 && (
                                            <div className="flex flex-wrap gap-2 mb-6">
                                                {bookmark.auto_tags.slice(0, 3).map((tag) => (
                                                    <span key={tag} className="px-2.5 py-1 bg-gray-800 text-gray-500 text-[10px] font-black uppercase tracking-widest rounded-lg border border-gray-700/50">
                                                        {tag}
                                                    </span>
                                                ))}
                                            </div>
                                        )}

                                        <div className="flex items-center gap-3 pt-5 border-t border-gray-800/50">
                                            {isOwner ? (
                                                <button
                                                    onClick={() => toggleBookmarkVisibility(bookmark)}
                                                    className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all active:scale-95 ${bookmark.is_public ? 'bg-gray-800 hover:bg-gray-700 text-gray-400' : 'bg-primary-600 hover:bg-primary-500 text-white shadow-lg shadow-primary-600/20'}`}
                                                >
                                                    {bookmark.is_public ? (
                                                        <>
                                                            <EyeOff className="w-4 h-4" /> Make Private
                                                        </>
                                                    ) : (
                                                        <>
                                                            <Eye className="w-4 h-4" /> Make Public
                                                        </>
                                                    )}
                                                </button>
                                            ) : (
                                                <button
                                                    onClick={async () => {
                                                        if (!isAuthenticated) {
                                                            navigate(`/login?redirect=/@${username}&save=${bookmark.id}`)
                                                        } else {
                                                            try {
                                                                const { bookmarksApi } = await import('../lib/api')
                                                                await bookmarksApi.savePublic(bookmark.id)
                                                                // Optional: show a toast
                                                            } catch (err) {
                                                                console.error('Failed to save public bookmark:', err)
                                                            }
                                                        }
                                                    }}
                                                    className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-primary-600 hover:bg-primary-500 text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-lg shadow-primary-600/20 active:scale-95"
                                                >
                                                    <Plus className="w-4 h-4" /> Save
                                                </button>
                                            )}
                                            <a
                                                href={bookmark.url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="w-12 h-12 flex items-center justify-center bg-gray-800 hover:bg-gray-700 text-gray-400 rounded-xl transition-all shrink-0"
                                            >
                                                <ExternalLink className="w-5 h-5" />
                                            </a>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {/* Footer */}
                <div className="text-center mt-20 pt-10 border-t border-gray-900">
                    <a href="/" className="inline-flex items-center gap-2 text-gray-600 hover:text-primary-500 text-xs font-black uppercase tracking-[0.2em] transition-all">
                        Powered by <BookMarked className="w-4 h-4 shrink-0" /> Markly
                    </a>
                </div>
            </div>
        </div>
    )
}
