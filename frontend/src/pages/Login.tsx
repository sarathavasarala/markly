import { useNavigate } from 'react-router-dom'
import { BookMarked, AlertCircle, Sparkles, Search, Layers, Zap } from 'lucide-react'
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

  const handleLogin = async () => {
    await signInWithGoogle()
  }

  const valueProps = [
    {
      icon: <Layers className="w-6 h-6 text-primary-200" />,
      title: "Intelligent Curation",
      description: "A fast, distraction-free interface built to handle high-volume bookmark libraries with ease."
    },
    {
      icon: <Sparkles className="w-6 h-6 text-primary-200" />,
      title: "AI Enrichment",
      description: "Automated summaries and smart metadata extraction for every link you save, instantly."
    },
    {
      icon: <Search className="w-6 h-6 text-primary-200" />,
      title: "Semantic Search",
      description: "Find exactly what you need by searching for meaning and intent, not just exact keywords."
    },
    {
      icon: <Zap className="w-6 h-6 text-primary-200" />,
      title: "Smart Organization",
      description: "Multi-topic filtering that lets you slice through thousands of links in seconds."
    }
  ]

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-white dark:bg-gray-950">
      {/* Left Side: Login Form */}
      <div className="flex-1 flex items-center justify-center p-8 lg:p-12">
        <div className="w-full max-w-sm">
          {/* Logo */}
          <div className="mb-12">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-primary-600 rounded-xl mb-4">
              <BookMarked className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Markly
            </h1>
            <p className="text-gray-500 dark:text-gray-400">
              Your smart bookmark library
            </p>
          </div>

          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                Welcome back
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Please sign in to access your collection
              </p>
            </div>

            {error && (
              <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-900/30 rounded-lg flex items-center gap-3 text-red-600 dark:text-red-400">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <div className="text-sm flex-1">{error}</div>
                <button
                  onClick={clearError}
                  className="text-red-400 hover:text-red-600"
                >
                  ✕
                </button>
              </div>
            )}

            <button
              onClick={handleLogin}
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-3 px-4 py-3.5 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-900 dark:text-white transition-all duration-200 font-medium shadow-sm active:scale-[0.98] disabled:opacity-50"
            >
              {isLoading ? (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary-600"></div>
              ) : (
                <>
                  <svg className="w-5 h-5" viewBox="0 0 24 24">
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
                  <span>Continue with Google</span>
                </>
              )}
            </button>
          </div>

          <p className="mt-12 text-center text-xs text-gray-400 dark:text-gray-600">
            By continuing, you agree to our Terms of Service and Privacy Policy.
          </p>
        </div>
      </div>

      {/* Right Side: Value Prop */}
      <div className="hidden md:flex flex-1 bg-primary-600 dark:bg-primary-950 items-center justify-center p-12 lg:p-20 relative overflow-hidden">
        {/* Abstract background elements */}
        <div className="absolute top-0 right-0 -translate-y-1/2 translate-x-1/4 w-96 h-96 bg-primary-500 rounded-full blur-3xl opacity-20 animate-pulse" />
        <div className="absolute bottom-0 left-0 translate-y-1/2 -translate-x-1/4 w-96 h-96 bg-primary-700 rounded-full blur-3xl opacity-20" />

        <div className="relative max-w-lg">
          <h2 className="text-3xl font-bold text-white mb-12">
            The power to organize your digital world.
          </h2>

          <div className="grid gap-10">
            {valueProps.map((prop, index) => (
              <div key={index} className="flex gap-4 group">
                <div className="flex-shrink-0 w-12 h-12 bg-white/10 rounded-xl flex items-center justify-center backdrop-blur-sm group-hover:bg-white/20 transition-colors border border-white/10">
                  {prop.icon}
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white mb-1">
                    {prop.title}
                  </h3>
                  <p className="text-primary-100/70 leading-relaxed">
                    {prop.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
