import { useState, useEffect, ReactNode, useMemo, useRef } from 'react'

interface MasonryGridProps<T> {
    items: T[]
    renderItem: (item: T) => ReactNode
    gap?: number
    columnClasses?: string
    // Breakpoints map container width to number of columns
    breakpoints?: { [width: number]: number }
}

/**
 * A robust masonry grid that distributes items into columns by tracking column heights.
 * This preserves semi-row-wise ordering (Today at top) while ensuring balanced columns.
 * 
 * Updated: Responsive to container width via ResizeObserver.
 */
export default function MasonryGrid<T>({
    items,
    renderItem,
    gap = 24,
    columnClasses = "",
    breakpoints = { 0: 1, 640: 2, 1024: 3, 1280: 4 }
}: MasonryGridProps<T>) {
    const [columns, setColumns] = useState(1)
    const containerRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (!containerRef.current) return

        const updateColumns = (width: number) => {
            const sortedBreaks = Object.keys(breakpoints).map(Number).sort((a, b) => b - a)
            const currentBreak = sortedBreaks.find(b => width >= b) || 0
            setColumns(breakpoints[currentBreak] || 1)
        }

        const resizeObserver = new ResizeObserver((entries) => {
            for (const entry of entries) {
                if (entry.contentBoxSize) {
                    // Use contentBoxSize if available
                    const contentBoxSize = entry.contentBoxSize[0]
                    updateColumns(contentBoxSize.inlineSize)
                } else {
                    // Fallback to contentRect
                    updateColumns(entry.contentRect.width)
                }
            }
        })

        resizeObserver.observe(containerRef.current)

        // Initial call
        updateColumns(containerRef.current.offsetWidth)

        return () => resizeObserver.disconnect()
    }, [breakpoints])

    // Simple height heuristic for better balancing
    const estimateHeight = (item: any) => {
        let height = 200 // Base card height
        if (item.thumbnail_url) height += 160
        if (item.ai_summary) height += Math.min(item.ai_summary.length * 0.4, 120)
        if (item.auto_tags) height += (Math.min(item.auto_tags.length, 3) / 3) * 20
        return height
    }

    // Balanced distribution logic
    const columnsData = useMemo(() => {
        const cols: T[][] = Array.from({ length: columns }, () => [])
        const heights = new Array(columns).fill(0)

        items.forEach((item, index) => {
            let targetCol = 0

            if (index < columns) {
                // Place first row strictly left-to-right
                targetCol = index
            } else {
                // Find shortest column for subsequent items to balance the bottom
                let minHeight = heights[0]
                for (let i = 1; i < columns; i++) {
                    if (heights[i] < minHeight) {
                        minHeight = heights[i]
                        targetCol = i
                    }
                }
            }

            cols[targetCol].push(item)
            heights[targetCol] += estimateHeight(item) + gap
        })

        return cols
    }, [items, columns, gap])

    return (
        <div
            ref={containerRef}
            className="flex w-full justify-center transition-all duration-300"
            style={{ gap: `${gap}px` }}
        >
            {columnsData.map((colItems, colIndex) => (
                <div
                    key={colIndex}
                    className={`flex flex-col ${columnClasses}`}
                    style={{
                        gap: `${gap}px`,
                        flex: `1 1 0%`,
                        minWidth: 0,
                        maxWidth: columns === 1 ? '100%' : `${100 / columns}%`
                    }}
                >
                    {colItems.map((item, itemIndex) => (
                        <div key={(item as any).id || itemIndex} className="w-full animate-in fade-in slide-in-from-bottom-2 duration-500">
                            {renderItem(item)}
                        </div>
                    ))}
                </div>
            ))}
        </div>
    )
}
