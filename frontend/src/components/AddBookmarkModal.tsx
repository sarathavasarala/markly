import { useState } from 'react'
import { X, Loader2, Sparkles, CheckCircle2, AlertCircle, Plus } from 'lucide-react'
import { bookmarksApi } from '../lib/api'
import { useBookmarksStore } from '../stores/bookmarksStore'

interface AddBookmarkModalProps {
  isOpen: boolean
  onClose: () => void
  folderId?: string | null
}


export default function AddBookmarkModal({ isOpen, onClose, folderId }: AddBookmarkModalProps) {
  const [url, setUrl] = useState('')
  const [description, setDescription] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [step, setStep] = useState<'idle' | 'analyzing' | 'curating' | 'failed'>('idle')

  // Curator state
  const [editTitle, setEditTitle] = useState('')
  const [editSummary, setEditSummary] = useState('')
  const [editTags, setEditTags] = useState<string[]>([])
  const [newTag, setNewTag] = useState('')
  const [previewData, setPreviewData] = useState<any>(null)
  const [enrichmentWarning, setEnrichmentWarning] = useState<string | null>(null)
  const [isPublic, setIsPublic] = useState(true) // Default to public

  const createBookmark = useBookmarksStore((state: any) => state.createBookmark)

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setEnrichmentWarning(null)

    if (!url.trim()) {
      setError('Please paste a link first')
      return
    }

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
    setStep('analyzing')

    try {
      const resp = await bookmarksApi.analyze(finalUrl, description.trim() || undefined)
      const data = resp.data

      setPreviewData(data)
      setEditTitle(data.clean_title || data.original_title || '')
      setEditSummary(data.ai_summary || '')
      setEditTags(data.auto_tags || [])

      if (!data.scrape_success) {
        setEnrichmentWarning('Scraping failed: content could not be extracted. Please review AI guessed metadata.')
      }

      setStep('curating')
    } catch (err: any) {
      setError(err.response?.data?.error || 'Analysis failed. Please try again.')
      setStep('idle')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleFinish = async () => {
    if (!previewData) return
    setIsSubmitting(true)
    setError('')

    // Auto-flush current tag input if not empty
    const finalTags = [...editTags]
    const tag = newTag.trim().toLowerCase().replace(/\s+/g, '-')
    if (tag && !finalTags.includes(tag)) {
      finalTags.push(tag)
    }

    try {
      // Create the bookmark with ALL the curated data
      await createBookmark(
        url,
        description.trim() || undefined,
        undefined,
        {
          ...previewData,
          clean_title: editTitle,
          ai_summary: editSummary,
          auto_tags: finalTags,
          is_public: isPublic,
          folder_id: folderId,
        }
      )
      handleClose()
      // No reload needed - Zustand store already updated the bookmark list
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to save to collection')
      setIsSubmitting(false)
    }
  }

  const handleClose = () => {
    setUrl('')
    setDescription('')
    setError('')
    setPreviewData(null)
    setEditTitle('')
    setEditSummary('')
    setEditTags([])
    setEnrichmentWarning(null)
    setIsPublic(true)
    setStep('idle')
    setIsSubmitting(false)
    onClose()
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

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity" onClick={handleClose} />

      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative w-full max-w-5xl bg-white dark:bg-gray-900 rounded-2xl shadow-2xl overflow-hidden flex flex-col md:flex-row min-h-[500px]">

          {/* Left Pane - Input */}
          <div className="w-full md:w-5/12 p-8 border-b md:border-b-0 md:border-r border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/20">
            <div className="mb-8">
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Capture</h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">Paste a link and add optional context for the AI.</p>
            </div>

            <form onSubmit={handleAnalyze} className="space-y-6">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Direct Link</label>
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="Paste article, blog, or newsletter link..."
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 outline-none transition-all shadow-sm"
                  disabled={step !== 'idle'}
                  autoFocus
                />
              </div>


              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Context / Notes (Optional)</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What is this about? Paste related text or your own thoughts..."
                  rows={6}
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 outline-none transition-all resize-none shadow-sm"
                  disabled={step !== 'idle'}
                />
              </div>

              <button
                type="submit"
                disabled={step !== 'idle' || !url.trim()}
                className="w-full flex items-center justify-center gap-2 py-4 bg-primary-600 hover:bg-primary-700 disabled:bg-gray-300 dark:disabled:bg-gray-700 text-white rounded-xl font-bold transition-all shadow-lg hover:shadow-primary-500/20 active:scale-[0.98]"
              >
                {step === 'analyzing' ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    Analyze Link
                  </>
                )}
              </button>

              {error && (
                <div className="flex items-start gap-2 p-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm rounded-xl border border-red-100 dark:border-red-900/30">
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  {error}
                </div>
              )}
            </form>
          </div>

          {/* Right Pane - Curator */}
          <div className="w-full md:w-7/12 p-8 flex flex-col bg-white dark:bg-gray-900">
            {step === 'idle' || step === 'analyzing' ? (
              <div className="hidden md:flex flex-1 flex-col items-center justify-center text-center p-8">
                <div className="w-20 h-20 bg-gray-50 dark:bg-gray-800 rounded-2xl flex items-center justify-center mb-6 border border-gray-100 dark:border-gray-700">
                  <Sparkles className={`w-10 h-10 ${step === 'analyzing' ? 'text-primary-500 animate-pulse' : 'text-gray-300'}`} />
                </div>
                <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">Analysis</h3>
                <p className="text-gray-500 dark:text-gray-400 max-w-sm">
                  {step === 'analyzing'
                    ? "markly is extracting content and generating metadata for you to review."
                    : "Paste your link to get started. markly will recommend a description and tags based on the page content, which you can easily review and edit right here."}
                </p>
                {step === 'analyzing' && (
                  <div className="mt-8 flex items-center gap-3 px-4 py-2 bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400 rounded-full text-sm font-medium">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Reading current page...
                  </div>
                )}
              </div>
            ) : (
              <div className="flex-1 flex flex-col">
                <div className="flex items-center justify-between mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Curate</h2>
                  <div className="flex items-center gap-2 px-3 py-1 bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 rounded-lg text-sm font-bold border border-green-100 dark:border-green-900/30">
                    <CheckCircle2 className="w-4 h-4" /> Ready
                  </div>
                </div>

                {enrichmentWarning && (
                  <div className="mb-6 flex items-start gap-3 p-4 bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 text-sm rounded-xl border border-amber-100 dark:border-amber-900/30">
                    <AlertCircle className="w-5 h-5 flex-shrink-0" />
                    <p>{enrichmentWarning}</p>
                  </div>
                )}

                <div className="space-y-6 flex-1">
                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Clean Title</label>
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 outline-none transition-all font-medium"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">AI Summary</label>
                    <textarea
                      value={editSummary}
                      onChange={(e) => setEditSummary(e.target.value)}
                      rows={4}
                      className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-primary-500 outline-none transition-all resize-none text-sm leading-relaxed"
                    />
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
                      <button
                        type="submit"
                        className="p-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg text-gray-500 dark:text-gray-400 transition-colors"
                      >
                        <Plus className="w-5 h-5" />
                      </button>
                    </form>
                    <div className="mt-6">
                      <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Visibility</label>
                      <button
                        onClick={() => setIsPublic(!isPublic)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all border ${isPublic
                          ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border-green-100 dark:border-green-900/30'
                          : 'bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-gray-100 dark:border-gray-700'
                          }`}
                      >
                        {isPublic ? (
                          <>
                            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                            Public (Shared to profile)
                          </>
                        ) : (
                          <>
                            <div className="w-2 h-2 rounded-full bg-gray-400" />
                            Private (Only you)
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                <div className="mt-8 flex gap-4 pt-6 border-t border-gray-100 dark:border-gray-800">
                  <button
                    onClick={handleClose}
                    className="flex-1 px-6 py-4 text-gray-600 dark:text-gray-400 font-bold hover:bg-gray-50 dark:hover:bg-gray-800 rounded-xl transition-colors"
                  >
                    Discard
                  </button>
                  <button
                    onClick={handleFinish}
                    disabled={isSubmitting}
                    className="flex-[2] px-6 py-4 bg-gray-900 dark:bg-white text-white dark:text-gray-900 rounded-xl font-bold transition-all shadow-xl hover:shadow-gray-500/20 active:scale-[0.98] flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {isSubmitting ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <>
                        <CheckCircle2 className="w-5 h-5" />
                        Add to Collection
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Close button - top right */}
          <button
            onClick={handleClose}
            className="absolute top-4 right-4 p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors z-10"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
      </div>
    </div>
  )
}

