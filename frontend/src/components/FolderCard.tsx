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
            className="group relative w-full cursor-pointer overflow-hidden rounded-card bg-surface-light p-5 shadow-card ring-1 ring-white/60 transition-all duration-300 hover:-translate-y-1 hover:shadow-card-hover dark:bg-surface-dark dark:ring-white/10"
        >
            <div className="flex items-center gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-[1rem] bg-[#eef1ee] text-slate-650 transition-colors group-hover:bg-slate-900 group-hover:text-white dark:bg-slate-900 dark:text-slate-350 dark:group-hover:bg-slate-100 dark:group-hover:text-slate-950">
                    <FolderIcon className="h-6 w-6" />
                </div>

                <div className="min-w-0 flex-1">
                    <h3 className="truncate font-display text-xl font-normal leading-tight text-slate-950 transition-colors group-hover:text-slate-800 dark:text-slate-50 dark:group-hover:text-slate-200">
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
