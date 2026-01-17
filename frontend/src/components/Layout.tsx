import { Outlet, Link, useNavigate } from 'react-router-dom'
import {
  BookMarked,
  Search,
  LogOut,
  Plus,
  Sun,
  Moon,
  X,
  Menu,
} from 'lucide-react'
import { useState, useEffect } from 'react'
import { useAuthStore } from '../stores/authStore'
import { useUIStore } from '../stores/uiStore'
import { useFolderStore } from '../stores/folderStore'
import Sidebar from './Sidebar'
import AddBookmarkModal from './AddBookmarkModal'
import EditBookmarkModal from './EditBookmarkModal'

export default function Layout({
  children,
  noPadding = false
}: {
  children?: React.ReactNode,
  noPadding?: boolean
}) {
  const [searchQuery, setSearchQuery] = useState('')
  const [isSearchOpen, setIsSearchOpen] = useState(false)
  const { logout, user, isAuthenticated } = useAuthStore((state) => ({
    logout: state.logout,
    user: state.user,
    isAuthenticated: state.isAuthenticated
  }))
  const { theme, toggleTheme, editingBookmark, setEditingBookmark, isAddModalOpen, setIsAddModalOpen, isSidebarOpen, toggleSidebar } = useUIStore()
  const { fetchFolders } = useFolderStore()
  const navigate = useNavigate()

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

  // Update document title post-login
  useEffect(() => {
    if (isAuthenticated) {
      const displayName = userName || userEmail.split('@')[0]
      if (displayName) {
        document.title = `${displayName} - Markly`
      } else {
        document.title = 'Markly'
      }
      fetchFolders()
    } else {
      document.title = 'Markly - Your smart bookmark library'
    }

    return () => {
      document.title = 'Markly - Your smart bookmark library'
    }
  }, [userName, userEmail, fetchFolders, isAuthenticated])

  return (
    <div className="min-h-screen bg-white dark:bg-gray-950 transition-colors duration-300">
      {/* Header */}
      <header className={`fixed top-0 left-0 right-0 z-50 ${isAuthenticated ? 'bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-b border-gray-200 dark:border-gray-800' : 'bg-white/80 dark:bg-gray-950/80 backdrop-blur-md border-b border-gray-100 dark:border-gray-800'}`}>
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-10">
          <div className={`flex items-center justify-between ${isAuthenticated ? 'h-16' : 'h-20'} gap-4`}>
            {/* Logo */}
            <div className="flex items-center gap-3">
              {isAuthenticated && (
                <button
                  onClick={toggleSidebar}
                  className="p-2 -ml-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
                >
                  <Menu className="w-5 h-5" />
                </button>
              )}
              <Link to="/" className={`flex items-center gap-3 flex-shrink-0 ${!isAuthenticated ? '-ml-1' : ''}`}>
                <BookMarked className={`${isAuthenticated ? 'w-7 h-7' : 'w-8 h-8'} text-primary-600`} />
                <span className={`${isAuthenticated ? 'text-lg sm:block hidden' : 'text-2xl'} font-black text-gray-900 dark:text-white tracking-tight`}>
                  markly
                </span>
              </Link>
            </div>

            {isAuthenticated ? (
              <>
                {/* Mobile Search Toggle */}
                <div className="sm:hidden flex-1 flex justify-end">
                  {isSearchOpen ? (
                    <form onSubmit={handleSearch} className="absolute inset-x-0 top-0 h-16 bg-white dark:bg-gray-900 flex items-center px-4 z-50">
                      <Search className="w-5 h-5 text-gray-400 mr-2" />
                      <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search bookmarks..."
                        autoFocus
                        className="flex-1 bg-transparent border-none focus:ring-0 text-gray-900 dark:text-white placeholder-gray-400"
                      />
                      <button
                        type="button"
                        onClick={() => setIsSearchOpen(false)}
                        className="p-2 ml-2 text-gray-500"
                      >
                        <X className="w-5 h-5" />
                      </button>
                    </form>
                  ) : (
                    <button
                      onClick={() => setIsSearchOpen(true)}
                      className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    >
                      <Search className="w-5 h-5" />
                    </button>
                  )}
                </div>

                {/* Desktop Search Bar */}
                <form onSubmit={handleSearch} className="hidden sm:block flex-1 max-w-2xl px-4 lg:px-8">
                  <div className="relative">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search your bookmarks..."
                      className="w-full pl-12 pr-4 py-2 border border-gray-300 dark:border-gray-700 rounded-full bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-white placeholder-gray-400 focus:ring-2 focus:ring-primary-500 focus:border-transparent focus:bg-white dark:focus:bg-gray-700 transition-colors"
                    />
                  </div>
                </form>

                {/* Actions */}
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={() => setIsAddModalOpen(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-full hover:bg-primary-700 transition-colors font-medium"
                  >
                    <Plus className="w-5 h-5" />
                    <span className="hidden sm:inline">Add</span>
                  </button>

                  {/* User Avatar/Initials */}
                  <div className="relative group">
                    <Link
                      to={`/@${userEmail.split('@')[0]}`}
                      className="block"
                      title="View your public profile"
                    >
                      {userAvatar ? (
                        <img
                          src={userAvatar}
                          alt={userName || userEmail}
                          className="w-8 h-8 rounded-full border-2 border-gray-200 dark:border-gray-700 cursor-pointer hover:border-primary-500 transition-colors"
                        />
                      ) : (
                        <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center text-white text-sm font-medium cursor-pointer hover:bg-primary-500 transition-colors">
                          {userInitials}
                        </div>
                      )}
                    </Link>
                  </div>

                  <button
                    onClick={toggleTheme}
                    className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                  >
                    {theme === 'light' ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
                  </button>

                  <button
                    onClick={logout}
                    className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                  >
                    <LogOut className="w-5 h-5" />
                  </button>
                </div>
              </>
            ) : (
              <div className="flex items-center gap-4">
                <button
                  onClick={() => navigate('/login')}
                  className="px-6 py-3 bg-gray-800 hover:bg-gray-700 text-white text-[10px] font-black uppercase tracking-widest rounded-xl transition-all border border-gray-700/50 shadow-lg shadow-black/20"
                >
                  Sign In
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className={`flex ${isAuthenticated ? 'pt-16' : 'pt-24'}`}>
        {isAuthenticated && !noPadding && <Sidebar />}
        <main className={`flex-1 w-full transition-all duration-300 ${noPadding ? '' : `${isSidebarOpen && isAuthenticated ? 'lg:pl-64' : ''}`}`}>
          <div className={noPadding ? '' : "max-w-screen-2xl mx-auto pt-6 pb-8 px-4 sm:px-6 lg:px-10 w-full overflow-hidden"}>
            {children || <Outlet />}
          </div>
        </main>
      </div>

      {isAuthenticated && (
        <>
          <AddBookmarkModal
            isOpen={isAddModalOpen}
            onClose={() => setIsAddModalOpen(false)}
          />
          <EditBookmarkModal
            bookmark={editingBookmark}
            onClose={() => setEditingBookmark(null)}
          />
        </>
      )}
    </div>
  )
}
