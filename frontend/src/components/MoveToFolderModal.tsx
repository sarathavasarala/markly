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
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-gray-900/60 backdrop-blur-sm animate-in fade-in duration-200"
                onClick={onClose}
            />

            {/* Modal */}
            <div className="relative w-full max-w-md bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border border-gray-100 dark:border-gray-800 overflow-hidden animate-in zoom-in-95 duration-200">
                {/* Header */}
                <div className="px-6 py-4 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between bg-gray-50/50 dark:bg-gray-800/50">
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                        <FolderIcon className="w-5 h-5 text-primary-600" />
                        Move to folder
                    </h2>
                    <button
                        onClick={onClose}
                        className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-full hover:bg-white dark:hover:bg-gray-700 transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Search */}
                <div className="p-4 border-b border-gray-100 dark:border-gray-800">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <input
                            autoFocus
                            type="text"
                            placeholder="Search folders..."
                            className="w-full pl-10 pr-4 py-2 bg-gray-50 dark:bg-gray-800 border-none rounded-xl text-sm focus:ring-2 focus:ring-primary-500 outline-none dark:text-white transition-all"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                </div>

                {/* List */}
                <div className="max-h-[350px] overflow-y-auto custom-scrollbar p-2">
                    {/* Default Option: Everything */}
                    <button
                        disabled={isSubmitting}
                        onClick={() => handleSelect(null)}
                        className={`w-full flex items-center justify-between p-3 rounded-xl transition-all ${currentFolderId === null
                            ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600'
                            : 'hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300'
                            }`}
                    >
                        <div className="flex items-center gap-3">
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${currentFolderId === null ? 'bg-primary-100 dark:bg-primary-900/40' : 'bg-gray-100 dark:bg-gray-800'
                                }`}>
                                <BookMarked className={`w-4 h-4 ${currentFolderId === null ? 'text-primary-600' : 'text-gray-400'}`} />
                            </div>
                            <span className="text-sm font-semibold uppercase tracking-tight">Everything</span>
                        </div>
                        {currentFolderId === null && <Check className="w-4 h-4" />}
                    </button>

                    <div className="h-px bg-gray-50 dark:bg-gray-800 my-2 mx-2" />

                    {filteredFolders.length === 0 ? (
                        <div className="py-8 text-center text-gray-400 text-sm">
                            {searchQuery ? 'No folders match your search' : 'No folders created yet'}
                        </div>
                    ) : (
                        filteredFolders.map(folder => (
                            <button
                                key={folder.id}
                                disabled={isSubmitting}
                                onClick={() => handleSelect(folder.id)}
                                className={`w-full flex items-center justify-between p-3 rounded-xl transition-all ${currentFolderId === folder.id
                                    ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-600'
                                    : 'hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300'
                                    }`}
                            >
                                <div className="flex items-center gap-3">
                                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${currentFolderId === folder.id ? 'bg-primary-100 dark:bg-primary-900/40' : 'bg-gray-100 dark:bg-gray-800'
                                        }`}>
                                        <FolderIcon className={`w-4 h-4 ${currentFolderId === folder.id ? 'text-primary-600' : 'text-gray-400'}`} />
                                    </div>
                                    <span className="text-sm font-semibold uppercase tracking-tight truncate max-w-[200px]">{folder.name}</span>
                                </div>
                                {currentFolderId === folder.id && <Check className="w-4 h-4" />}
                            </button>
                        ))
                    )}
                </div>

                {/* Footer */}
                <div className="p-4 bg-gray-50/50 dark:bg-gray-800/50 flex justify-end">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-bold text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors uppercase tracking-widest"
                    >
                        Cancel
                    </button>
                </div>
            </div>
        </div>
    )
}
