import { render, screen } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'
import BookmarkCard from '../BookmarkCard'
import { Bookmark } from '../../lib/api'

// Mock the stores
vi.mock('../../stores/bookmarksStore', () => ({
    useBookmarksStore: () => ({
        trackAccess: vi.fn(),
        retryEnrichment: vi.fn(),
        deleteBookmark: vi.fn().mockResolvedValue({}),
    }),
}))

vi.mock('../../stores/uiStore', () => ({
    useUIStore: vi.fn((selector) => selector({
        setEditingBookmark: vi.fn(),
    })),
}))

// Mock lucide-react
vi.mock('lucide-react', () => ({
    ExternalLink: () => <div data-testid="external-link-icon" />,
    Copy: () => <div data-testid="copy-icon" />,
    Loader2: () => <div data-testid="loader-icon" />,
    AlertCircle: () => <div data-testid="alert-icon" />,
    RefreshCw: () => <div data-testid="refresh-icon" />,
    MoreVertical: () => <div data-testid="more-icon" />,
    Trash2: () => <div data-testid="trash-icon" />,
    Edit2: () => <div data-testid="edit-icon" />,
    Eye: () => <div data-testid="eye-icon" />,
    EyeOff: () => <div data-testid="eye-off-icon" />,
    Plus: () => <div data-testid="plus-icon" />,
    Check: () => <div data-testid="check-icon" />,
    BookMarked: () => <div data-testid="bookmarked-icon" />,
}))

const mockBookmark: Bookmark = {
    id: '1',
    url: 'https://example.com',
    domain: 'example.com',
    original_title: 'Original Title',
    clean_title: 'Clean Title',
    ai_summary: 'Test Summary',
    raw_notes: 'Test Notes',
    auto_tags: ['tag1', 'tag2'],
    favicon_url: 'https://example.com/favicon.ico',
    thumbnail_url: 'https://example.com/thumb.jpg',
    content_type: 'article',
    intent_type: 'learn',
    technical_level: 'beginner',
    key_quotes: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    last_accessed_at: null,
    access_count: 0,
    is_public: true,
    enrichment_status: 'completed',
    enrichment_error: null,
}

describe('BookmarkCard', () => {
    it('renders the bookmark title and summary', () => {
        render(<BookmarkCard bookmark={mockBookmark} />)

        expect(screen.getByText('Clean Title')).toBeInTheDocument()
        expect(screen.getByText('Test Summary')).toBeInTheDocument()
        expect(screen.getByText('example.com')).toBeInTheDocument()
    })

    it('renders tags', () => {
        render(<BookmarkCard bookmark={mockBookmark} />)

        expect(screen.getByText('tag1')).toBeInTheDocument()
        expect(screen.getByText('tag2')).toBeInTheDocument()
    })

    it('shows enrichment status when pending', () => {
        const pendingBookmark = { ...mockBookmark, enrichment_status: 'pending' as const }
        render(<BookmarkCard bookmark={pendingBookmark} />)

        expect(screen.getByText('Analyzing content...')).toBeInTheDocument()
    })
})
