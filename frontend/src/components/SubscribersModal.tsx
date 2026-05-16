import { useState, useEffect } from 'react'
import { X, Mail, Loader2, Trash2 } from 'lucide-react'
import { publicApi } from '../lib/api'

interface Subscriber {
    email: string
    subscribed_at: string
}

interface SubscribersModalProps {
    isOpen: boolean
    onClose: () => void
    username: string
}

export default function SubscribersModal({ isOpen, onClose, username }: SubscribersModalProps) {
    const [subscribers, setSubscribers] = useState<Subscriber[]>([])
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (isOpen && username) {
            const fetchSubscribers = async () => {
                setIsLoading(true)
                setError(null)
                try {
                    const res = await publicApi.listSubscribers(username)
                    setSubscribers(res.data.subscribers || [])
                } catch (error: any) {
                    console.error('Failed to fetch subscribers:', error)
                    setError(error.response?.data?.error || 'Failed to load subscribers list')
                } finally {
                    setIsLoading(false)
                }
            }
            fetchSubscribers()
        }
    }, [isOpen, username])

    const handleDelete = async (email: string) => {
        if (!window.confirm(`Stop ${email} from being subscribed?`)) return
        try {
            await publicApi.deleteSubscriber(username, email)
            setSubscribers(prev => prev.filter(s => s.email !== email))
        } catch (error: any) {
            console.error('Failed to delete subscriber:', error)
            alert('Failed to delete subscriber. Please try again.')
        }
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div
                className="absolute inset-0 bg-slate-950/40 backdrop-blur-sm"
                onClick={onClose}
            />

            <div className="relative w-full max-w-lg rounded-card bg-surface-light shadow-card-hover ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 overflow-hidden animate-in fade-in zoom-in duration-200">
                <div className="px-6 py-5 flex items-center justify-between">
                    <div>
                        <h3 className="font-display text-2xl text-slate-950 dark:text-slate-50">Subscribers</h3>
                        <p className="text-sm text-slate-500 dark:text-slate-400">People who signed up for your digest</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:text-slate-200 dark:hover:bg-slate-800 transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="max-h-[60vh] overflow-y-auto">
                    {isLoading ? (
                        <div className="flex flex-col items-center justify-center py-16">
                            <Loader2 className="w-6 h-6 animate-spin text-slate-400 mb-2" />
                            <p className="text-sm text-slate-500">Loading subscribers…</p>
                        </div>
                    ) : error ? (
                        <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
                            <p className="text-rose-600 dark:text-rose-400 font-medium">{error}</p>
                            <button
                                onClick={() => window.location.reload()}
                                className="mt-3 text-sm text-indigo-700 dark:text-indigo-300 hover:underline"
                            >
                                Refresh the page
                            </button>
                        </div>
                    ) : subscribers.length > 0 ? (
                        <ul className="divide-y divide-slate-100 dark:divide-slate-800/60">
                            {subscribers.map((sub, idx) => (
                                <li key={idx} className="px-6 py-3 flex items-center justify-between group hover:bg-slate-50/60 dark:hover:bg-slate-900/40 transition-colors">
                                    <div className="flex items-center gap-3 min-w-0">
                                        <div className="w-9 h-9 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-500 dark:text-slate-400 shrink-0">
                                            <Mail className="w-4 h-4" />
                                        </div>
                                        <div className="min-w-0">
                                            <p className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">{sub.email}</p>
                                            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                                                Subscribed {new Date(sub.subscribed_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                                            </p>
                                        </div>
                                    </div>

                                    <button
                                        onClick={() => handleDelete(sub.email)}
                                        className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-900/20 rounded-xl transition-all opacity-0 group-hover:opacity-100"
                                        title="Remove subscriber"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
                            <div className="w-12 h-12 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center mb-3 text-slate-400">
                                <Mail className="w-6 h-6" />
                            </div>
                            <p className="text-slate-700 dark:text-slate-200 font-medium">No subscribers yet</p>
                            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Share your profile link to get started.</p>
                        </div>
                    )}
                </div>

                <div className="px-6 py-3 text-center border-t border-slate-200/70 dark:border-slate-800/70">
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                        {subscribers.length} {subscribers.length === 1 ? 'subscriber' : 'subscribers'} total
                    </p>
                </div>
            </div>
        </div>
    )
}
