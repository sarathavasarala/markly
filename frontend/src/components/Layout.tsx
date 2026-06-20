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
import { feedsApi } from '../lib/api'
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
  const { theme, toggleTheme, editingBookmark, setEditingBookmark, isAddModalOpen, addModalPrefill, setIsAddModalOpen, openAddModal, isSidebarOpen, toggleSidebar } = useUIStore()
  const { fetchFolders, selectedFolderId } = useFolderStore()
  const navigate = useNavigate()

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

  useEffect(() => {
    if (isAuthenticated) {
      const displayName = userName || userEmail.split('@')[0]
      if (displayName) {
        document.title = `${displayName} - markly`
      } else {
        document.title = 'markly'
      }
      fetchFolders()
      feedsApi.refresh({ force: false, stale_after_minutes: 30 }).catch((error) => {
        console.error('Feed refresh failed:', error)
      })
    } else {
      document.title = 'markly - your daily reading brief'
    }

    return () => {
      document.title = 'markly - your daily reading brief'
    }
  }, [userName, userEmail, fetchFolders, isAuthenticated])

  return (
    <div className="min-h-screen bg-[#eef1ee] text-slate-950 transition-colors duration-300 dark:bg-[#0b0d11] dark:text-slate-100">
      <header className="fixed left-0 right-0 top-0 z-50 border-b border-slate-200/70 bg-[#eef1ee]/80 backdrop-blur-md dark:border-slate-800/80 dark:bg-[#0b0d11]/80">
        <div className="mx-auto max-w-screen-2xl px-4 sm:px-6 lg:px-10">
          <div className={`flex items-center justify-between gap-4 ${isAuthenticated ? 'h-16' : 'h-20'}`}>
            <div className="flex items-center gap-3">
              {isAuthenticated && (
                <button
                  onClick={toggleSidebar}
                  className="-ml-2 rounded-lg p-2 text-slate-500 transition-colors hover:bg-white/70 hover:text-slate-900 dark:hover:bg-slate-800 dark:hover:text-slate-100"
                >
                  <Menu className="h-5 w-5" />
                </button>
              )}
              <Link to="/" className={`flex flex-shrink-0 items-center gap-2 ${!isAuthenticated ? '-ml-1' : ''}`}>
                <BookMarked className={`${isAuthenticated ? 'h-6 w-6' : 'h-7 w-7'} text-slate-900 dark:text-slate-100`} />
                <span className={`${isAuthenticated ? 'hidden text-xl sm:block' : 'text-2xl'} font-display font-normal tracking-tight text-slate-950 dark:text-slate-50`}>
                  markly
                </span>
              </Link>
            </div>

            {isAuthenticated ? (
              <>
                {/* Mobile search toggle */}
                <div className="flex flex-1 justify-end sm:hidden">
                  {isSearchOpen ? (
                    <form onSubmit={handleSearch} className="absolute inset-x-0 top-0 z-50 flex h-16 items-center bg-[#eef1ee] px-4 dark:bg-[#0b0d11]">
                      <Search className="mr-2 h-5 w-5 text-slate-400" />
                      <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search bookmarks..."
                        autoFocus
                        className="flex-1 border-none bg-transparent text-slate-900 placeholder-slate-400 focus:ring-0 dark:text-white"
                      />
                      <button
                        type="button"
                        onClick={() => setIsSearchOpen(false)}
                        className="ml-2 p-2 text-slate-500"
                      >
                        <X className="h-5 w-5" />
                      </button>
                    </form>
                  ) : (
                    <button
                      onClick={() => setIsSearchOpen(true)}
                      className="p-2 text-slate-500 hover:text-slate-900 dark:hover:text-slate-100"
                    >
                      <Search className="h-5 w-5" />
                    </button>
                  )}
                </div>

                {/* Desktop search */}
                <form onSubmit={handleSearch} className="hidden max-w-2xl flex-1 px-4 sm:block lg:px-8">
                  <div className="relative">
                    <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search your bookmarks..."
                      className="w-full rounded-full border border-slate-200 bg-white px-12 py-2 text-sm text-slate-900 placeholder-slate-400 transition focus:border-slate-400 focus:bg-white focus:ring-2 focus:ring-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:placeholder-slate-500 dark:focus:border-slate-500 dark:focus:ring-slate-700/40"
                    />
                  </div>
                </form>

                <div className="flex flex-shrink-0 items-center gap-2">
                  <button
                    onClick={() => openAddModal()}
                    className="flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 active:scale-95 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
                  >
                    <Plus className="h-4 w-4" />
                    <span className="hidden sm:inline">Add</span>
                  </button>

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
                          className="h-8 w-8 cursor-pointer rounded-full border border-slate-200 transition-colors hover:border-slate-400 dark:border-slate-700 dark:hover:border-slate-500"
                        />
                      ) : (
                        <div className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full bg-slate-900 text-sm font-medium text-white transition-colors hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-950">
                          {userInitials}
                        </div>
                      )}
                    </Link>
                  </div>

                  <button
                    onClick={toggleTheme}
                    className="p-2 text-slate-500 transition-colors hover:text-slate-900 dark:hover:text-slate-100"
                  >
                    {theme === 'light' ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
                  </button>

                  <button
                    onClick={logout}
                    className="p-2 text-slate-500 transition-colors hover:text-slate-900 dark:hover:text-slate-100"
                  >
                    <LogOut className="h-5 w-5" />
                  </button>
                </div>
              </>
            ) : (
              <div className="flex items-center gap-4">
                <button
                  onClick={() => navigate('/login')}
                  className="rounded-full bg-slate-900 px-5 py-2 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-950 dark:hover:bg-white"
                >
                  Sign in
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <div className={`flex ${isAuthenticated ? 'pt-16' : 'pt-24'}`}>
        {isAuthenticated && !noPadding && <Sidebar />}
        <main className={`w-full flex-1 transition-all duration-300 ${noPadding ? '' : `${isSidebarOpen && isAuthenticated ? 'lg:pl-64' : ''}`}`}>
          <div className={noPadding ? '' : 'mx-auto w-full max-w-screen-2xl overflow-hidden px-4 pb-8 pt-6 sm:px-6 lg:px-10'}>
            {children || <Outlet />}
          </div>
        </main>
      </div>

      {isAuthenticated && (
        <>
          <AddBookmarkModal
            isOpen={isAddModalOpen}
            onClose={() => setIsAddModalOpen(false)}
            folderId={selectedFolderId}
            prefill={addModalPrefill}
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
