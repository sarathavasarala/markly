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
    const { folders, isLoading, selectedFolderId, setSelectedFolderId, createFolder, deleteFolder, updateFolder } = useFolderStore()
    const { isSidebarOpen, setIsSidebarOpen, setBookmarksViewMode } = useUIStore()
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

    const itemBase = 'w-full flex items-center gap-3 px-3 py-2 rounded-2xl text-sm font-medium transition-colors cursor-pointer'
    const itemActive = 'bg-white text-slate-950 ring-1 ring-slate-200 shadow-sm dark:bg-slate-800 dark:text-slate-50 dark:ring-slate-700'
    const itemIdle = 'text-slate-600 hover:bg-white/60 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-100'

    return (
        <>
            {isSidebarOpen && (
                <div
                    className="fixed inset-0 z-40 bg-slate-950/40 backdrop-blur-sm lg:hidden"
                    onClick={() => setIsSidebarOpen(false)}
                />
            )}

            <aside className={`fixed bottom-0 left-0 top-16 z-40 flex w-64 flex-col border-r border-slate-200/70 bg-[#eef1ee] transition-transform duration-300 ease-in-out dark:border-slate-800/80 dark:bg-[#0b0d11] ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
                <div className="flex h-full flex-col p-4">
                    <div className="mb-6 flex-shrink-0 space-y-1">
                        <button
                            onClick={() => setSelectedFolderId(null)}
                            className={`${itemBase} ${selectedFolderId === null ? itemActive : itemIdle}`}
                        >
                            <LayoutGrid className="h-4 w-4" />
                            Everything
                        </button>
                    </div>

                    <div className="custom-scrollbar min-h-0 flex-1 overflow-y-auto">
                        <div className="mb-2 flex items-center justify-between px-3">
                            <h2 className="text-xs font-medium text-slate-500 dark:text-slate-400">Folders</h2>
                            <button
                                onClick={() => setIsCreating(true)}
                                className="rounded-md p-1 text-slate-400 transition-colors hover:bg-white/70 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                                title="New folder"
                            >
                                <FolderPlus className="h-4 w-4" />
                            </button>
                        </div>

                        {isCreating && (
                            <form onSubmit={handleCreate} className="mb-2 px-3">
                                <input
                                    autoFocus
                                    type="text"
                                    placeholder="Folder name..."
                                    className="w-full rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900 outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:focus:border-indigo-500 dark:focus:ring-indigo-900/40"
                                    value={newFolderName}
                                    onChange={(e) => setNewFolderName(e.target.value)}
                                    onBlur={() => !newFolderName && setIsCreating(false)}
                                />
                            </form>
                        )}

                        <div className="space-y-1">
                            {isLoading ? (
                                [1, 2, 3].map(i => (
                                    <div key={i} className="mx-3 h-9 animate-pulse rounded-2xl bg-slate-200/70 dark:bg-slate-800/70" />
                                ))
                            ) : (
                                folders.map((folder) => (
                                    <div key={folder.id} className="group relative">
                                        {editingId === folder.id ? (
                                            <input
                                                autoFocus
                                                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                                                value={editingName}
                                                onChange={(e) => setEditingName(e.target.value)}
                                                onBlur={() => handleEdit(folder.id)}
                                                onKeyDown={(e) => e.key === 'Enter' && handleEdit(folder.id)}
                                            />
                                        ) : (
                                            <div
                                                role="button"
                                                tabIndex={0}
                                                onClick={() => {
                                                    setSelectedFolderId(folder.id)
                                                    setBookmarksViewMode('cards')
                                                }}
                                                onKeyDown={(e) => {
                                                    if (e.key === 'Enter') {
                                                        setSelectedFolderId(folder.id)
                                                        setBookmarksViewMode('cards')
                                                    }
                                                }}
                                                className={`${itemBase} justify-between ${selectedFolderId === folder.id ? itemActive : itemIdle}`}
                                            >
                                                <div className="flex min-w-0 flex-1 items-center gap-3 truncate">
                                                    <FolderIcon className="h-4 w-4 flex-shrink-0" />
                                                    <span className="truncate">{folder.name}</span>
                                                    {folder.bookmark_count !== undefined && folder.bookmark_count > 0 && (
                                                        <span className="ml-auto flex-shrink-0 text-xs tabular-nums text-slate-400 dark:text-slate-500">
                                                            {folder.bookmark_count}
                                                        </span>
                                                    )}
                                                </div>

                                                <div className="hidden items-center gap-1 group-hover:flex">
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation()
                                                            setEditingId(folder.id)
                                                            setEditingName(folder.name)
                                                        }}
                                                        className="p-1 text-slate-400 hover:text-indigo-700 dark:hover:text-indigo-300"
                                                    >
                                                        <Edit2 className="h-3 w-3" />
                                                    </button>
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation()
                                                            if (window.confirm('Delete folder? Bookmarks will be unfiled.')) {
                                                                deleteFolder(folder.id)
                                                            }
                                                        }}
                                                        className="p-1 text-slate-400 hover:text-red-600"
                                                    >
                                                        <Trash2 className="h-3 w-3" />
                                                    </button>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            </aside>
        </>
    )
}
