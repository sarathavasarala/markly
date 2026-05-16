import { useState } from 'react'
import { X, Loader2, AlertCircle, Plus, ArrowRight } from 'lucide-react'
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

  const [editTitle, setEditTitle] = useState('')
  const [editSummary, setEditSummary] = useState('')
  const [editTags, setEditTags] = useState<string[]>([])
  const [newTag, setNewTag] = useState('')
  const [previewData, setPreviewData] = useState<any>(null)
  const [enrichmentWarning, setEnrichmentWarning] = useState<string | null>(null)
  const [isPublic, setIsPublic] = useState(true)

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
        setEnrichmentWarning('Couldn’t fully read the page. Review the metadata below before saving.')
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

    const finalTags = [...editTags]
    const tag = newTag.trim().toLowerCase().replace(/\s+/g, '-')
    if (tag && !finalTags.includes(tag)) {
      finalTags.push(tag)
    }

    try {
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
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to save to your library')
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

  const labelClass = "block text-xs font-medium text-slate-500 dark:text-slate-400 mb-2"
  const inputClass = "w-full px-4 py-3 rounded-2xl bg-white/80 ring-1 ring-slate-200 text-slate-900 placeholder-slate-400 outline-none transition focus:ring-2 focus:ring-indigo-300 dark:bg-slate-900/60 dark:ring-slate-700 dark:text-slate-100 dark:placeholder-slate-500 dark:focus:ring-indigo-500/40"

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="fixed inset-0 bg-slate-950/40 backdrop-blur-sm transition-opacity" onClick={handleClose} />

      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative w-full max-w-4xl rounded-card bg-surface-light shadow-card-hover ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 overflow-hidden flex flex-col md:flex-row min-h-[480px]">

          <div className="w-full md:w-5/12 p-7 sm:p-8 md:border-r border-slate-200/70 dark:border-slate-800/70">
            <div className="mb-6">
              <h2 className="font-display text-3xl text-slate-950 dark:text-slate-50 leading-tight">Save a link</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Paste a URL. We'll fetch a title, summary, and topics for you to review.</p>
            </div>

            <form onSubmit={handleAnalyze} className="space-y-5">
              <div>
                <label className={labelClass}>Link</label>
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://…"
                  className={inputClass}
                  disabled={step !== 'idle'}
                  autoFocus
                />
              </div>

              <div>
                <label className={labelClass}>Notes (optional)</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Why does this matter to you?"
                  rows={5}
                  className={`${inputClass} resize-none`}
                  disabled={step !== 'idle'}
                />
              </div>

              <button
                type="submit"
                disabled={step !== 'idle' || !url.trim()}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-full bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white transition-colors disabled:opacity-50"
              >
                {step === 'analyzing' ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Reading…
                  </>
                ) : (
                  <>
                    Analyze link
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>

              {error && (
                <div className="flex items-start gap-2 px-4 py-3 rounded-2xl bg-rose-50 text-rose-700 text-sm dark:bg-rose-900/20 dark:text-rose-300">
                  <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  {error}
                </div>
              )}
            </form>
          </div>

          <div className="w-full md:w-7/12 p-7 sm:p-8 flex flex-col">
            {step === 'idle' || step === 'analyzing' ? (
              <div className="hidden md:flex flex-1 flex-col items-center justify-center text-center">
                <div className="w-14 h-14 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400 mb-5">
                  {step === 'analyzing' ? (
                    <Loader2 className="w-6 h-6 animate-spin" />
                  ) : (
                    <Plus className="w-6 h-6" />
                  )}
                </div>
                <h3 className="font-display text-2xl text-slate-950 dark:text-slate-50 mb-2">
                  {step === 'analyzing' ? 'Reading the page…' : 'Preview appears here'}
                </h3>
                <p className="max-w-sm text-sm text-slate-500 dark:text-slate-400 leading-relaxed">
                  {step === 'analyzing'
                    ? "We're extracting the title, a short summary, and a few topic suggestions."
                    : "Once you paste a link and analyze it, you'll get a draft to review and edit before saving."}
                </p>
              </div>
            ) : (
              <div className="flex-1 flex flex-col">
                <h2 className="font-display text-2xl text-slate-950 dark:text-slate-50 mb-5">Review</h2>

                {enrichmentWarning && (
                  <div className="mb-5 flex items-start gap-2 px-4 py-3 rounded-2xl bg-amber-50 text-amber-800 text-sm dark:bg-amber-900/20 dark:text-amber-300">
                    <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                    <p>{enrichmentWarning}</p>
                  </div>
                )}

                <div className="space-y-4 flex-1">
                  <div>
                    <label className={labelClass}>Title</label>
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className={inputClass}
                    />
                  </div>

                  <div>
                    <label className={labelClass}>Summary</label>
                    <textarea
                      value={editSummary}
                      onChange={(e) => setEditSummary(e.target.value)}
                      rows={4}
                      className={`${inputClass} resize-none text-sm leading-relaxed`}
                    />
                  </div>

                  <div>
                    <label className={labelClass}>Topics</label>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {editTags.map(tag => (
                        <span key={tag} className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium lowercase bg-white text-slate-600 ring-1 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700">
                          {tag}
                          <button onClick={() => removeTag(tag)} className="text-slate-400 hover:text-rose-500 transition-colors">
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
                        placeholder="Add a topic…"
                        className={`${inputClass} py-2.5 text-sm`}
                      />
                      <button
                        type="submit"
                        className="p-2.5 rounded-2xl bg-slate-100 hover:bg-slate-200 text-slate-500 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-400 transition-colors"
                      >
                        <Plus className="w-4 h-4" />
                      </button>
                    </form>
                  </div>

                  <div>
                    <label className={labelClass}>Visibility</label>
                    <div className="inline-flex rounded-full bg-slate-100/70 ring-1 ring-slate-200/70 p-1 dark:bg-slate-800/60 dark:ring-slate-700/70">
                      <button
                        onClick={() => setIsPublic(true)}
                        className={`px-4 py-1.5 rounded-full text-xs font-medium transition-colors ${isPublic
                          ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-950'
                          : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-slate-100'
                          }`}
                      >
                        Public
                      </button>
                      <button
                        onClick={() => setIsPublic(false)}
                        className={`px-4 py-1.5 rounded-full text-xs font-medium transition-colors ${!isPublic
                          ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-950'
                          : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-slate-100'
                          }`}
                      >
                        Private
                      </button>
                    </div>
                  </div>
                </div>

                <div className="mt-6 flex gap-3 pt-5 border-t border-slate-200/70 dark:border-slate-800/70">
                  <button
                    onClick={handleClose}
                    className="flex-1 py-3 rounded-full text-sm font-medium text-slate-600 hover:bg-slate-100/70 dark:text-slate-300 dark:hover:bg-slate-800/60 transition-colors"
                  >
                    Discard
                  </button>
                  <button
                    onClick={handleFinish}
                    disabled={isSubmitting}
                    className="flex-[2] py-3 rounded-full text-sm font-medium bg-slate-900 text-white hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save to library'}
                  </button>
                </div>
              </div>
            )}
          </div>

          <button
            onClick={handleClose}
            className="absolute top-4 right-4 p-2 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-100 dark:hover:text-slate-200 dark:hover:bg-slate-800 transition-colors z-10"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  )
}
