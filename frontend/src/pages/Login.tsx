import { useNavigate } from 'react-router-dom'
import { BookMarked, AlertCircle } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { useEffect } from 'react'

export default function Login() {
  const navigate = useNavigate()
  const { signInWithGoogle, isAuthenticated, isLoading, error, clearError } = useAuthStore()

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/')
    }
  }, [isAuthenticated, navigate])

  useEffect(() => {
    document.title = 'markly - Never lose a great link again'
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
              A quiet home for the links you want to remember.
            </p>
          </div>

          <div className="space-y-5">
            <div>
              <h2 className="font-display text-2xl text-slate-950 dark:text-slate-50">Sign in</h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Continue with Google to access your library.
              </p>
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
      </div>

      {/* Right: sample card preview */}
      <div className="hidden md:flex flex-1 items-center justify-center p-12 lg:p-20">
        <div className="w-full max-w-md space-y-6">
          <SampleCard
            title="Scaling product work without losing craft"
            domain="linear.app"
            summary="A quiet meditation on how small product teams keep shipping with care: write the doc, sweat the details, ship slowly."
            tags={['product', 'craft', 'workflow']}
          />
          <SampleCard
            title="The bookshelf as personal interface"
            domain="aworkinglibrary.com"
            summary="What a curated reading list says about how we think — and why a library, not an algorithm, still feels like home."
            tags={['reading', 'design']}
          />
          <p className="text-center text-sm text-slate-500 dark:text-slate-400">
            Save links. Find them later. That's the whole thing.
          </p>
        </div>
      </div>
    </div>
  )
}

function SampleCard({ title, domain, summary, tags }: { title: string, domain: string, summary: string, tags: string[] }) {
  return (
    <div className="rounded-card bg-surface-light shadow-card ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 p-5">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-9 h-9 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-500 dark:text-slate-400 text-xs font-medium">
          {domain[0].toUpperCase()}
        </div>
        <span className="text-xs text-slate-500 dark:text-slate-400">{domain}</span>
      </div>
      <h3 className="font-display text-[1.4rem] text-slate-950 dark:text-slate-50 leading-tight">
        {title}
      </h3>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300 leading-relaxed line-clamp-2">{summary}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {tags.map(tag => (
          <span key={tag} className="px-2.5 py-0.5 rounded-full text-[11px] font-medium lowercase bg-white text-slate-600 ring-1 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700">
            {tag}
          </span>
        ))}
      </div>
    </div>
  )
}
