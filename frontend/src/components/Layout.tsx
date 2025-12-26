import { Outlet, Link, useNavigate } from 'react-router-dom'
import {
  BookMarked,
  Search,
  LogOut,
  Plus,
  Upload,
  Sun,
  Moon,
} from 'lucide-react'
import { useState } from 'react'
import { useAuthStore } from '../stores/authStore'
import { useUIStore } from '../stores/uiStore'
import AddBookmarkModal from './AddBookmarkModal'
import EditBookmarkModal from './EditBookmarkModal'

export default function Layout() {
  const [searchQuery, setSearchQuery] = useState('')
  const [showAddModal, setShowAddModal] = useState(false)
  const navigate = useNavigate()

  const { logout, user } = useAuthStore((state) => ({ logout: state.logout, user: state.user }))
  const { theme, toggleTheme, editingBookmark, setEditingBookmark } = useUIStore()

  // Get user display info
  const userEmail = user?.email || ''
  const userName = user?.user_metadata?.full_name || user?.user_metadata?.name || ''
  const userAvatar = user?.user_metadata?.avatar_url || user?.user_metadata?.picture || ''
  const userInitials = userName
    ? userName.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)
    : userEmail.slice(0, 2).toUpperCase()

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-10">
          <div className="flex items-center justify-between h-16 gap-4">
            {/* Logo */}
            <Link to="/" className="flex items-center gap-2 flex-shrink-0">
              <BookMarked className="w-7 h-7 text-primary-600" />
              <span className="text-lg font-bold text-gray-900 dark:text-white hidden sm:block">
                Markly
              </span>
            </Link>

            {/* Global Search Bar */}
            <form onSubmit={handleSearch} className="flex-1 max-w-2xl">
              <div className="relative">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search your bookmarks..."
                  className="w-full pl-12 pr-4 py-2.5 border border-gray-300 dark:border-gray-600 rounded-full bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-primary-500 focus:border-transparent focus:bg-white dark:focus:bg-gray-600 transition-colors"
                />
              </div>
            </form>

            {/* Actions */}
            <div className="flex items-center gap-2 flex-shrink-0">
              <button
                onClick={() => navigate('/import')}
                className="hidden sm:flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-100 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors font-medium"
              >
                <Upload className="w-5 h-5" />
                <span className="hidden md:inline">Import</span>
              </button>

              <button
                onClick={() => setShowAddModal(true)}
                className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-full hover:bg-primary-700 transition-colors font-medium"
              >
                <Plus className="w-5 h-5" />
                <span className="hidden sm:inline">Add</span>
              </button>

              {/* User Avatar/Initials */}
              <div className="relative group">
                {userAvatar ? (
                  <img
                    src={userAvatar}
                    alt={userName || userEmail}
                    className="w-8 h-8 rounded-full border-2 border-gray-200 dark:border-gray-600 cursor-pointer"
                    title={userEmail}
                  />
                ) : (
                  <div
                    className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center text-white text-sm font-medium cursor-pointer"
                    title={userEmail}
                  >
                    {userInitials}
                  </div>
                )}
                {/* Tooltip */}
                <div className="absolute right-0 top-full mt-2 px-3 py-1.5 bg-gray-900 dark:bg-gray-700 text-white text-sm rounded-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 whitespace-nowrap z-50">
                  {userEmail}
                  <div className="absolute -top-1 right-3 w-2 h-2 bg-gray-900 dark:bg-gray-700 rotate-45"></div>
                </div>
              </div>

              <button
                onClick={toggleTheme}
                className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                title={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
              >
                {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
              </button>

              <button
                onClick={logout}
                className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                title="Logout"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-10 py-8">
        <Outlet />
      </main>

      {/* Add Bookmark Modal */}
      <AddBookmarkModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
      />
      {/* Edit Bookmark Modal */}
      <EditBookmarkModal
        bookmark={editingBookmark}
        onClose={() => setEditingBookmark(null)}
      />

    </div>
  )
}
