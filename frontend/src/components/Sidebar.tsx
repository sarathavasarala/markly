import React, { useState } from 'react'
import {
    Folder as FolderIcon,
    FolderPlus,
    Edit2,
    Trash2,
    LayoutGrid,
} from 'lucide-react'
import { useFolderStore } from '../stores/folderStore'
import { useUIStore } from '../stores/uiStore'

export default function Sidebar() {
    const { folders, selectedFolderId, setSelectedFolderId, createFolder, deleteFolder, updateFolder } = useFolderStore()
    const { isSidebarOpen, setIsSidebarOpen } = useUIStore()
    const [isCreating, setIsCreating] = useState(false)
    const [newFolderName, setNewFolderName] = useState('')
    const [editingId, setEditingId] = useState<string | null>(null)
    const [editingName, setEditingName] = useState('')

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!newFolderName.trim()) return
        try {
            await createFolder(newFolderName.trim())
            setNewFolderName('')
            setIsCreating(false)
        } catch (err) {
            console.error(err)
        }
    }
    const handleEdit = async (id: string) => {
        if (!editingName.trim()) return
        try {
            await updateFolder(id, { name: editingName.trim() })
            setEditingId(null)
        } catch (err) {
            console.error(err)
        }
    }

    return (
        <>
            {/* Mobile Backdrop */}
            {isSidebarOpen && (
                <div
                    className="fixed inset-0 bg-gray-900/50 backdrop-blur-sm z-40 lg:hidden"
                    onClick={() => setIsSidebarOpen(false)}
                />
            )}

            <aside className={`
            fixed left-0 top-16 bottom-0 w-64 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 
            transition-transform duration-300 ease-in-out z-40
            ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          `}>
                <div className="flex flex-col h-full p-4 overflow-y-auto custom-scrollbar">
                    {/* Main Navigation */}
                    <div className="space-y-1 mb-6">
                        <button
                            onClick={() => setSelectedFolderId(null)}
                            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${selectedFolderId === null
                                ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400'
                                : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800'
                                }`}
                        >
                            <LayoutGrid className="w-4 h-4" />
                            Everything
                        </button>
                    </div>

                    {/* Folders Section */}
                    <div className="mb-4">
                        <div className="flex items-center justify-between px-3 mb-2">
                            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Folders</h2>
                            <button
                                onClick={() => setIsCreating(true)}
                                className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md text-gray-400 hover:text-primary-600"
                                title="New Folder"
                            >
                                <FolderPlus className="w-4 h-4" />
                            </button>
                        </div>

                        {isCreating && (
                            <form onSubmit={handleCreate} className="px-3 mb-2">
                                <input
                                    autoFocus
                                    type="text"
                                    placeholder="Folder name..."
                                    className="w-full px-2 py-1.5 text-sm bg-gray-50 dark:bg-gray-800 border border-primary-500 rounded-md focus:ring-1 focus:ring-primary-500 outline-none dark:text-white"
                                    value={newFolderName}
                                    onChange={(e) => setNewFolderName(e.target.value)}
                                    onBlur={() => !newFolderName && setIsCreating(false)}
                                />
                            </form>
                        )}

                        <div className="space-y-1">
                            {folders.map((folder) => (
                                <div key={folder.id} className="group relative">
                                    {editingId === folder.id ? (
                                        <input
                                            autoFocus
                                            className="w-full px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-primary-500 rounded-lg outline-none dark:text-white"
                                            value={editingName}
                                            onChange={(e) => setEditingName(e.target.value)}
                                            onBlur={() => handleEdit(folder.id)}
                                            onKeyDown={(e) => e.key === 'Enter' && handleEdit(folder.id)}
                                        />
                                    ) : (
                                        <button
                                            onClick={() => setSelectedFolderId(folder.id)}
                                            className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-colors ${selectedFolderId === folder.id
                                                ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400'
                                                : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800'
                                                }`}
                                        >
                                            <div className="flex items-center gap-3 truncate">
                                                <FolderIcon className="w-4 h-4 flex-shrink-0" />
                                                <span className="truncate">{folder.name}</span>
                                            </div>

                                            <div className="hidden group-hover:flex items-center gap-1">
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation()
                                                        setEditingId(folder.id)
                                                        setEditingName(folder.name)
                                                    }}
                                                    className="p-1 hover:text-primary-600 text-gray-400"
                                                >
                                                    <Edit2 className="w-3 h-3" />
                                                </button>
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation()
                                                        if (window.confirm('Delete folder? Bookmarks will be unfiled.')) {
                                                            deleteFolder(folder.id)
                                                        }
                                                    }}
                                                    className="p-1 hover:text-red-600 text-gray-400"
                                                >
                                                    <Trash2 className="w-3 h-3" />
                                                </button>
                                            </div>
                                        </button>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </aside>
        </>
    )
}
