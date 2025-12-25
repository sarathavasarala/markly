import { useEffect, useRef, useState } from 'react'
import { X, Loader2, Sparkles, CheckCircle2, AlertCircle } from 'lucide-react'
import { Bookmark, bookmarksApi } from '../lib/api'
import { useBookmarksStore } from '../stores/bookmarksStore'
import BookmarkCard from './BookmarkCard'

interface AddBookmarkModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function AddBookmarkModal({ isOpen, onClose }: AddBookmarkModalProps) {
  const [url, setUrl] = useState('')
  const [description, setDescription] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [step, setStep] = useState<'idle' | 'saving' | 'enriching' | 'preview' | 'failed'>('idle')
  const [preview, setPreview] = useState<Bookmark | null>(null)
  const pollRef = useRef<NodeJS.Timeout | null>(null)
  
  const createBookmark = useBookmarksStore((state) => state.createBookmark)
  const refreshBookmark = useBookmarksStore((state) => state.refreshBookmark)
  const upsertBookmark = useBookmarksStore((state) => state.upsertBookmark)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (step === 'preview' && preview) {
      handleFinish()
      return
    }
    setError('')
    
    if (!url.trim()) {
      setError('URL is required')
      return
    }
    
    // Basic URL validation - add https if missing
    let finalUrl = url.trim()
    if (!finalUrl.startsWith('http://') && !finalUrl.startsWith('https://')) {
      finalUrl = 'https://' + finalUrl
    }
    
    try {
      new URL(finalUrl)
    } catch {
      setError('Please enter a valid URL')
      return
    }
    
    setIsSubmitting(true)
    setStep('saving')
    
    try {
      // Pass description to skip scraping if provided (for Twitter, etc.)
      const bookmark = await createBookmark(finalUrl, undefined, description.trim() || undefined)
      
      if (bookmark) {
        setStep('enriching')
        startPolling(bookmark.id)
      } else {
        setError('Failed to create bookmark')
        setStep('failed')
      }
    } catch {
      setError('Failed to create bookmark')
      setStep('failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  const startPolling = (id: string) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        await refreshBookmark(id)
      } catch {
        // ignore poll errors
      }
      try {
        const res = await fetchPreview(id)
        if (res) {
          clearPoll()
          setPreview(res)
          upsertBookmark(res)
          setStep(res.enrichment_status === 'completed' ? 'preview' : 'failed')
        }
      } catch {
        // ignore and continue polling
      }
    }, 1500)
  }

  const clearPoll = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const fetchPreview = async (id: string) => {
    try {
      const res = await bookmarksApi.get(id)
      const data: Bookmark = res.data
      if (data.enrichment_status === 'completed' || data.enrichment_status === 'failed') {
        return data
      }
    } catch {
      return null
    }
    return null
  }

  const handleClose = () => {
    clearPoll()
    setUrl('')
    setDescription('')
    setError('')
    setPreview(null)
    setStep('idle')
    onClose()
  }

  const handleFinish = () => {
    if (preview) {
      upsertBookmark(preview)
    }
    handleClose()
    // Ensure the new bookmark is visible in lists
    setTimeout(() => {
      window.location.reload()
    }, 100)
  }

  useEffect(() => {
    return () => clearPoll()
  }, [])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 transition-opacity"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative w-full max-w-lg bg-white dark:bg-gray-800 rounded-xl shadow-xl">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Add Bookmark
            </h2>
            <button
              onClick={handleClose}
              className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          
          {/* Form */}
          <form onSubmit={handleSubmit} className="p-4 space-y-4">
            {error && (
              <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm rounded-lg">
                {error}
              </div>
            )}
            
            <div>
              <label 
                htmlFor="url" 
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                URL
              </label>
              <input
                type="text"
                id="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="Paste any link..."
                className="w-full px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                autoFocus
              />
            </div>
            
            <div>
              <label 
                htmlFor="description" 
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Description{' '}
                <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Paste tweet text, add context, or describe what this is about. Great for pages we can't scrape (Twitter, Instagram, etc.)"
                rows={4}
                className="w-full px-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
              />
            </div>
            
            {/* AI info */}
            <div className="flex items-start gap-2 p-3 bg-primary-50 dark:bg-primary-900/20 rounded-lg">
              <Sparkles className="w-4 h-4 text-primary-500 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-primary-700 dark:text-primary-300">
                We'll extract the page, summarize it, and add tags. Keep this open to see progress and the preview before closing.
                {description && ' Your description will be used instead of scraping the page.'}
              </p>
            </div>

            {/* Progress / Preview */}
            {(step !== 'idle' || preview) && (
              <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-3 space-y-3">
                <div className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-200">
                  {step === 'preview' ? (
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                  ) : step === 'failed' ? (
                    <AlertCircle className="w-4 h-4 text-red-500" />
                  ) : (
                    <Loader2 className="w-4 h-4 animate-spin text-primary-600" />
                  )}
                  {step === 'saving' && 'Saving bookmark...'}
                  {step === 'enriching' && 'Running AI enrichment...'}
                  {step === 'preview' && 'Enrichment complete. Preview below.'}
                  {step === 'failed' && 'Enrichment failed. The bookmark was saved; you can retry later.'}
                </div>

                {preview && (
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                    <BookmarkCard bookmark={preview} />
                  </div>
                )}
              </div>
            )}
            
            {/* Actions */}
            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={handleClose}
                disabled={isSubmitting}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type={step === 'preview' ? 'button' : 'submit'}
                onClick={step === 'preview' ? handleFinish : undefined}
                disabled={isSubmitting || (!url.trim() && step !== 'preview')}
                className="flex items-center gap-2 px-5 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
              >
                {step === 'preview' ? (
                  'Save'
                ) : isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {step === 'enriching' ? 'Enriching...' : 'Saving...'}
                  </>
                ) : (
                  'Save'
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
