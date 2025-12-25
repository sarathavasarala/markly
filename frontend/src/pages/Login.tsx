import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookMarked, Loader2, AlertCircle } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'

export default function Login() {
  const [secretPhrase, setSecretPhrase] = useState('')
  const navigate = useNavigate()
  
  const { login, isLoading, error, clearError } = useAuthStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!secretPhrase.trim()) return
    
    const success = await login(secretPhrase)
    
    if (success) {
      navigate('/')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-primary-100 dark:from-gray-900 dark:to-gray-800 px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary-600 rounded-2xl mb-4">
            <BookMarked className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Markly
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Your smart bookmark library
          </p>
        </div>

        {/* Login Form */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
            Welcome back
          </h2>
          
          {error && (
            <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg flex items-center gap-2 text-red-600 dark:text-red-400">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm">{error}</span>
              <button 
                onClick={clearError}
                className="ml-auto text-red-400 hover:text-red-600"
              >
                ✕
              </button>
            </div>
          )}
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label 
                htmlFor="secret" 
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
              >
                Secret Phrase
              </label>
              <input
                type="password"
                id="secret"
                value={secretPhrase}
                onChange={(e) => setSecretPhrase(e.target.value)}
                placeholder="Enter your secret phrase"
                className="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                autoFocus
              />
            </div>
            
            <button
              type="submit"
              disabled={isLoading || !secretPhrase.trim()}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {isLoading && <Loader2 className="w-5 h-5 animate-spin" />}
              {isLoading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-sm text-gray-500 dark:text-gray-400">
          Personal bookmark library powered by AI
        </p>
      </div>
    </div>
  )
}
