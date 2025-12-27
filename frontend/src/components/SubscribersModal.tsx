import { useState, useEffect } from 'react'
import { X, Mail, Calendar, Loader2, Trash2 } from 'lucide-react'
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
                    console.log(`Fetching subscribers for curator: ${username}`)
                    const res = await publicApi.listSubscribers(username)
                    console.log('Subscribers response:', res.data)
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
        if (!window.confirm(`Are you sure you want to stop ${email} from being subscribed?`)) return

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
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-gray-950/60 backdrop-blur-sm"
                onClick={onClose}
            />

            {/* Modal */}
            <div className="relative w-full max-w-lg bg-white dark:bg-gray-900 rounded-3xl shadow-2xl overflow-hidden border border-gray-200 dark:border-gray-800 animate-in fade-in zoom-in duration-200">
                <div className="p-6 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
                    <div>
                        <h3 className="text-xl font-bold text-gray-900 dark:text-white">Subscribers</h3>
                        <p className="text-sm text-gray-500 dark:text-gray-400">People who signed up for your digest</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="p-0 max-h-[60vh] overflow-y-auto">
                    {isLoading ? (
                        <div className="flex flex-col items-center justify-center py-20">
                            <Loader2 className="w-8 h-8 animate-spin text-primary-600 mb-2" />
                            <p className="text-sm text-gray-500">Loading subscribers...</p>
                        </div>
                    ) : error ? (
                        <div className="flex flex-col items-center justify-center py-20 px-6 text-center">
                            <div className="w-16 h-16 rounded-3xl bg-red-50 dark:bg-red-900/20 flex items-center justify-center mb-4">
                                <X className="w-8 h-8 text-red-500" />
                            </div>
                            <p className="text-red-600 dark:text-red-400 font-medium">{error}</p>
                            <button
                                onClick={() => window.location.reload()}
                                className="mt-4 text-sm text-primary-600 hover:underline"
                            >
                                Try refreshing the page
                            </button>
                        </div>
                    ) : subscribers.length > 0 ? (
                        <ul className="divide-y divide-gray-50 dark:divide-gray-800">
                            {subscribers.map((sub, idx) => (
                                <li key={idx} className="px-6 py-4 flex items-center justify-between group hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center">
                                            <Mail className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                                        </div>
                                        <div>
                                            <p className="text-sm font-semibold text-gray-900 dark:text-white">{sub.email}</p>
                                            <div className="flex items-center gap-1.5 text-[10px] text-gray-500 uppercase tracking-widest font-black mt-0.5">
                                                <Calendar className="w-3 h-3" />
                                                Subscribed on {new Date(sub.subscribed_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                                            </div>
                                        </div>
                                    </div>

                                    <button
                                        onClick={() => handleDelete(sub.email)}
                                        className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/10 rounded-lg transition-all opacity-0 group-hover:opacity-100"
                                        title="Remove subscriber"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <div className="flex flex-col items-center justify-center py-20 px-6 text-center">
                            <div className="w-16 h-16 rounded-3xl bg-gray-50 dark:bg-gray-800 flex items-center justify-center mb-4">
                                <Mail className="w-8 h-8 text-gray-300" />
                            </div>
                            <p className="text-gray-500 dark:text-gray-400 font-medium">No subscribers yet</p>
                            <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">Share your profile link to get started</p>
                        </div>
                    )}
                </div>

                <div className="p-4 bg-gray-50 dark:bg-gray-800/30 text-center border-t border-gray-100 dark:border-gray-800">
                    <p className="text-[10px] text-gray-400 uppercase font-black tracking-widest">
                        {subscribers.length} {subscribers.length === 1 ? 'subscriber' : 'subscribers'} total
                    </p>
                </div>
            </div>
        </div>
    )
}
