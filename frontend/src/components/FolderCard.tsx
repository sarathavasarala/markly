import { Folder as FolderIcon } from 'lucide-react'
import { Folder } from '../lib/api'

interface FolderCardProps {
    folder: Folder
    onClick: () => void
    matchCount?: number  // When filtering by tags, shows how many bookmarks match
}

export default function FolderCard({ folder, onClick, matchCount }: FolderCardProps) {
    const isFiltering = matchCount !== undefined
    const totalCount = folder.bookmark_count || 0

    return (
        <div
            role="button"
            tabIndex={0}
            onClick={onClick}
            onKeyDown={(e) => e.key === 'Enter' && onClick()}
            className="group bg-gradient-to-br from-primary-50 to-white dark:from-gray-800 dark:to-gray-900 
                       rounded-2xl border-2 border-primary-100 dark:border-gray-700 
                       p-6 cursor-pointer transition-all duration-200
                       hover:border-primary-300 dark:hover:border-primary-600 
                       hover:shadow-lg hover:shadow-primary-100/50 dark:hover:shadow-primary-900/30
                       hover:-translate-y-0.5"
        >
            <div className="flex items-center gap-4">
                {/* Folder Icon */}
                <div className="w-12 h-12 rounded-xl bg-primary-100 dark:bg-primary-900/40 
                               flex items-center justify-center
                               group-hover:bg-primary-200 dark:group-hover:bg-primary-800/50 transition-colors">
                    <FolderIcon className="w-6 h-6 text-primary-600 dark:text-primary-400" />
                </div>

                {/* Folder Info */}
                <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-gray-900 dark:text-white truncate text-lg">
                        {folder.name}
                    </h3>
                    {isFiltering ? (
                        <p className="text-sm text-primary-600 dark:text-primary-400 mt-0.5 font-medium">
                            {matchCount} of {totalCount} match
                        </p>
                    ) : totalCount > 0 ? (
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                            {totalCount} {totalCount === 1 ? 'bookmark' : 'bookmarks'}
                        </p>
                    ) : (
                        <p className="text-sm text-gray-400 dark:text-gray-500 mt-0.5">
                            Empty folder
                        </p>
                    )}
                </div>
            </div>
        </div>
    )
}
