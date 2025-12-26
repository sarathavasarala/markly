import { useNavigate } from 'react-router-dom'
import { BookMarked, AlertCircle, Sparkles, Search, Layers, Zap, ChevronRight } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { useEffect, useState } from 'react'

export default function Login() {
  const navigate = useNavigate()
  const { signInWithGoogle, isAuthenticated, isLoading, error, clearError } = useAuthStore()
  const [previewIndex, setPreviewIndex] = useState(0)

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/')
    }
  }, [isAuthenticated, navigate])

  const handleLogin = async () => {
    await signInWithGoogle()
  }

  const mobilePreviews = [
    {
      headline: "Your bookmarks, organized simply.",
      title: "Scaling Design Systems for 2025",
      domain: "designlab.co / 5 min read",
      summary: "How modern product teams leverage token-based architectures to maintain consistency across global engineering squads.",
      tags: ["design", "architecture", "ux-strategy"],
      icon: <Layers className="w-5 h-5 text-blue-500" />
    },
    {
      headline: "Enriched with AI.",
      title: "Why Modern Analytics Efforts Fail",
      domain: "datanews.io / 12 min read",
      summary: "Common pitfalls in data engineering from zero to millions of daily orders, focusing on robust event tracking and observability.",
      tags: ["analytics", "bigquery", "strategy"],
      icon: <Sparkles className="w-5 h-5 text-primary-500" />
    },
    {
      headline: "Powered by semantic search.",
      title: "Memory in AI Agents Explained",
      domain: "techpulse.ai / 8 min read",
      summary: "An exploration of four memory types—working, episodic, semantic, and procedural—for building persistent agentic workflows.",
      tags: ["ai-agents", "memory-models", "workflow"],
      icon: <Search className="w-5 h-5 text-amber-500" />
    }
  ]

  useEffect(() => {
    const timer = setInterval(() => {
      setPreviewIndex((prev) => (prev + 1) % mobilePreviews.length)
    }, 3500)
    return () => clearInterval(timer)
  }, [mobilePreviews.length])

  const activePreview = mobilePreviews[previewIndex]

  // Shared Preview UI Component to keep it consistent
  const PreviewCard = ({ preview, index }: { preview: typeof mobilePreviews[0], index: number }) => (
    <div key={index} className="w-full max-w-md flex flex-col items-center">
      <h3 className="text-xl md:text-2xl font-bold text-white mb-8 md:mb-12 text-center h-8 md:h-10 animate-in fade-in slide-in-from-bottom-2 duration-700">
        {preview.headline}
      </h3>

      <div className="w-full relative px-4 md:px-0">
        <div className="flex flex-col overflow-hidden rounded-3xl border border-primary-900/30 bg-gray-900/80 p-6 md:p-8 backdrop-blur-md shadow-2xl transition-all duration-500 animate-in fade-in slide-in-from-right-8">
          <div className="flex items-center gap-5 mb-5 md:mb-6">
            <div className="w-12 h-12 md:w-14 md:h-14 rounded-2xl bg-gray-800 flex items-center justify-center shadow-inner">
              {preview.icon}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-base md:text-lg font-bold text-white leading-tight truncate">
                {preview.title}
              </div>
              <div className="text-xs text-gray-500 font-medium truncate mt-1">
                {preview.domain}
              </div>
            </div>
          </div>

          <div className="space-y-4 md:space-y-6">
            <p className="text-sm md:text-base text-gray-400 leading-relaxed italic border-l-2 border-primary-800 pl-4">
              "{preview.summary}"
            </p>

            <div className="flex flex-wrap gap-2.5 mt-2">
              {preview.tags.map(tag => (
                <span key={tag} className="px-3 py-1.5 rounded-lg bg-gray-800 text-[10px] md:text-xs text-gray-400 font-bold uppercase tracking-wider">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Progress Indicators */}
        <div className="flex justify-center gap-2 mt-8 md:mt-12">
          {mobilePreviews.map((_, i) => (
            <div
              key={i}
              className={`h-1.5 rounded-full transition-all duration-500 ${i === previewIndex ? 'w-8 bg-primary-500' : 'w-2 bg-gray-800'}`}
            />
          ))}
        </div>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-gray-950">
      {/* Left Side: Login Form (Dark Mode) */}
      <div className="flex-1 flex items-center justify-center p-6 md:p-12 lg:p-20 relative overflow-hidden">
        {/* Background Glows */}
        <div className="absolute top-0 right-0 -translate-y-1/2 translate-x-1/4 w-96 h-96 bg-primary-600/10 rounded-full blur-[128px] opacity-50" />
        <div className="absolute bottom-0 left-0 translate-y-1/2 -translate-x-1/4 w-96 h-96 bg-primary-800/20 rounded-full blur-[128px] opacity-50" />

        <div className="w-full max-w-sm relative">
          {/* Logo */}
          <div className="mb-12 text-center md:text-left">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-primary-500 to-primary-700 rounded-3xl mb-6 shadow-xl shadow-primary-500/20">
              <BookMarked className="w-8 h-8 text-white" />
            </div>
            <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
              Markly
            </h1>
            <p className="text-gray-400 mt-2 font-medium text-lg">
              Your smart bookmark library
            </p>
          </div>

          <div className="space-y-8">
            <div className="text-center md:text-left">
              <h2 className="text-2xl font-semibold text-white mb-2">
                Welcome back
              </h2>
              <p className="text-gray-400">
                Please sign in to access your collection
              </p>
            </div>

            {error && (
              <div className="p-4 bg-red-900/20 border border-red-900/30 rounded-2xl flex items-center gap-3 text-red-400 animate-in fade-in slide-in-from-top-1">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <div className="text-sm flex-1">{error}</div>
                <button
                  onClick={clearError}
                  className="text-red-400 hover:text-red-600 p-1"
                >
                  ✕
                </button>
              </div>
            )}

            <button
              onClick={handleLogin}
              disabled={isLoading}
              className="w-full h-[64px] flex items-center justify-center gap-4 px-6 bg-gray-900 border border-gray-800 rounded-2xl hover:bg-gray-800 text-white transition-all duration-200 font-bold shadow-sm active:scale-[0.98] disabled:opacity-50 group border-b-4 border-gray-700 active:border-b-0 active:translate-y-[2px]"
            >
              {isLoading ? (
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600"></div>
              ) : (
                <>
                  <svg className="w-6 h-6 group-hover:rotate-12 transition-transform" viewBox="0 0 24 24">
                    <path
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      fill="#4285F4"
                    />
                    <path
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      fill="#34A853"
                    />
                    <path
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                      fill="#FBBC05"
                    />
                    <path
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                      fill="#EA4335"
                    />
                  </svg>
                  <span className="text-lg">Continue with Google</span>
                  <ChevronRight className="w-5 h-5 text-gray-600 group-hover:translate-x-1 transition-transform" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Right Side: Value Prop (Desktop Carousel) */}
      <div className="hidden md:flex flex-1 bg-gradient-to-br from-primary-900/40 to-gray-950 items-center justify-center p-12 lg:p-20 relative overflow-hidden border-l border-white/5">
        {/* Abstract background elements */}
        <div className="absolute top-0 right-0 -translate-y-1/2 translate-x-1/4 w-full h-full bg-primary-600/5 rounded-full blur-[160px] animate-pulse" />

        <div className="relative w-full max-w-lg flex flex-col items-center">
          <PreviewCard preview={activePreview} index={previewIndex} />
        </div>
      </div>

      {/* Mobile-only Preview (Inside form column, only visible on small screens) */}
      <div className="md:hidden px-6 pb-12 w-full max-w-sm mx-auto">
        <PreviewCard preview={activePreview} index={previewIndex} />
      </div>
    </div>
  )
}
