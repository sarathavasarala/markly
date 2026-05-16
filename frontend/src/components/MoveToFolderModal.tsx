import { useState, useMemo } from 'react'
import { Folder as FolderIcon, Search, X, BookMarked, Check } from 'lucide-react'
import { useFolderStore } from '../stores/folderStore'

interface MoveToFolderModalProps {
    isOpen: boolean
    onClose: () => void
    currentFolderId: string | null
    onSelect: (folderId: string | null) => Promise<void>
}

export default function MoveToFolderModal({ isOpen, onClose, currentFolderId, onSelect }: MoveToFolderModalProps) {
    const { folders } = useFolderStore()
    const [searchQuery, setSearchQuery] = useState('')
    const [isSubmitting, setIsSubmitting] = useState(false)

    const filteredFolders = useMemo(() => {
        return folders.filter(f =>
            f.name.toLowerCase().includes(searchQuery.toLowerCase())
        )
    }, [folders, searchQuery])

    if (!isOpen) return null

    const handleSelect = async (folderId: string | null) => {
        if (folderId === currentFolderId) return
        setIsSubmitting(true)
        try {
            await onSelect(folderId)
            onClose()
        } catch (err) {
            console.error(err)
        } finally {
            setIsSubmitting(false)
        }
    }

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
            <div
                className="absolute inset-0 bg-slate-950/40 backdrop-blur-sm animate-in fade-in duration-200"
                onClick={onClose}
            />

            <div className="relative w-full max-w-md rounded-card bg-surface-light shadow-card-hover ring-1 ring-white/60 dark:bg-surface-dark dark:ring-white/5 overflow-hidden animate-in zoom-in-95 duration-200">
                <div className="px-6 py-4 flex items-center justify-between">
                    <h2 className="font-display text-xl text-slate-950 dark:text-slate-50">Move to folder</h2>
                    <button
                        onClick={onClose}
                        className="p-2 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="px-6 pb-3">
                    <div className="relative">
                        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                        <input
                            autoFocus
                            type="text"
                            placeholder="Search folders…"
                            className="w-full pl-10 pr-4 py-2.5 rounded-2xl bg-white/80 ring-1 ring-slate-200 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:ring-2 focus:ring-indigo-300 dark:bg-slate-900/60 dark:ring-slate-700 dark:text-slate-100 dark:placeholder-slate-500 dark:focus:ring-indigo-500/40"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                </div>

                <div className="max-h-[350px] overflow-y-auto px-3 pb-3">
                    <button
                        disabled={isSubmitting}
                        onClick={() => handleSelect(null)}
                        className={`w-full flex items-center justify-between px-3 py-2.5 rounded-2xl transition-colors ${currentFolderId === null
                            ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-950'
                            : 'text-slate-700 hover:bg-slate-100/70 dark:text-slate-300 dark:hover:bg-slate-800/60'
                            }`}
                    >
                        <div className="flex items-center gap-3">
                            <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${currentFolderId === null
                                ? 'bg-white/15'
                                : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400'
                                }`}>
                                <BookMarked className="w-4 h-4" />
                            </div>
                            <span className="text-sm font-medium">Everything</span>
                        </div>
                        {currentFolderId === null && <Check className="w-4 h-4" />}
                    </button>

                    <div className="my-1.5 mx-3 h-px bg-slate-200/70 dark:bg-slate-800/70" />

                    {filteredFolders.length === 0 ? (
                        <div className="py-8 text-center text-slate-500 text-sm">
                            {searchQuery ? 'No folders match your search' : 'No folders created yet'}
                        </div>
                    ) : (
                        filteredFolders.map(folder => (
                            <button
                                key={folder.id}
                                disabled={isSubmitting}
                                onClick={() => handleSelect(folder.id)}
                                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-2xl transition-colors ${currentFolderId === folder.id
                                    ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-950'
                                    : 'text-slate-700 hover:bg-slate-100/70 dark:text-slate-300 dark:hover:bg-slate-800/60'
                                    }`}
                            >
                                <div className="flex items-center gap-3 min-w-0">
                                    <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${currentFolderId === folder.id
                                        ? 'bg-white/15'
                                        : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400'
                                        }`}>
                                        <FolderIcon className="w-4 h-4" />
                                    </div>
                                    <span className="text-sm font-medium truncate">{folder.name}</span>
                                </div>
                                {currentFolderId === folder.id && <Check className="w-4 h-4 shrink-0" />}
                            </button>
                        ))
                    )}
                </div>

                <div className="px-6 py-3 border-t border-slate-200/70 dark:border-slate-800/70 flex justify-end">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-medium text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
                    >
                        Cancel
                    </button>
                </div>
            </div>
        </div>
    )
}
