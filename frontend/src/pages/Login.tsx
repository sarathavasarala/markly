import { useNavigate } from 'react-router-dom'
import { BookMarked, AlertCircle } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { useEffect, useState } from 'react'

export default function Login() {
  const navigate = useNavigate()
  const { signInWithGoogle, isAuthenticated, isLoading, error, clearError } = useAuthStore()

  const [activeSlide, setActiveSlide] = useState(0)

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/')
    }
  }, [isAuthenticated, navigate])

  useEffect(() => {
    const timer = setInterval(() => {
      setActiveSlide((prev) => (prev === 0 ? 1 : 0))
    }, 6000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    document.title = 'markly - your daily reading brief'
  }, [])

  const handleLogin = async () => {
    await signInWithGoogle()
  }

  return (
    <div className="min-h-screen bg-[#eef1ee] text-slate-950 dark:bg-[#0b0d11] dark:text-slate-100 flex flex-col md:flex-row">
      {/* Left: sign-in */}
      <div className="flex-1 flex items-center justify-center p-8 md:p-12 lg:p-16">
        <div className="w-full max-w-sm">
          <div className="mb-10">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-slate-900 text-white mb-5 dark:bg-slate-100 dark:text-slate-950">
              <BookMarked className="w-6 h-6" />
            </div>
            <h1 className="font-display text-5xl text-slate-950 dark:text-slate-50 leading-none">markly</h1>
            <p className="mt-3 text-base text-slate-600 dark:text-slate-300">
              Your daily brief from the blogs and newsletters you follow.
            </p>
          </div>

          <div className="space-y-5">
            <div>
              <h2 className="font-display text-2xl text-slate-950 dark:text-slate-50">Sign in</h2>
            </div>

            {error && (
              <div className="px-4 py-3 rounded-2xl bg-rose-50 text-rose-700 dark:bg-rose-900/20 dark:text-rose-300 flex items-start gap-2 text-sm">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div className="flex-1">{error}</div>
                <button onClick={clearError} className="text-rose-700/60 hover:text-rose-700 dark:text-rose-300/60 dark:hover:text-rose-300">
                  ✕
                </button>
              </div>
            )}

            <button
              onClick={handleLogin}
              disabled={isLoading}
              className="w-full h-12 flex items-center justify-center gap-3 rounded-full bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white transition-colors disabled:opacity-50"
            >
              {isLoading ? (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white dark:border-slate-950"></div>
              ) : (
                <>
                  <svg className="w-4 h-4" viewBox="0 0 24 24">
                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1c-3.17 0-5.92 1.83-7.24 4.5l3.66 2.85c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                  </svg>
                  Continue with Google
                </>
              )}
            </button>

            <p className="text-xs text-slate-500 dark:text-slate-400">
              By signing in you agree to keep things calm and well-curated.
            </p>
          </div>
        </div>
      </div>      {/* Right: sample card preview */}
      <div className="hidden md:flex flex-1 items-center justify-center p-12 lg:p-20">
        <div className="w-full max-w-md space-y-6">
          <div className="min-h-[480px] flex flex-col justify-between">
            {activeSlide === 0 ? (
              <div className="rounded-card bg-surface-light shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 p-6 text-left flex-1 flex flex-col justify-between animate-in fade-in duration-500">
                <div>
                  <div className="border-b border-slate-200/60 pb-3 dark:border-slate-800/60">
                    <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 block mb-0.5">Wednesday</span>
                    <h3 className="font-display text-2xl font-normal text-slate-950 dark:text-slate-50">
                      Today's brief
                    </h3>
                  </div>
                  <div className="rounded-2xl bg-slate-50/50 px-4 py-3 mt-4 dark:bg-slate-900/30 ring-1 ring-slate-200/50 dark:ring-slate-800/50">
                    <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                      <span className="font-semibold text-slate-800 dark:text-slate-200">Your daily brief</span>, synthesized from recent articles across your feeds. Below are the themes and developments that stood out today.
                    </p>
                  </div>
                  <div className="space-y-5 mt-5 text-sm text-slate-800 dark:text-slate-300 leading-relaxed font-sans">
                    <div className="space-y-1">
                      <h4 className="font-semibold text-slate-950 dark:text-slate-50 text-xs uppercase tracking-wider">AI Architecture & Moats</h4>
                      <p className="text-xs sm:text-sm">
                        Apple and Meta are expanding their system-level advantages by routing computation and context differently. Apple is pursuing a split architecture to handle everyday tasks on-device, while Meta is leveraging its off-platform behavioral data to build context moats that stand apart from raw model capabilities.
                      </p>
                      {/* Skeleton lines to show there's more detail */}
                      <div className="space-y-2 pt-2 opacity-50">
                        <div className="h-2 bg-slate-300 dark:bg-slate-700 rounded w-full animate-pulse" />
                        <div className="h-2 bg-slate-300 dark:bg-slate-700 rounded w-11/12 animate-pulse" />
                        <div className="h-2 bg-slate-300 dark:bg-slate-700 rounded w-3/4 animate-pulse" />
                      </div>
                    </div>
                    <div className="space-y-1">
                      <h4 className="font-semibold text-slate-950 dark:text-slate-50 text-xs uppercase tracking-wider">Frontier Model Segmentation</h4>
                      <p className="text-xs sm:text-sm">
                        Enterprise adoption is shifting focus from benchmarks to operational controls. Anthropic is segmenting its API access by packaging safety classifiers and predictable safety classifiers directly into the Claude Fable model tier.
                      </p>
                      {/* Skeleton lines */}
                      <div className="space-y-2 pt-2 opacity-50">
                        <div className="h-2 bg-slate-300 dark:bg-slate-700 rounded w-full animate-pulse" />
                        <div className="h-2 bg-slate-300 dark:bg-slate-700 rounded w-5/6 animate-pulse" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-card bg-surface-light shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 p-6 text-left flex-1 flex flex-col justify-between animate-in fade-in duration-500">
                <div>
                  <div className="border-b border-slate-200/60 pb-3 dark:border-slate-800/60">
                    <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 block mb-0.5">How it works</span>
                    <h3 className="font-display text-2xl font-normal text-slate-950 dark:text-slate-50">
                      The reading loop
                    </h3>
                  </div>
                  
                  {/* Explainer Steps */}
                  <div className="mt-8 space-y-6 px-2">
                    {/* Step 1 */}
                    <div className="flex gap-4 relative">
                      <div className="absolute left-3 top-6 -bottom-6 w-px bg-slate-200 dark:bg-slate-800" />
                      <div className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-400">
                        1
                      </div>
                      <div className="space-y-0.5 text-left">
                        <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Follow</h4>
                        <p className="text-xs text-slate-500 dark:text-slate-450">Add the blogs and newsletters you already read.</p>
                      </div>
                    </div>

                    {/* Step 2 */}
                    <div className="flex gap-4 relative">
                      <div className="absolute left-3 top-6 -bottom-6 w-px bg-slate-200 dark:bg-slate-800" />
                      <div className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-400">
                        2
                      </div>
                      <div className="space-y-0.5 text-left">
                        <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Read</h4>
                        <p className="text-xs text-slate-500 dark:text-slate-455">markly turns them into one synthesized brief.</p>
                      </div>
                    </div>

                    {/* Step 3 */}
                    <div className="flex gap-4 relative">
                      <div className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-semibold text-slate-700 dark:bg-slate-800 dark:text-slate-400">
                        3
                      </div>
                      <div className="space-y-0.5 text-left">
                        <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Keep and share</h4>
                        <p className="text-xs text-slate-500 dark:text-slate-450">Save what's worth keeping, and your reading becomes a list others can follow.</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Carousel Pagination Dots */}
          <div className="flex flex-col items-center gap-3">
            <div className="flex justify-center gap-2">
              <button
                onClick={() => setActiveSlide(0)}
                className={`h-2 w-2 rounded-full transition-all duration-300 ${activeSlide === 0 ? 'bg-slate-800 dark:bg-slate-200 w-4' : 'bg-slate-350 dark:bg-slate-700 hover:bg-slate-400'}`}
                aria-label="View daily brief preview"
              />
              <button
                onClick={() => setActiveSlide(1)}
                className={`h-2 w-2 rounded-full transition-all duration-300 ${activeSlide === 1 ? 'bg-slate-800 dark:bg-slate-200 w-4' : 'bg-slate-350 dark:bg-slate-700 hover:bg-slate-400'}`}
                aria-label="View features diagram"
              />
            </div>
            <p className="text-center text-xs text-slate-450 dark:text-slate-500">
              The good stuff from your feeds, every day.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

