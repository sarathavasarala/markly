import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect, useCallback, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { bookmarksApi, BookmarkArchive } from '../lib/api'
import {
  ArrowLeft,
  ExternalLink,
  Loader2,
  AlertCircle,
  RefreshCw,
  BookOpen,
  Clock,
  Edit3,
  Eye,
  FileText,
  Check,
  X,
  Bold,
  Italic,
  Heading2,
  Heading3,
  List,
  ListOrdered,
  Quote,
  Code,
  Link as LinkIcon,
} from 'lucide-react'

export default function BookmarkReader() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [archive, setArchive] = useState<BookmarkArchive | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isRetrying, setIsRetrying] = useState(false)

  // Edit mode state
  const [isEditing, setIsEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [editFormat, setEditFormat] = useState<'markdown' | 'text'>('markdown')
  const [editTab, setEditTab] = useState<'write' | 'preview'>('write')
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const loadArchive = useCallback(async (showLoading = true) => {
    if (!id) return
    if (showLoading) setIsLoading(true)
    setError(null)
    try {
      const res = await bookmarksApi.getArchive(id)
      setArchive(res.data)
    } catch (err: any) {
      if (err.response?.status === 409 && err.response?.data) {
        setArchive(err.response.data)
      } else {
        setError(err.response?.data?.error || 'Failed to load article archive.')
      }
    } finally {
      setIsLoading(false)
    }
  }, [id])

  useEffect(() => {
    loadArchive()
  }, [id, loadArchive])

  // Poll for changes if status is pending or processing (only when not actively editing)
  useEffect(() => {
    if (!archive || isEditing) return
    const status = archive.archive_status
    if (status === 'pending' || status === 'processing') {
      const interval = setInterval(() => {
        loadArchive(false)
      }, 3000)
      return () => clearInterval(interval)
    }
  }, [archive, isEditing, loadArchive])

  const handleStartEdit = () => {
    setEditContent(archive?.archive_content || '')
    setEditFormat(archive?.archive_format || 'markdown')
    setEditTab('write')
    setSaveError(null)
    setSaveSuccess(false)
    setIsEditing(true)
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
    setSaveError(null)
  }

  const handleSaveArchive = async () => {
    if (!id) return
    setIsSaving(true)
    setSaveError(null)
    try {
      const res = await bookmarksApi.updateArchive(id, {
        archive_content: editContent,
        archive_format: editFormat,
      })
      setArchive(res.data)
      setIsEditing(false)
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err: any) {
      setSaveError(err.response?.data?.error || 'Failed to save changes to offline copy.')
    } finally {
      setIsSaving(false)
    }
  }

  const insertMarkdown = (prefix: string, suffix = '') => {
    const textarea = textareaRef.current
    if (!textarea) return
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const selectedText = editContent.substring(start, end)
    const replacement = prefix + (selectedText || 'text') + suffix
    const newContent = editContent.substring(0, start) + replacement + editContent.substring(end)
    setEditContent(newContent)
    setTimeout(() => {
      textarea.focus()
      const newPos = start + prefix.length + (selectedText.length || 4)
      textarea.setSelectionRange(newPos, newPos)
    }, 0)
  }

  const handleRetry = async () => {
    if (!id) return
    setIsRetrying(true)
    try {
      await bookmarksApi.retryArchive(id)
      setArchive((prev) =>
        prev
          ? {
              ...prev,
              archive_status: 'pending' as const,
              archive_error: null,
            }
          : null
      )
      await loadArchive(false)
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to restart archiving.')
    } finally {
      setIsRetrying(false)
    }
  }

  const formatDateTime = (dateStr: string | null) => {
    if (!dateStr) return ''
    return new Date(dateStr).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    })
  }

  const readingTime = (wordCount: number | null) => {
    if (!wordCount) return '1 min read'
    const wordsPerMinute = 225
    const minutes = Math.ceil(wordCount / wordsPerMinute)
    return `${minutes} min read`
  }

  const liveWordCount = editContent ? editContent.trim().split(/\s+/).filter(Boolean).length : 0
  const liveCharCount = editContent.length

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-slate-500 dark:text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-slate-500 mb-4" />
        <p className="text-sm font-medium">Loading saved copy...</p>
      </div>
    )
  }

  if (error && !archive) {
    return (
      <div className="max-w-2xl mx-auto my-8 p-6 bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/40 rounded-card flex flex-col items-center text-center">
        <AlertCircle className="w-10 h-10 text-rose-500 dark:text-rose-400 mb-4" />
        <h3 className="font-display text-xl text-slate-900 dark:text-white mb-2">Error Loading Archive</h3>
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-6">{error}</p>
        <button
          onClick={() => loadArchive()}
          className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-950 font-medium text-xs hover:opacity-90 transition-all active:scale-95"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Try Again
        </button>
      </div>
    )
  }

  const status = archive?.archive_status

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Header Controls */}
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-slate-200/60 dark:border-slate-800/60">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to library</span>
        </button>

        <div className="flex items-center gap-3">
          {archive && !isEditing && (
            <>
              <button
                onClick={handleStartEdit}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-100 hover:bg-slate-200/80 dark:bg-slate-800 dark:hover:bg-slate-700/80 text-slate-700 dark:text-slate-200 text-xs font-medium transition-all active:scale-95"
              >
                <Edit3 className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" />
                <span>Edit copy</span>
              </button>
              <a
                href={archive.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-slate-200 dark:border-slate-800 text-slate-700 hover:text-slate-950 dark:text-slate-350 dark:hover:text-slate-200 text-xs font-medium transition-colors"
              >
                <span>Open original</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </>
          )}

          {isEditing && (
            <div className="flex items-center gap-2">
              <button
                onClick={handleCancelEdit}
                disabled={isSaving}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full border border-slate-200 dark:border-slate-800 text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 text-xs font-medium transition-colors disabled:opacity-50"
              >
                <X className="w-3.5 h-3.5" />
                <span>Cancel</span>
              </button>
              <button
                onClick={handleSaveArchive}
                disabled={isSaving}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-slate-950 text-white dark:bg-slate-100 dark:text-slate-950 text-xs font-medium hover:opacity-90 transition-all active:scale-95 disabled:opacity-50"
              >
                {isSaving ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Saving...</span>
                  </>
                ) : (
                  <>
                    <Check className="w-3.5 h-3.5" />
                    <span>Save changes</span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Success Notification */}
      {saveSuccess && (
        <div className="mb-6 px-4 py-3 rounded-2xl bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/40 text-emerald-800 dark:text-emerald-300 text-xs font-medium flex items-center gap-2">
          <Check className="w-4 h-4 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
          <span>Offline article copy updated and saved successfully.</span>
        </div>
      )}

      {/* Save Error Notification */}
      {saveError && (
        <div className="mb-6 px-4 py-3 rounded-2xl bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/40 text-rose-800 dark:text-rose-300 text-xs font-medium flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 flex-shrink-0" />
          <span>{saveError}</span>
        </div>
      )}

      {archive && (
        <>
          {/* Article Info Header */}
          <div className="mb-8">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              {archive.domain || 'Local Copy'}
            </span>
            <h1 className="font-display text-3xl sm:text-4xl font-normal leading-tight text-slate-950 dark:text-slate-50 mt-2 mb-4">
              {archive.title}
            </h1>
            
            <div className="flex flex-wrap gap-4 text-xs text-slate-400 dark:text-slate-500">
              {!isEditing && archive.archive_word_count !== null && archive.archive_word_count !== undefined && (
                <span className="flex items-center gap-1.5">
                  <BookOpen className="w-3.5 h-3.5" />
                  {archive.archive_word_count.toLocaleString()} words
                </span>
              )}
              {!isEditing && archive.archive_word_count && (
                <span className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" />
                  {readingTime(archive.archive_word_count)}
                </span>
              )}
              {isEditing && (
                <span className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300 font-medium">
                  <BookOpen className="w-3.5 h-3.5" />
                  {liveWordCount.toLocaleString()} words ({liveCharCount.toLocaleString()} chars)
                </span>
              )}
              {archive.archived_at && (
                <span>Archived on {formatDateTime(archive.archived_at)}</span>
              )}
            </div>
          </div>

          {/* Edit Mode View */}
          {isEditing ? (
            <div className="space-y-4">
              {/* Tab Selector & Format Controls */}
              <div className="flex flex-wrap items-center justify-between gap-3 p-2 bg-slate-100/70 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-800/60 rounded-2xl">
                <div className="flex items-center gap-1 bg-white/80 dark:bg-slate-800/80 p-1 rounded-xl shadow-xs border border-slate-200/40 dark:border-slate-700/40">
                  <button
                    type="button"
                    onClick={() => setEditTab('write')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      editTab === 'write'
                        ? 'bg-slate-950 text-white dark:bg-slate-100 dark:text-slate-950 shadow-xs'
                        : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                    }`}
                  >
                    <FileText className="w-3.5 h-3.5" />
                    <span>Write</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditTab('preview')}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      editTab === 'preview'
                        ? 'bg-slate-950 text-white dark:bg-slate-100 dark:text-slate-950 shadow-xs'
                        : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                    }`}
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>Preview</span>
                  </button>
                </div>

                <div className="flex items-center gap-2 text-xs">
                  <span className="text-slate-500 dark:text-slate-400">Format:</span>
                  <select
                    value={editFormat}
                    onChange={(e) => setEditFormat(e.target.value as 'markdown' | 'text')}
                    className="px-2.5 py-1 rounded-lg bg-white/90 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 text-xs outline-none focus:ring-1 focus:ring-slate-400"
                  >
                    <option value="markdown">Markdown</option>
                    <option value="text">Plain Text</option>
                  </select>
                </div>
              </div>

              {/* Formatting Toolbar (Only in Write mode and Markdown format) */}
              {editTab === 'write' && editFormat === 'markdown' && (
                <div className="flex flex-wrap items-center gap-1 p-1.5 bg-white/60 dark:bg-slate-900/40 border border-slate-200/50 dark:border-slate-800/50 rounded-xl text-slate-600 dark:text-slate-400">
                  <button
                    type="button"
                    onClick={() => insertMarkdown('**', '**')}
                    title="Bold (**text**)"
                    className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
                  >
                    <Bold className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => insertMarkdown('*', '*')}
                    title="Italic (*text*)"
                    className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
                  >
                    <Italic className="w-3.5 h-3.5" />
                  </button>
                  <div className="w-px h-4 bg-slate-200 dark:bg-slate-800 mx-1" />
                  <button
                    type="button"
                    onClick={() => insertMarkdown('## ', '')}
                    title="Heading 2 (## Heading)"
                    className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
                  >
                    <Heading2 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => insertMarkdown('### ', '')}
                    title="Heading 3 (### Heading)"
                    className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
                  >
                    <Heading3 className="w-3.5 h-3.5" />
                  </button>
                  <div className="w-px h-4 bg-slate-200 dark:bg-slate-800 mx-1" />
                  <button
                    type="button"
                    onClick={() => insertMarkdown('- ', '')}
                    title="Bullet List (- item)"
                    className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
                  >
                    <List className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => insertMarkdown('1. ', '')}
                    title="Numbered List (1. item)"
                    className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
                  >
                    <ListOrdered className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => insertMarkdown('> ', '')}
                    title="Quote (> quote)"
                    className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
                  >
                    <Quote className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => insertMarkdown('```\n', '\n```')}
                    title="Code Block (```)"
                    className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
                  >
                    <Code className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => insertMarkdown('[', '](url)')}
                    title="Link ([title](url))"
                    className="p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100 transition-colors"
                  >
                    <LinkIcon className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {/* Editor Write View */}
              {editTab === 'write' ? (
                <div>
                  <textarea
                    ref={textareaRef}
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    placeholder="Paste your formatted article copy, clean markdown summary, or edited text here..."
                    className="w-full min-h-[520px] p-5 font-mono text-sm leading-relaxed rounded-2xl bg-white/90 dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-slate-100 placeholder-slate-400 outline-none transition focus:ring-2 focus:ring-slate-300 dark:focus:ring-slate-700/60 resize-y"
                  />
                  <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-2 px-1">
                    Tip: You can paste full markdown summaries, clean text, or edit existing formatting. Hit Save changes above to update this offline copy and the search index.
                  </p>
                </div>
              ) : (
                /* Editor Preview View */
                <div className="min-h-[520px] p-6 rounded-2xl bg-white/80 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
                  {editContent.trim() ? (
                    <article className="prose prose-slate dark:prose-invert max-w-none select-text">
                      {editFormat === 'markdown' ? (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{editContent}</ReactMarkdown>
                      ) : (
                        <div className="whitespace-pre-wrap font-sans text-base leading-relaxed">
                          {editContent}
                        </div>
                      )}
                    </article>
                  ) : (
                    <div className="text-center py-20 text-slate-400 dark:text-slate-500 text-sm">
                      Nothing to preview yet. Switch to the Write tab to paste or type article content.
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            /* Normal Read Mode */
            <>
              {/* Pending / Processing State */}
              {(status === 'pending' || status === 'processing') && (
                <div className="flex flex-col items-center justify-center py-16 px-6 bg-slate-50 dark:bg-slate-900/40 border border-slate-200/50 dark:border-slate-800/50 rounded-card text-center">
                  <Loader2 className="w-8 h-8 animate-spin text-slate-500 mb-4" />
                  <h3 className="font-display text-lg text-slate-900 dark:text-white mb-2">Saving local copy...</h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mb-6">
                    We are currently downloading and formatting a clean, readable copy of this article. This page will update automatically.
                  </p>
                  <button
                    onClick={handleStartEdit}
                    className="flex items-center gap-2 px-4 py-2 rounded-full border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-medium text-xs hover:bg-slate-100 dark:hover:bg-slate-800 transition-all"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                    <span>Paste copy manually instead</span>
                  </button>
                </div>
              )}

              {/* Failed / Unavailable State */}
              {(status === 'failed' || status === 'unavailable') && (
                <div className="flex flex-col items-center justify-center py-12 px-6 bg-rose-50/50 dark:bg-rose-950/10 border border-rose-200/60 dark:border-rose-900/30 rounded-card text-center">
                  <AlertCircle className="w-8 h-8 text-rose-500 dark:text-rose-400 mb-4" />
                  <h3 className="font-display text-lg text-slate-900 dark:text-white mb-2">Saved Copy Unavailable</h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mb-6">
                    {archive.archive_error || "A local copy could not be saved because the website blocked downloading or is password-protected."}
                  </p>
                  <div className="flex flex-wrap items-center justify-center gap-3">
                    <button
                      onClick={handleRetry}
                      disabled={isRetrying}
                      className="flex items-center gap-2 px-5 py-2.5 rounded-full border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200 font-medium text-xs hover:bg-slate-100 dark:hover:bg-slate-800 transition-all active:scale-95 disabled:opacity-50"
                    >
                      {isRetrying ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          Retry in progress...
                        </>
                      ) : (
                        <>
                          <RefreshCw className="w-3.5 h-3.5" />
                          Retry downloading
                        </>
                      )}
                    </button>
                    <button
                      onClick={handleStartEdit}
                      className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-slate-950 text-white dark:bg-slate-100 dark:text-slate-950 font-medium text-xs hover:opacity-90 transition-all active:scale-95"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                      <span>Paste article / summary</span>
                    </button>
                  </div>
                </div>
              )}

              {/* Completed State - Clean Content Render */}
              {status === 'completed' && archive.archive_content && (
                <article className="prose prose-slate dark:prose-invert max-w-none select-text">
                  {archive.archive_format === 'markdown' ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{archive.archive_content}</ReactMarkdown>
                  ) : (
                    <div className="whitespace-pre-wrap font-sans text-base sm:text-[17px] leading-relaxed">
                      {archive.archive_content}
                    </div>
                  )}
                </article>
              )}

              {/* Completed State - Empty Content */}
              {status === 'completed' && !archive.archive_content && (
                <div className="flex flex-col items-center justify-center py-16 px-6 bg-slate-50 dark:bg-slate-900/40 border border-slate-200/50 dark:border-slate-800/50 rounded-card text-center">
                  <BookOpen className="w-8 h-8 text-slate-400 mb-3" />
                  <h3 className="font-display text-lg text-slate-900 dark:text-white mb-2">No article content saved</h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mb-6">
                    This bookmark doesn't have an offline copy yet. You can paste the article body or a summary with formatted markdown.
                  </p>
                  <button
                    onClick={handleStartEdit}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-slate-950 text-white dark:bg-slate-100 dark:text-slate-950 font-medium text-xs hover:opacity-90 transition-all active:scale-95"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                    <span>Add article copy</span>
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
