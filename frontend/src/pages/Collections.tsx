import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { 
  FolderOpen, 
  Plus, 
  Loader2, 
  Sparkles, 
  Check, 
  X,
  Edit2
} from 'lucide-react'
import { useCollectionsStore } from '../stores/collectionsStore'
import { CollectionProposal } from '../lib/api'

export default function Collections() {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [showProposals, setShowProposals] = useState(false)
  
  const {
    collections,
    proposals,
    isLoading,
    isGenerating,
    fetchCollections,
    generateProposals,
    acceptProposals,
    clearProposals,
  } = useCollectionsStore()

  useEffect(() => {
    fetchCollections()
  }, [])

  const handleGenerateCollections = async () => {
    await generateProposals()
    setShowProposals(true)
  }

  const handleAcceptProposals = async (selectedProposals: CollectionProposal[]) => {
    await acceptProposals(selectedProposals)
    setShowProposals(false)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Collections
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Organize your bookmarks into collections
          </p>
        </div>
        
        <div className="flex items-center gap-3">
          <button
            onClick={handleGenerateCollections}
            disabled={isGenerating}
            className="flex items-center gap-2 px-4 py-2 bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 rounded-lg hover:bg-amber-200 dark:hover:bg-amber-900/50 transition-colors disabled:opacity-50"
          >
            {isGenerating ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            {isGenerating ? 'Analyzing...' : 'Generate Collections'}
          </button>
          
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Create
          </button>
        </div>
      </div>

      {/* Proposals Panel */}
      {showProposals && proposals.length > 0 && (
        <ProposalsPanel
          proposals={proposals}
          onAccept={handleAcceptProposals}
          onClose={() => {
            setShowProposals(false)
            clearProposals()
          }}
        />
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
        </div>
      )}

      {/* Collections Grid */}
      {!isLoading && collections.length > 0 && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {collections.map((collection) => (
            <Link
              key={collection.id}
              to={`/collections/${collection.id}`}
              className="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 hover:shadow-lg transition-shadow"
            >
              <div className="flex items-start gap-4">
                <div 
                  className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl"
                  style={{ backgroundColor: `${collection.color}20` }}
                >
                  {collection.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-900 dark:text-white truncate">
                    {collection.name}
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {collection.bookmark_count} bookmark{collection.bookmark_count !== 1 ? 's' : ''}
                  </p>
                  {collection.description && (
                    <p className="text-sm text-gray-600 dark:text-gray-300 mt-2 line-clamp-2">
                      {collection.description}
                    </p>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && collections.length === 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl p-12 text-center">
          <FolderOpen className="w-12 h-12 mx-auto text-gray-300 dark:text-gray-600 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            No collections yet
          </h3>
          <p className="text-gray-500 dark:text-gray-400 mb-6">
            Create collections manually or let AI generate them for you
          </p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={handleGenerateCollections}
              disabled={isGenerating}
              className="flex items-center gap-2 px-4 py-2 bg-amber-100 text-amber-700 rounded-lg hover:bg-amber-200"
            >
              <Sparkles className="w-4 h-4" />
              Generate with AI
            </button>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
            >
              <Plus className="w-4 h-4" />
              Create Manually
            </button>
          </div>
        </div>
      )}

      {/* Create Modal */}
      <CreateCollectionModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
      />
    </div>
  )
}

// Proposals Panel Component
interface ProposalsPanelProps {
  proposals: CollectionProposal[]
  onAccept: (selected: CollectionProposal[]) => void
  onClose: () => void
}

function ProposalsPanel({ proposals, onAccept, onClose }: ProposalsPanelProps) {
  const [selected, setSelected] = useState<Set<number>>(
    new Set(proposals.map((_, i) => i))
  )
  const [editingNames, setEditingNames] = useState<Record<number, string>>({})

  const toggleSelection = (index: number) => {
    const newSelected = new Set(selected)
    if (newSelected.has(index)) {
      newSelected.delete(index)
    } else {
      newSelected.add(index)
    }
    setSelected(newSelected)
  }

  const handleAccept = () => {
    const selectedProposals = proposals
      .filter((_, i) => selected.has(i))
      .map((p, i) => ({
        ...p,
        name: editingNames[i] || p.name,
      }))
    onAccept(selectedProposals)
  }

  return (
    <div className="bg-amber-50 dark:bg-amber-900/20 rounded-xl border border-amber-200 dark:border-amber-800 overflow-hidden">
      <div className="p-4 border-b border-amber-200 dark:border-amber-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-amber-600" />
          <h2 className="font-semibold text-gray-900 dark:text-white">
            AI-Generated Collection Proposals
          </h2>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-gray-400 hover:text-gray-600"
        >
          <X className="w-5 h-5" />
        </button>
      </div>
      
      <div className="p-4 space-y-3 max-h-[400px] overflow-y-auto">
        {proposals.map((proposal, index) => (
          <div
            key={index}
            className={`p-4 rounded-lg border transition-colors ${
              selected.has(index)
                ? 'bg-white dark:bg-gray-800 border-primary-300 dark:border-primary-600'
                : 'bg-gray-50 dark:bg-gray-700/50 border-gray-200 dark:border-gray-600'
            }`}
          >
            <div className="flex items-start gap-3">
              <button
                onClick={() => toggleSelection(index)}
                className={`mt-1 w-5 h-5 rounded border flex items-center justify-center flex-shrink-0 ${
                  selected.has(index)
                    ? 'bg-primary-600 border-primary-600 text-white'
                    : 'border-gray-300 dark:border-gray-500'
                }`}
              >
                {selected.has(index) && <Check className="w-3 h-3" />}
              </button>
              
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xl">{proposal.suggested_icon}</span>
                  {editingNames[index] !== undefined ? (
                    <input
                      type="text"
                      value={editingNames[index]}
                      onChange={(e) => setEditingNames({ ...editingNames, [index]: e.target.value })}
                      onBlur={() => {
                        if (!editingNames[index]?.trim()) {
                          const { [index]: _, ...rest } = editingNames
                          setEditingNames(rest)
                        }
                      }}
                      className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded"
                      autoFocus
                    />
                  ) : (
                    <>
                      <span className="font-medium text-gray-900 dark:text-white">
                        {proposal.name}
                      </span>
                      <button
                        onClick={() => setEditingNames({ ...editingNames, [index]: proposal.name })}
                        className="p-1 text-gray-400 hover:text-gray-600"
                      >
                        <Edit2 className="w-3 h-3" />
                      </button>
                    </>
                  )}
                  <span className="text-sm text-gray-500">
                    ({proposal.bookmark_count} bookmarks)
                  </span>
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                  {proposal.description}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
      
      <div className="p-4 border-t border-amber-200 dark:border-amber-800 flex items-center justify-between">
        <span className="text-sm text-gray-500">
          {selected.size} of {proposals.length} selected
        </span>
        <div className="flex items-center gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 hover:text-gray-800"
          >
            Cancel
          </button>
          <button
            onClick={handleAccept}
            disabled={selected.size === 0}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            Create {selected.size} Collection{selected.size !== 1 ? 's' : ''}
          </button>
        </div>
      </div>
    </div>
  )
}

// Create Collection Modal
interface CreateCollectionModalProps {
  isOpen: boolean
  onClose: () => void
}

function CreateCollectionModal({ isOpen, onClose }: CreateCollectionModalProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [icon, setIcon] = useState('📁')
  const [color, setColor] = useState('#6366f1')
  const [isSubmitting, setIsSubmitting] = useState(false)
  
  const { createCollection } = useCollectionsStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!name.trim()) return
    
    setIsSubmitting(true)
    
    const result = await createCollection({
      name: name.trim(),
      description: description.trim() || undefined,
      icon,
      color,
    })
    
    setIsSubmitting(false)
    
    if (result) {
      setName('')
      setDescription('')
      setIcon('📁')
      setColor('#6366f1')
      onClose()
    }
  }

  const iconOptions = ['📁', '📚', '💻', '🎨', '🔧', '📝', '🎯', '💡', '🚀', '⚡', '🔬', '📊']
  const colorOptions = ['#6366f1', '#8b5cf6', '#ec4899', '#ef4444', '#f97316', '#eab308', '#22c55e', '#14b8a6', '#3b82f6']

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="fixed inset-0 bg-black/50" onClick={onClose} />
      
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative w-full max-w-md bg-white dark:bg-gray-800 rounded-xl shadow-xl">
          <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Create Collection
            </h2>
            <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600">
              <X className="w-5 h-5" />
            </button>
          </div>
          
          <form onSubmit={handleSubmit} className="p-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My Collection"
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                autoFocus
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Description (optional)
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What's this collection about?"
                rows={2}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white resize-none"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Icon
              </label>
              <div className="flex flex-wrap gap-2">
                {iconOptions.map((emoji) => (
                  <button
                    key={emoji}
                    type="button"
                    onClick={() => setIcon(emoji)}
                    className={`w-10 h-10 text-xl rounded-lg flex items-center justify-center transition-colors ${
                      icon === emoji
                        ? 'bg-primary-100 dark:bg-primary-900 ring-2 ring-primary-500'
                        : 'bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600'
                    }`}
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Color
              </label>
              <div className="flex flex-wrap gap-2">
                {colorOptions.map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setColor(c)}
                    className={`w-8 h-8 rounded-full transition-transform ${
                      color === c ? 'ring-2 ring-offset-2 ring-gray-400 scale-110' : ''
                    }`}
                    style={{ backgroundColor: c }}
                  />
                ))}
              </div>
            </div>
            
            <div className="flex justify-end gap-3 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting || !name.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
                Create
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
