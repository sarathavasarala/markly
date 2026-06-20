import { useState } from 'react'
import { X } from 'lucide-react'

interface Tag {
    tag: string
    count: number
}

interface TopicsBoxProps {
    tags: Tag[]
    selectedTags: string[]
    isLoading?: boolean
    onTagClick: (tag: string) => void
    onClearFilters?: () => void
    title?: string
    limit?: number
}

export default function TopicsBox({
    tags,
    selectedTags,
    isLoading = false,
    onTagClick,
    onClearFilters,
    title = "Topics",
    limit = 8
}: TopicsBoxProps) {
    const [showAll, setShowAll] = useState(false)

    const displayedTags = showAll ? tags : tags.slice(0, limit)

    return (
        <div className="rounded-card bg-surface-light px-6 py-5 shadow-card ring-1 ring-white/60 transition-colors duration-300 dark:bg-surface-dark dark:ring-white/10">
            <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <h2 className="text-sm font-medium text-slate-500 dark:text-slate-400">{title}</h2>
                    {selectedTags.length > 0 && onClearFilters && (
                        <button
                            onClick={onClearFilters}
                            className="flex items-center gap-1 text-xs font-medium text-slate-700 transition-colors hover:text-slate-900 dark:text-slate-350 dark:hover:text-slate-200"
                        >
                            Clear <X className="h-3 w-3" />
                        </button>
                    )}
                </div>
                {!isLoading && tags.length > limit && (
                    <button
                        onClick={() => setShowAll(!showAll)}
                        className="text-xs font-medium text-slate-500 transition-colors hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
                    >
                        {showAll ? 'Show less' : `Show all ${tags.length}`}
                    </button>
                )}
            </div>
            <div className="flex flex-wrap gap-2">
                {isLoading ? (
                    [1, 2, 3, 4, 5, 6].map(i => (
                        <div key={i} className="h-7 w-20 animate-pulse rounded-full bg-slate-200/70 dark:bg-slate-800/70" />
                    ))
                ) : tags.length === 0 ? (
                    <p className="text-sm text-slate-400 dark:text-slate-500">No topics yet</p>
                ) : (
                    displayedTags.map(({ tag, count }) => {
                        const selected = selectedTags.includes(tag)
                        return (
                            <button
                                key={tag}
                                onClick={() => onTagClick(tag)}
                                className={`rounded-full px-3 py-1 text-xs font-medium lowercase transition-all ${selected
                                    ? 'bg-slate-900 text-white ring-1 ring-slate-900 dark:bg-slate-100 dark:text-slate-950 dark:ring-slate-100'
                                    : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:text-slate-900 hover:ring-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700 dark:hover:text-slate-100'
                                    }`}
                            >
                                {tag}
                                <span className={`ml-1.5 tabular-nums ${selected ? 'opacity-60' : 'text-slate-400 dark:text-slate-500'}`}>{count}</span>
                            </button>
                        )
                    })
                )}
            </div>
        </div>
    )
}
