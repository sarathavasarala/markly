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
        <div className="bg-white dark:bg-gray-900 py-5 px-6 rounded-2xl border border-gray-100 dark:border-gray-800 shadow-sm transition-colors duration-300">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <h2 className="text-sm font-bold tracking-wider text-gray-400">{title}</h2>
                    {selectedTags.length > 0 && onClearFilters && (
                        <button
                            onClick={onClearFilters}
                            className="text-[10px] font-black uppercase tracking-widest text-primary-600 hover:text-primary-700 transition-colors flex items-center gap-1"
                        >
                            Clear <X className="w-3 h-3" />
                        </button>
                    )}
                </div>
                {!isLoading && tags.length > limit && (
                    <button
                        onClick={() => setShowAll(!showAll)}
                        className="text-xs font-medium text-primary-600 dark:text-primary-400 hover:text-primary-700 dark:hover:text-primary-300 transition-colors"
                    >
                        {showAll ? 'Show less' : `Show all ${tags.length}`}
                    </button>
                )}
            </div>
            <div className="flex flex-wrap gap-2">
                {isLoading ? (
                    [1, 2, 3, 4, 5, 6].map(i => (
                        <div key={i} className="w-20 h-8 bg-gray-100 dark:bg-gray-800 rounded-full animate-pulse" />
                    ))
                ) : tags.length === 0 ? (
                    <p className="text-sm text-gray-400">No topics yet</p>
                ) : (
                    displayedTags.map(({ tag, count }) => (
                        <button
                            key={tag}
                            onClick={() => onTagClick(tag)}
                            className={`px-3 py-1.5 rounded-full text-xs font-bold border transition-all ${selectedTags.includes(tag)
                                ? 'bg-primary-600 border-primary-600 text-white shadow-md scale-[1.02]'
                                : 'bg-primary-50 dark:bg-primary-900/10 border-primary-100 dark:border-primary-900/30 text-primary-700 dark:text-primary-400 hover:border-primary-300 dark:hover:border-primary-800'
                                }`}
                        >
                            #{tag} <span className={`ml-1 ${selectedTags.includes(tag) ? 'text-primary-200' : 'text-primary-400'}`}>{count}</span>
                        </button>
                    ))
                )}
            </div>
        </div>
    )
}
