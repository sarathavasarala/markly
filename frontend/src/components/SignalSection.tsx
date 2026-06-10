import { useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Sparkles, Settings, Loader2, Calendar, ChevronRight, Info, X, RefreshCw, Undo2, Trash2, Check, Circle } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { signalApi, SignalBrief } from '../lib/api'

interface SignalSectionProps {
  onGenerateSuccess?: () => void
}

interface PipelineStep {
  id: string
  label: string
  status: 'pending' | 'active' | 'done'
  detail?: string
  titles?: string[]
}

const getInitialSteps = (webSearchEnabled: boolean): PipelineStep[] => {
  const steps: PipelineStep[] = [
    { id: 'scanning', label: 'Scanning sources', status: 'pending' },
    { id: 'filtering', label: 'Applying taste profile', status: 'pending' },
    { id: 'extracting', label: 'Extracting full text', status: 'pending' },
  ]
  if (webSearchEnabled) {
    steps.push({ id: 'researching', label: 'Researching background context', status: 'pending' })
  }
  steps.push({ id: 'synthesizing', label: 'Writing your daily brief', status: 'pending' })
  return steps
}

export default function SignalSection({ onGenerateSuccess }: SignalSectionProps) {
  const [briefs, setBriefs] = useState<SignalBrief[]>([])
  const [selectedBriefId, setSelectedBriefId] = useState<string | null>(null)
  const [tasteProfileInput, setTasteProfileInput] = useState<string>('')
  
  const [signalCandidateLimit, setSignalCandidateLimit] = useState<number | null>(null)
  const [signalFilterPrompt, setSignalFilterPrompt] = useState<string>('')
  const [signalSynthesisPrompt, setSignalSynthesisPrompt] = useState<string>('')
  const [defaultFilterPrompt, setDefaultFilterPrompt] = useState<string>('')
  const [defaultSynthesisPrompt, setDefaultSynthesisPrompt] = useState<string>('')
  const [signalWebSearchEnabled, setSignalWebSearchEnabled] = useState<boolean>(true)
  
  const [activeSettingsTab, setActiveSettingsTab] = useState<'instructions' | 'prompts' | 'settings'>('instructions')

  const [isLoading, setIsLoading] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>(getInitialSteps(true))
  const [isTasteProfileOpen, setIsTasteProfileOpen] = useState(false)
  const [isHistoryExpanded, setIsHistoryExpanded] = useState(false)
  
  const [error, setError] = useState<string | null>(null)
  const [infoMessage, setInfoMessage] = useState<string | null>(null)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

  const [candidateWords, setCandidateWords] = useState<number | null>(null)
  const [extractedWords, setExtractedWords] = useState<number | null>(null)
  const [researchWords, setResearchWords] = useState<number | null>(null)
  const [synthesisWords, setSynthesisWords] = useState<number | null>(null)
  const [synthesisOutputWords, setSynthesisOutputWords] = useState<number | null>(null)

  const loadSignalData = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [briefsRes, profileRes] = await Promise.all([
        signalApi.listBriefs(),
        signalApi.getTasteProfile()
      ])
      setBriefs(briefsRes.data.briefs)
      setTasteProfileInput(profileRes.data.taste_profile)
      setSignalCandidateLimit(profileRes.data.signal_candidate_limit)
      
      const defaultFilter = profileRes.data.default_filter_prompt || ''
      const defaultSynth = profileRes.data.default_synthesis_prompt || ''
      setDefaultFilterPrompt(defaultFilter)
      setDefaultSynthesisPrompt(defaultSynth)
      
      setSignalFilterPrompt(profileRes.data.signal_filter_prompt !== null ? profileRes.data.signal_filter_prompt : defaultFilter)
      setSignalSynthesisPrompt(profileRes.data.signal_synthesis_prompt !== null ? profileRes.data.signal_synthesis_prompt : defaultSynth)
      setSignalWebSearchEnabled(profileRes.data.signal_web_search_enabled !== undefined ? !!profileRes.data.signal_web_search_enabled : true)

      if (briefsRes.data.briefs.length > 0) {
        setSelectedBriefId(briefsRes.data.briefs[0].id)
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load Signal data')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadSignalData()
  }, [loadSignalData])

  const updateStep = (stepId: string, updates: Partial<PipelineStep>) => {
    setPipelineSteps(prev => prev.map(s => s.id === stepId ? { ...s, ...updates } : s))
  }

  const markStepDone = (stepId: string, detail?: string, titles?: string[]) => {
    setPipelineSteps(prev => prev.map(s => {
      if (s.id === stepId) {
        return {
          ...s,
          status: 'done' as const,
          // Preserve existing detail/titles if new ones aren't provided
          detail: detail ?? s.detail,
          titles: titles ?? s.titles,
        }
      }
      return s
    }))
  }

  const markStepActive = (stepId: string, detail?: string) => {
    setPipelineSteps(prev => prev.map(s => {
      if (s.id === stepId) return { ...s, status: 'active' as const, detail }
      return s
    }))
  }

  const handleGenerate = async () => {
    setIsGenerating(true)
    setError(null)
    setInfoMessage(null)
    setCandidateWords(null)
    setExtractedWords(null)
    setResearchWords(null)
    setSynthesisWords(null)
    setSynthesisOutputWords(null)
    setPipelineSteps(getInitialSteps(signalWebSearchEnabled).map(s => ({ ...s, status: 'pending' as const, detail: undefined, titles: undefined })))

    try {
      const response = await signalApi.generateBriefStream()
      if (!response.ok) {
        const text = await response.text()
        try {
          const err = JSON.parse(text)
          setError(err.error || 'Failed to generate brief.')
        } catch {
          setError('Failed to generate brief. Please ensure you have added active RSS feeds.')
        }
        setIsGenerating(false)
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        setError('Streaming not supported in this browser.')
        setIsGenerating(false)
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))

            switch (event.stage) {
              case 'scanning':
                markStepActive('scanning', event.message)
                if (event.candidate_word_count !== undefined) setCandidateWords(event.candidate_word_count)
                // Immediately mark done since scanning is instant
                setTimeout(() => markStepDone('scanning', event.message), 300)
                break
              case 'filtering':
                markStepDone('scanning')
                markStepActive('filtering', event.message)
                break
              case 'filtered':
                markStepDone('filtering', event.message, event.titles)
                if (event.candidate_word_count !== undefined) setCandidateWords(event.candidate_word_count)
                break
              case 'extracting':
                markStepActive('extracting', event.message)
                updateStep('extracting', { detail: event.message })
                break
              case 'researching':
                markStepDone('extracting')
                markStepActive('researching', event.message)
                if (event.extracted_word_count !== undefined) setExtractedWords(event.extracted_word_count)
                break
              case 'researched':
                markStepDone('researching', event.message, event.titles)
                if (event.research_word_count !== undefined) setResearchWords(event.research_word_count)
                if (event.extracted_word_count !== undefined) setExtractedWords(event.extracted_word_count)
                break
              case 'synthesizing':
                markStepDone('researching')
                markStepDone('extracting')
                markStepActive('synthesizing', event.message)
                if (event.extracted_word_count !== undefined) setExtractedWords(event.extracted_word_count)
                if (event.research_word_count !== undefined) setResearchWords(event.research_word_count)
                if (event.synthesis_word_count !== undefined) setSynthesisWords(event.synthesis_word_count)
                break
              case 'complete': {
                markStepDone('synthesizing')
                const newBrief = event.brief as SignalBrief
                setBriefs(prev => [newBrief, ...prev])
                setSelectedBriefId(newBrief.id)
                if (event.synthesis_output_word_count !== undefined) setSynthesisOutputWords(event.synthesis_output_word_count)
                if (onGenerateSuccess) onGenerateSuccess()
                break
              }
              case 'error':
                setInfoMessage(event.message)
                break
            }
          } catch {
            // Skip unparseable lines
          }
        }
      }
    } catch (err: any) {
      setError(err.message || 'Failed to generate brief. Please ensure you have added active RSS feeds.')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleSaveProfile = async () => {
    setSaveStatus('saving')
    try {
      const res = await signalApi.updateTasteProfile({
        taste_profile: tasteProfileInput,
        signal_candidate_limit: signalCandidateLimit,
        signal_filter_prompt: signalFilterPrompt,
        signal_synthesis_prompt: signalSynthesisPrompt,
        signal_web_search_enabled: signalWebSearchEnabled,
      })
      setTasteProfileInput(res.data.taste_profile)
      setSignalCandidateLimit(res.data.signal_candidate_limit)
      setSignalFilterPrompt(res.data.signal_filter_prompt !== null ? res.data.signal_filter_prompt : defaultFilterPrompt)
      setSignalSynthesisPrompt(res.data.signal_synthesis_prompt !== null ? res.data.signal_synthesis_prompt : defaultSynthesisPrompt)
      setSignalWebSearchEnabled(res.data.signal_web_search_enabled !== undefined ? !!res.data.signal_web_search_enabled : true)
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus('idle'), 2000)
    } catch (err) {
      setSaveStatus('error')
      setTimeout(() => setSaveStatus('idle'), 3000)
    }
  }

  const handleResetProfile = async () => {
    if (window.confirm('Reset Taste Profile and prompts to the recommended default instructions?')) {
      setSaveStatus('saving')
      try {
        const res = await signalApi.updateTasteProfile({
          taste_profile: '',
          signal_candidate_limit: null,
          signal_filter_prompt: null,
          signal_synthesis_prompt: null,
          signal_web_search_enabled: true,
        })
        setTasteProfileInput(res.data.taste_profile)
        setSignalCandidateLimit(res.data.signal_candidate_limit)
        setSignalFilterPrompt(defaultFilterPrompt)
        setSignalSynthesisPrompt(defaultSynthesisPrompt)
        setSignalWebSearchEnabled(true)
        setSaveStatus('saved')
        setTimeout(() => setSaveStatus('idle'), 2000)
      } catch (err) {
        setSaveStatus('error')
        setTimeout(() => setSaveStatus('idle'), 3000)
      }
    }
  }

  const formatDate = (value: string | null) => {
    if (!value) return null
    try {
      return new Intl.DateTimeFormat(undefined, { 
        weekday: 'long', 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
      }).format(new Date(value))
    } catch {
      return null
    }
  }

  const formatShortDate = (value: string | null) => {
    if (!value) return null
    try {
      return new Intl.DateTimeFormat(undefined, { 
        month: 'short', 
        day: 'numeric',
        year: 'numeric'
      }).format(new Date(value))
    } catch {
      return null
    }
  }

  const selectedBrief = briefs.find(b => b.id === selectedBriefId)

  return (
    <div className="space-y-6">
      {/* Action Bar */}
      <div className="flex flex-col gap-3 border-b border-slate-200/60 pb-3 dark:border-slate-800/60 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-sm font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
          Today's Signal
        </h2>
        
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setIsTasteProfileOpen(true)}
            className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700 dark:hover:bg-slate-700"
            title="Edit Taste Profile Settings"
          >
            <Settings className="h-4 w-4" />
            Taste Profile
          </button>
          
          <button
            onClick={handleGenerate}
            disabled={isGenerating}
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
          >
            {isGenerating ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {briefs.length > 0 ? 'Generate today\'s brief' : 'Generate brief'}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:bg-rose-900/20 dark:text-rose-300">
          {error}
        </div>
      )}

      {infoMessage && (
        <div className="flex items-start gap-3 rounded-2xl bg-amber-50 px-4 py-4 text-sm text-amber-800 dark:bg-amber-950/20 dark:text-amber-300 ring-1 ring-amber-200/50 dark:ring-amber-900/20">
          <Info className="h-5 w-5 flex-shrink-0 text-amber-600 dark:text-amber-500 mt-0.5" />
          <div>
            <p className="font-semibold text-slate-900 dark:text-slate-100">Brief Generation Status</p>
            <p className="mt-1">{infoMessage}</p>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)] w-full min-w-0">
          <div className="space-y-2 w-full min-w-0">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded-2xl bg-slate-200/70 dark:bg-slate-800/70" />
            ))}
          </div>
          <div className="h-96 animate-pulse rounded-3xl bg-slate-200/70 dark:bg-slate-800/70" />
        </div>
      ) : briefs.length === 0 && !isGenerating ? (
        /* Empty State */
        <div className="rounded-card border border-dashed border-slate-300 bg-white/40 px-6 py-16 text-center dark:border-slate-700 dark:bg-slate-900/40">
          <div className="mx-auto max-w-lg space-y-4">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-800">
              <Sparkles className="h-6 w-6 text-slate-600 dark:text-slate-400" />
            </div>
            <h2 className="font-display text-xl font-normal text-slate-900 dark:text-slate-100">
              Create your first Daily Brief
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Instead of reading individual feed items, Signal filters recent RSS stories using your Taste Profile and synthesizes them into a unified chief-of-staff memo.
            </p>
            <div className="pt-4 flex justify-center gap-3">
              <button
                onClick={() => setIsTasteProfileOpen(true)}
                className="rounded-full bg-white px-4 py-2.5 text-sm font-medium text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700 dark:hover:bg-slate-700"
              >
                Configure Taste Profile
              </button>
              <button
                onClick={handleGenerate}
                className="rounded-full bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
              >
                Generate Brief
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* Signal Brief Viewport */
        <div className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)] w-full min-w-0">
          {/* Left Column: Brief History Sidebar */}
          <aside className="space-y-3 w-full min-w-0">
            <button
              type="button"
              onClick={() => setIsHistoryExpanded(!isHistoryExpanded)}
              className="flex w-full items-center justify-between rounded-2xl border border-slate-200/70 bg-white/70 px-4 py-3 text-left text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-slate-800/80 dark:bg-slate-900/50 dark:text-slate-300 xl:hidden"
            >
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-slate-500 dark:text-slate-400" />
                <span className="text-slate-500 dark:text-slate-400 font-semibold">Brief History</span>
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-400 font-medium">
                  {selectedBrief ? formatShortDate(selectedBrief.created_at) : 'No briefs'}
                </span>
              </div>
              <span className="text-xs text-slate-400 font-semibold">
                {isHistoryExpanded ? 'Hide ▲' : 'Show ▼'}
              </span>
            </button>

            <div className="hidden xl:flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
              <Calendar className="h-3.5 w-3.5" />
              Brief History
            </div>

            <div className={`${isHistoryExpanded ? 'block animate-in fade-in slide-in-from-top-2 duration-200' : 'hidden'} xl:block space-y-1 w-full min-w-0`}>
              {briefs.map((brief) => {
                const isSelected = brief.id === selectedBriefId
                return (
                  <div key={brief.id} className="group flex items-center gap-1 w-full min-w-0">
                    <button
                      onClick={() => {
                        setSelectedBriefId(brief.id)
                        setInfoMessage(null)
                        setIsHistoryExpanded(false)
                      }}
                      className={`min-w-0 flex-1 flex items-center justify-between rounded-2xl px-4 py-3 text-left transition ${
                        isSelected
                          ? 'bg-white text-slate-950 ring-1 ring-slate-200 shadow-sm dark:bg-slate-800 dark:text-slate-50 dark:ring-slate-700'
                          : 'text-slate-600 hover:bg-white/60 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-100'
                      }`}
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate" title={brief.title || formatShortDate(brief.created_at) || undefined}>
                          {brief.title || formatShortDate(brief.created_at)}
                        </p>
                        <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500 truncate">
                          {brief.title 
                            ? formatShortDate(brief.created_at) 
                            : (brief.article_count ? `${brief.article_count} articles analyzed` : 'Synthesized memo')
                          }
                        </p>
                      </div>
                      <ChevronRight className={`h-4 w-4 flex-shrink-0 ml-2 ${isSelected ? 'text-slate-600 dark:text-slate-400' : 'text-slate-300'}`} />
                    </button>
                    <button
                      onClick={async (e) => {
                        e.stopPropagation()
                        if (!window.confirm('Delete this brief? You can regenerate a new one.')) return
                        try {
                          await signalApi.deleteBrief(brief.id)
                          setBriefs(prev => prev.filter(b => b.id !== brief.id))
                          if (selectedBriefId === brief.id) {
                            const remaining = briefs.filter(b => b.id !== brief.id)
                            setSelectedBriefId(remaining.length > 0 ? remaining[0].id : null)
                          }
                        } catch {
                          setError('Failed to delete brief')
                        }
                      }}
                      className="rounded-lg p-1.5 text-slate-300 opacity-0 transition hover:bg-rose-50 hover:text-rose-600 group-hover:opacity-100 dark:hover:bg-rose-900/20 dark:hover:text-rose-300"
                      title="Delete brief"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )
              })}
            </div>
          </aside>

          {/* Right Column: Brief Viewer Area */}
          <section className="space-y-4 w-full min-w-0">
            {isGenerating ? (
              <div className="rounded-card border border-slate-200/70 bg-white/70 p-4 sm:p-8 dark:border-slate-800/80 dark:bg-slate-900/50 min-h-[400px] flex flex-col justify-center">
                <h3 className="font-display text-lg font-medium text-slate-900 dark:text-slate-100 mb-6">
                  Preparing your daily brief
                </h3>
                <div className="space-y-0">
                  {pipelineSteps.map((step, idx) => (
                    <div key={step.id} className="flex items-stretch gap-3">
                      {/* Step connector line + icon */}
                      <div className="flex flex-col items-center flex-shrink-0">
                        <div className="flex h-6 w-6 items-center justify-center rounded-full flex-shrink-0">
                          {step.status === 'done' ? (
                            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-900 dark:bg-slate-100">
                              <Check className="h-3 w-3 text-white dark:text-slate-900" />
                            </div>
                          ) : step.status === 'active' ? (
                            <Loader2 className="h-5 w-5 animate-spin text-slate-700 dark:text-slate-300" />
                          ) : (
                            <Circle className="h-4 w-4 text-slate-300 dark:text-slate-600" />
                          )}
                        </div>
                        {idx < pipelineSteps.length - 1 && (
                          <div className={`w-px flex-1 mt-1 ${
                            step.status === 'done' ? 'bg-slate-400 dark:bg-slate-500' : 'bg-slate-200 dark:bg-slate-700'
                          }`} />
                        )}
                      </div>
                      {/* Step text */}
                      <div className="pb-4 min-w-0 flex-1">
                        <p className={`text-sm font-medium ${
                          step.status === 'done'
                            ? 'text-slate-900 dark:text-slate-100'
                            : step.status === 'active'
                            ? 'text-slate-800 dark:text-slate-200'
                            : 'text-slate-400 dark:text-slate-500'
                        }`}>
                          {step.detail || step.label}
                        </p>
                        {/* Word Count / Token Count Telemetry */}
                        {step.status === 'done' && (
                          <div className="mt-1">
                            {step.id === 'filtering' && candidateWords !== null && (
                              <p className="text-xs text-slate-400 dark:text-slate-500 font-sans">
                                Filter input: ~{candidateWords.toLocaleString()} words (estimated tokens ~{Math.round(candidateWords * 1.35).toLocaleString()})
                              </p>
                            )}
                            {step.id === 'extracting' && extractedWords !== null && (
                              <p className="text-xs text-slate-400 dark:text-slate-500 font-sans">
                                Extracted text: ~{extractedWords.toLocaleString()} words (estimated tokens ~{Math.round(extractedWords * 1.35).toLocaleString()})
                              </p>
                            )}
                            {step.id === 'researching' && researchWords !== null && (
                              <p className="text-xs text-slate-400 dark:text-slate-500 font-sans">
                                Research context: ~{researchWords.toLocaleString()} words (estimated tokens ~{Math.round(researchWords * 1.35).toLocaleString()})
                              </p>
                            )}
                            {step.id === 'synthesizing' && synthesisWords !== null && (
                              <p className="text-xs text-slate-400 dark:text-slate-500 font-sans">
                                Synthesis input: ~{synthesisWords.toLocaleString()} words (estimated tokens ~{Math.round(synthesisWords * 1.35).toLocaleString()})
                              </p>
                            )}
                          </div>
                        )}
                        {/* Show step details if present (e.g. titles or queries) */}
                        {((step.id === 'filtering' || step.id === 'researching') && step.status === 'done' && step.titles && step.titles.length > 0) && (
                          <div className="mt-2 space-y-1">
                            {step.titles.map((title, i) => (
                              <p key={i} className="text-xs text-slate-400 dark:text-slate-500 truncate pl-2 border-l-2 border-slate-200 dark:border-slate-700">
                                {step.id === 'researching' ? `🔍 ${title}` : title}
                              </p>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Token Telemetry Collapsible Section */}
                {(candidateWords || extractedWords || researchWords || synthesisWords) && (() => {
                  const totalInputWords = (candidateWords || 0) + (signalWebSearchEnabled && extractedWords ? extractedWords : 0) + (synthesisWords || 0)
                  const totalOutputWords = (signalWebSearchEnabled && researchWords ? researchWords : 0) + (synthesisOutputWords || 0)
                  const totalInputTokens = Math.round(totalInputWords * 1.35)
                  const totalOutputTokens = Math.round(totalOutputWords * 1.35)

                  return (
                    <details className="group mt-6 border-t border-slate-200/60 pt-4 dark:border-slate-800/60">
                      <summary className="flex items-center justify-between cursor-pointer list-none text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider hover:text-slate-700 dark:hover:text-slate-300">
                        <span className="flex items-center gap-1.5">
                          <Sparkles className="h-3.5 w-3.5 text-slate-450 dark:text-slate-500 transition-transform group-open:rotate-45" />
                          Token Telemetry
                          <span className="text-[10px] lowercase text-slate-400 font-normal px-1 py-0.5 rounded bg-slate-100 dark:bg-slate-900 border border-slate-200/50 dark:border-slate-800/50">
                            click to view breakdown
                          </span>
                        </span>
                        <span className="normal-case text-slate-500 dark:text-slate-400 font-normal font-sans">
                          {synthesisOutputWords !== null ? (
                            `est. tokens: ~${totalInputTokens.toLocaleString()} input / ~${totalOutputTokens.toLocaleString()} output`
                          ) : (
                            `est. tokens: ~${totalInputTokens.toLocaleString()} input / ~${totalOutputTokens.toLocaleString()} output (so far)`
                          )}
                        </span>
                      </summary>
                      <div className="mt-3 space-y-2.5 text-xs text-slate-655 dark:text-slate-400 pl-5 divide-y divide-slate-100/50 dark:divide-slate-900/50">
                        {/* Stage 1: Filtering */}
                        {candidateWords !== null && (
                          <div className="space-y-1.5 py-1.5">
                            <span className="font-semibold text-slate-750 dark:text-slate-300 block">1. Taste Profile Filtering Stage</span>
                            <div className="flex items-center justify-between pl-3 text-slate-500 dark:text-slate-450">
                              <span>Input (Candidate summaries/metadata)</span>
                              <span>~{candidateWords.toLocaleString()} words (est. tokens ~{Math.round(candidateWords * 1.35).toLocaleString()})</span>
                            </div>
                            <div className="flex items-center justify-between pl-3 text-slate-500 dark:text-slate-455">
                              <span>Output (Selected IDs)</span>
                              <span>negligible (approx. &lt;100 tokens)</span>
                            </div>
                          </div>
                        )}

                        {/* Stage 2: Background Research (if web search is enabled) */}
                        {signalWebSearchEnabled && extractedWords !== null && (
                          <div className="space-y-1.5 py-2">
                            <span className="font-semibold text-slate-750 dark:text-slate-300 block">2. Background Research Stage (Web Search)</span>
                            <div className="flex items-center justify-between pl-3 text-slate-500 dark:text-slate-450">
                              <span>Input (Extracted high-signal full body)</span>
                              <span>~{extractedWords.toLocaleString()} words (est. tokens ~{Math.round(extractedWords * 1.35).toLocaleString()})</span>
                            </div>
                            {researchWords !== null && researchWords > 0 && (
                              <div className="flex items-center justify-between pl-3 text-slate-550 dark:text-slate-400">
                                <span className="font-medium text-slate-600 dark:text-slate-400">Output (Background Research Brief)</span>
                                <span className="font-medium">~{researchWords.toLocaleString()} words (est. tokens ~{Math.round(researchWords * 1.35).toLocaleString()})</span>
                              </div>
                            )}
                          </div>
                        )}

                        {/* Stage 3: Synthesis */}
                        {synthesisWords !== null && (
                          <div className="space-y-1.5 py-2">
                            <span className="font-semibold text-slate-750 dark:text-slate-300 block">3. Writing Stage (Brief Synthesis)</span>
                            <div className="flex items-center justify-between pl-3 text-slate-500 dark:text-slate-450">
                              <span>Input (Extracted text + research brief context)</span>
                              <span>~{synthesisWords.toLocaleString()} words (est. tokens ~{Math.round(synthesisWords * 1.35).toLocaleString()})</span>
                            </div>
                            {synthesisOutputWords !== null && (
                              <div className="flex items-center justify-between pl-3 text-slate-550 dark:text-slate-400">
                                <span className="font-medium text-slate-600 dark:text-slate-400">Output (Generated Daily Brief Content)</span>
                                <span className="font-medium">~{synthesisOutputWords.toLocaleString()} words (est. tokens ~{Math.round(synthesisOutputWords * 1.35).toLocaleString()})</span>
                              </div>
                            )}
                          </div>
                        )}

                        {/* Totals Summary */}
                        {synthesisOutputWords !== null && (
                          <div className="space-y-1.5 py-2.5 font-sans border-t border-slate-200 dark:border-slate-800">
                            <span className="font-bold text-slate-800 dark:text-slate-200 block">Estimated Footprint Summary Totals</span>
                            <div className="flex items-center justify-between pl-3">
                              <span className="font-semibold text-slate-700 dark:text-slate-350">Total Prompt Input size</span>
                              <span className="font-bold text-slate-900 dark:text-slate-100">
                                ~{totalInputWords.toLocaleString()} words (estimated tokens ~{totalInputTokens.toLocaleString()})
                              </span>
                            </div>
                            <div className="flex items-center justify-between pl-3">
                              <span className="font-semibold text-slate-700 dark:text-slate-350">Total Generated Output size</span>
                              <span className="font-bold text-slate-900 dark:text-slate-100">
                                ~{totalOutputWords.toLocaleString()} words (estimated tokens ~{totalOutputTokens.toLocaleString()})
                              </span>
                            </div>
                          </div>
                        )}
                      </div>
                    </details>
                  )
                })()}
              </div>
            ) : selectedBrief ? (
              /* Brief Display Card */
              <article className="rounded-card border border-slate-200/70 bg-white p-4 sm:p-6 shadow-sm dark:border-slate-800/80 dark:bg-slate-950">
                {/* Header info */}
                <div className="border-b border-slate-100 pb-4 mb-6 dark:border-slate-900">
                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1">
                    {selectedBrief.title ? formatDate(selectedBrief.created_at) : 'Daily Briefing Memo'}
                  </div>
                  <h2 className="font-display text-2xl font-normal text-slate-900 dark:text-slate-50">
                    {selectedBrief.title || formatDate(selectedBrief.created_at)}
                  </h2>
                </div>

                {/* Briefing intro note */}
                <div className="rounded-2xl bg-slate-50 px-4 py-3 mb-6 dark:bg-slate-900/40 ring-1 ring-slate-100 dark:ring-slate-800">
                  <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                    <span className="font-semibold text-slate-800 dark:text-slate-200">Your daily brief</span>
                    {selectedBrief.article_count
                      ? ` - based on analysis of ${selectedBrief.article_count} articles from your RSS feeds.`
                      : ' - synthesized from recent articles across your RSS feeds.'}
                    {' '}Below are the themes and developments that stood out today.
                  </p>
                </div>
                
                {/* Synthesized Brief Content */}
                <div className="prose prose-slate dark:prose-invert max-w-none text-slate-800 dark:text-slate-200 select-text leading-relaxed font-sans text-base">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      a: ({ href, children }) => (
                        <a
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-slate-700 dark:text-slate-300 underline decoration-slate-400/50 underline-offset-2 transition hover:text-slate-950 hover:decoration-slate-700 dark:hover:text-slate-100 dark:decoration-slate-500/50 dark:hover:decoration-slate-300"
                        >
                          {children}
                        </a>
                      )
                    }}
                  >
                    {selectedBrief.content}
                  </ReactMarkdown>
                </div>
              </article>
            ) : null}
          </section>
        </div>
      )}

      {/* Slide-over Taste Profile Drawer */}
      {isTasteProfileOpen && createPortal(
        <div className="fixed inset-0 z-[60] flex justify-end bg-slate-950/40 backdrop-blur-sm transition-opacity animate-in fade-in-0 duration-200">
          <div 
            className="fixed inset-0" 
            onClick={() => setIsTasteProfileOpen(false)} 
          />
          <aside className="relative z-10 flex h-full w-full max-w-xl flex-col bg-white shadow-2xl transition-transform dark:bg-slate-950 border-l border-slate-200 dark:border-slate-800 animate-in slide-in-from-right duration-300 p-6">
            
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-200/60 pb-4 dark:border-slate-800/60">
              <div>
                <h3 className="font-display text-lg font-semibold text-slate-900 dark:text-slate-50">
                  Signal Taste Profile
                </h3>
                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                  Standing instructions that guide daily report filtering and style.
                </p>
              </div>
              <button
                onClick={() => setIsTasteProfileOpen(false)}
                className="rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                title="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Tabs Selector */}
            <div className="flex border-b border-slate-200/60 dark:border-slate-800/60 mt-4">
              <button
                type="button"
                onClick={() => setActiveSettingsTab('instructions')}
                className={`flex-1 pb-3 text-sm font-medium border-b-2 transition ${
                  activeSettingsTab === 'instructions'
                    ? 'border-slate-900 text-slate-900 dark:border-slate-100 dark:text-slate-100'
                    : 'border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
                }`}
              >
                Instructions
              </button>
              <button
                type="button"
                onClick={() => setActiveSettingsTab('prompts')}
                className={`flex-1 pb-3 text-sm font-medium border-b-2 transition ${
                  activeSettingsTab === 'prompts'
                    ? 'border-slate-900 text-slate-900 dark:border-slate-100 dark:text-slate-100'
                    : 'border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
                }`}
              >
                Prompts
              </button>
              <button
                type="button"
                onClick={() => setActiveSettingsTab('settings')}
                className={`flex-1 pb-3 text-sm font-medium border-b-2 transition ${
                  activeSettingsTab === 'settings'
                    ? 'border-slate-900 text-slate-900 dark:border-slate-100 dark:text-slate-100'
                    : 'border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200'
                }`}
              >
                Settings
              </button>
            </div>

            {/* Profile editor form */}
            <div className="flex-1 overflow-y-auto py-6">
              {activeSettingsTab === 'instructions' && (
                <div className="space-y-4">
                  <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Preference Instructions
                  </label>
                  
                  <textarea
                    value={tasteProfileInput}
                    onChange={(e) => setTasteProfileInput(e.target.value)}
                    placeholder="Describe your taste, filtering guidelines, style, or specific domains of interest..."
                    className="w-full h-80 rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:focus:border-slate-500 dark:focus:ring-slate-900/40 resize-none"
                  />

                  <div className="rounded-xl bg-slate-50 p-4 dark:bg-slate-900/40 text-xs text-slate-500 dark:text-slate-400 space-y-2">
                    <div className="flex items-center gap-1.5 font-semibold text-slate-700 dark:text-slate-300">
                      <Info className="h-3.5 w-3.5 text-slate-500" />
                      Taste Profile Guidelines
                    </div>
                    <p>
                      Explain exactly what insights you prioritize, what styles you favor, and what low-value content (e.g. clickbait, raw metrics, hype announcements) should be aggressively discarded.
                    </p>
                  </div>
                </div>
              )}

              {activeSettingsTab === 'prompts' && (
                <div className="space-y-6">
                  {/* Step 1: Filtering Prompt */}
                  <div className="space-y-3">
                    <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Step 1: Filter Prompt Template
                    </label>
                    <textarea
                      value={signalFilterPrompt}
                      onChange={(e) => setSignalFilterPrompt(e.target.value)}
                      placeholder="Filter prompt template..."
                      className="w-full h-64 rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:focus:border-slate-500 dark:focus:ring-slate-900/40 font-mono resize-none"
                    />
                    <div className="rounded-xl bg-amber-50 p-4 dark:bg-amber-950/20 text-xs text-amber-800 dark:text-amber-300 ring-1 ring-amber-200/50 dark:ring-amber-900/20 space-y-1">
                      <span className="font-semibold">Required variables:</span>
                      <p>
                        Your prompt template must include the placeholders <code className="bg-amber-100 dark:bg-amber-900/40 px-1 py-0.5 rounded font-mono font-semibold">{"{taste_profile}"}</code> and <code className="bg-amber-100 dark:bg-amber-900/40 px-1 py-0.5 rounded font-mono font-semibold">{"{articles_list_str}"}</code> for dynamic insertion.
                      </p>
                    </div>
                  </div>

                  <hr className="border-slate-200/60 dark:border-slate-800/60" />

                  {/* Step 2: Synthesis Prompt */}
                  <div className="space-y-3">
                    <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Step 2: Synthesis Prompt Template
                    </label>
                    <textarea
                      value={signalSynthesisPrompt}
                      onChange={(e) => setSignalSynthesisPrompt(e.target.value)}
                      placeholder="Synthesis prompt template..."
                      className="w-full h-64 rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:focus:border-slate-500 dark:focus:ring-slate-900/40 font-mono resize-none"
                    />
                    <div className="rounded-xl bg-amber-50 p-4 dark:bg-amber-950/20 text-xs text-amber-800 dark:text-amber-300 ring-1 ring-amber-200/50 dark:ring-amber-900/20 space-y-1">
                      <span className="font-semibold">Required variables:</span>
                      <p>
                        Your prompt template must include the placeholders <code className="bg-amber-100 dark:bg-amber-900/40 px-1 py-0.5 rounded font-mono font-semibold">{"{taste_profile}"}</code> and <code className="bg-amber-100 dark:bg-amber-900/40 px-1 py-0.5 rounded font-mono font-semibold">{"{articles_contents_str}"}</code> for dynamic insertion.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {activeSettingsTab === 'settings' && (
                <div className="space-y-4">
                  <div className="flex flex-col gap-1">
                    <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Articles to Scan
                    </label>
                    <p className="text-xs text-slate-400 dark:text-slate-500">
                      Determine the limit of recent RSS articles to check before selecting high-signal entries.
                    </p>
                  </div>
                  <input
                    type="number"
                    min="1"
                    max="1000"
                    value={signalCandidateLimit ?? ''}
                    onChange={(e) => {
                      const val = e.target.value
                      setSignalCandidateLimit(val === '' ? null : parseInt(val, 10))
                    }}
                    placeholder="100 (Default)"
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:focus:border-slate-500 dark:focus:ring-slate-900/40"
                  />
                  <div className="rounded-xl bg-slate-50 p-4 dark:bg-slate-900/40 text-xs text-slate-500 dark:text-slate-400 space-y-2">
                    <div className="flex items-center gap-1.5 font-semibold text-slate-700 dark:text-slate-300">
                      <Info className="h-3.5 w-3.5 text-slate-500" />
                      Candidate Limit Guidelines
                    </div>
                    <p>
                      A higher limit lets Signal scan further back in your feeds but takes longer to run. The default scan pool limit is 100 articles. Set a custom number to fine tune this scan threshold.
                    </p>
                  </div>

                  <hr className="border-slate-200/60 dark:border-slate-800/60 my-6" />

                  <div className="flex items-center justify-between gap-4">
                    <div className="space-y-1">
                      <label className="block text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                        Background Research
                      </label>
                      <p className="text-xs text-slate-400 dark:text-slate-500">
                        Run a separate web research step to gather factual context before writing your brief.
                      </p>
                    </div>
                    
                    <button
                      type="button"
                      onClick={() => setSignalWebSearchEnabled(!signalWebSearchEnabled)}
                      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                        signalWebSearchEnabled ? 'bg-slate-900 dark:bg-slate-100' : 'bg-slate-200 dark:bg-slate-800'
                      }`}
                    >
                      <span
                        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                          signalWebSearchEnabled ? 'translate-x-5 dark:bg-slate-900' : 'translate-x-0'
                        }`}
                      />
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Actions Footer */}
            <div className="border-t border-slate-200/60 pt-4 dark:border-slate-800/60 flex items-center justify-between gap-3">
              <button
                onClick={handleResetProfile}
                className="inline-flex items-center gap-1.5 rounded-full px-3 py-2 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                title="Reset to default prompt guidelines"
              >
                <Undo2 className="h-3.5 w-3.5" />
                Reset to Default
              </button>
              
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setIsTasteProfileOpen(false)}
                  className="rounded-full px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveProfile}
                  disabled={saveStatus === 'saving'}
                  className="rounded-full bg-slate-900 px-5 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white flex items-center gap-2"
                >
                  {saveStatus === 'saving' && <Loader2 className="h-4 w-4 animate-spin" />}
                  {saveStatus === 'saved' ? 'Saved' : saveStatus === 'error' ? 'Error' : 'Save Profile'}
                </button>
              </div>
            </div>

          </aside>
        </div>,
        document.body
      )}
    </div>
  )
}
