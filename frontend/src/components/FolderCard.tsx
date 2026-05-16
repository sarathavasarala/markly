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
            className="group relative w-full cursor-pointer overflow-hidden rounded-card bg-surface-light p-4 shadow-card ring-1 ring-white/60 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-card-hover dark:bg-surface-dark dark:ring-white/5"
        >
            <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-600 transition-colors group-hover:text-indigo-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:group-hover:text-indigo-300">
                    <FolderIcon className="h-5 w-5" />
                </div>

                <div className="min-w-0 flex-1">
                    <h3 className="truncate font-display text-lg font-normal leading-tight text-slate-950 transition-colors group-hover:text-indigo-700 dark:text-slate-50 dark:group-hover:text-indigo-300">
                        {folder.name}
                    </h3>
                    {isFiltering ? (
                        <p className="mt-0.5 text-sm font-medium text-slate-600 dark:text-slate-300">
                            {matchCount} of {totalCount} match
                        </p>
                    ) : totalCount > 0 ? (
                        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
                            {totalCount} {totalCount === 1 ? 'bookmark' : 'bookmarks'}
                        </p>
                    ) : (
                        <p className="mt-0.5 text-sm text-slate-400 dark:text-slate-500">
                            Empty folder
                        </p>
                    )}
                </div>
            </div>
        </div>
    )
}
