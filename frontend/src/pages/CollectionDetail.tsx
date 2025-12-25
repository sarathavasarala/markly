import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { 
  ArrowLeft, 
  Loader2, 
  Edit2, 
  Trash2, 
  MoreVertical,
  X
} from 'lucide-react'
import { collectionsApi, Collection } from '../lib/api'
import { useCollectionsStore } from '../stores/collectionsStore'
import BookmarkCard from '../components/BookmarkCard'

export default function CollectionDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  
  const [collection, setCollection] = useState<Collection | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [showMenu, setShowMenu] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  
  const { updateCollection, deleteCollection, removeBookmarkFromCollection } = useCollectionsStore()

  useEffect(() => {
    if (id) {
      loadCollection()
    }
  }, [id])

  const loadCollection = async () => {
    if (!id) return
    
    setIsLoading(true)
    try {
      const response = await collectionsApi.get(id)
      setCollection(response.data)
      setEditName(response.data.name)
      setEditDescription(response.data.description || '')
    } catch (error) {
      console.error('Failed to load collection:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSaveEdit = async () => {
    if (!id || !editName.trim()) return
    
    await updateCollection(id, {
      name: editName.trim(),
      description: editDescription.trim() || undefined,
    })
    
    setCollection((prev) => prev ? {
      ...prev,
      name: editName.trim(),
      description: editDescription.trim() || null,
    } : null)
    
    setIsEditing(false)
  }

  const handleDelete = async () => {
    if (!id) return
    
    if (window.confirm('Delete this collection? Bookmarks will not be deleted.')) {
      await deleteCollection(id)
      navigate('/collections')
    }
  }

  const handleRemoveBookmark = async (bookmarkId: string) => {
    if (!id) return
    
    await removeBookmarkFromCollection(id, bookmarkId)
    
    setCollection((prev) => {
      if (!prev) return null
      return {
        ...prev,
        bookmarks: prev.bookmarks?.filter((b) => b.id !== bookmarkId),
        bookmark_count: Math.max(0, prev.bookmark_count - 1),
      }
    })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
      </div>
    )
  }

  if (!collection) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 dark:text-gray-400">Collection not found</p>
        <Link to="/collections" className="text-primary-600 hover:text-primary-700 mt-2 inline-block">
          Back to collections
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Link
            to="/collections"
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          
          {isEditing ? (
            <div className="space-y-3">
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="text-2xl font-bold px-2 py-1 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                autoFocus
              />
              <textarea
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                placeholder="Description (optional)"
                rows={2}
                className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white resize-none"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleSaveEdit}
                  className="px-3 py-1 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700"
                >
                  Save
                </button>
                <button
                  onClick={() => {
                    setIsEditing(false)
                    setEditName(collection.name)
                    setEditDescription(collection.description || '')
                  }}
                  className="px-3 py-1 text-gray-600 dark:text-gray-300 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div>
              <div className="flex items-center gap-3">
                <span className="text-3xl">{collection.icon}</span>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  {collection.name}
                </h1>
              </div>
              {collection.description && (
                <p className="text-gray-600 dark:text-gray-300 mt-2 ml-12">
                  {collection.description}
                </p>
              )}
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 ml-12">
                {collection.bookmark_count} bookmark{collection.bookmark_count !== 1 ? 's' : ''}
              </p>
            </div>
          )}
        </div>
        
        {!isEditing && (
          <div className="relative">
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            >
              <MoreVertical className="w-5 h-5" />
            </button>
            
            {showMenu && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
                <div className="absolute right-0 top-10 z-20 w-48 bg-white dark:bg-gray-700 rounded-lg shadow-lg border border-gray-200 dark:border-gray-600 py-1">
                  <button
                    onClick={() => {
                      setIsEditing(true)
                      setShowMenu(false)
                    }}
                    className="w-full flex items-center gap-2 px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600"
                  >
                    <Edit2 className="w-4 h-4" />
                    Edit Collection
                  </button>
                  <button
                    onClick={() => {
                      handleDelete()
                      setShowMenu(false)
                    }}
                    className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-600"
                  >
                    <Trash2 className="w-4 h-4" />
                    Delete Collection
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Bookmarks */}
      {collection.bookmarks && collection.bookmarks.length > 0 ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {collection.bookmarks.map((bookmark) => (
            <div key={bookmark.id} className="relative group">
              <BookmarkCard bookmark={bookmark} />
              <button
                onClick={() => handleRemoveBookmark(bookmark.id)}
                className="absolute top-2 right-2 p-1.5 bg-red-100 text-red-600 rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-200"
                title="Remove from collection"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-xl p-12 text-center">
          <p className="text-gray-500 dark:text-gray-400">
            No bookmarks in this collection yet
          </p>
          <Link
            to="/bookmarks"
            className="text-primary-600 hover:text-primary-700 mt-2 inline-block"
          >
            Browse bookmarks to add
          </Link>
        </div>
      )}
    </div>
  )
}
