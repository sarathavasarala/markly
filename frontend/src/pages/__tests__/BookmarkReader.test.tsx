import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import BookmarkReader from '../BookmarkReader'
import { bookmarksApi } from '../../lib/api'

// Mock react-router-dom
const mockNavigate = vi.fn()
vi.mock('react-router-dom', () => ({
  useParams: () => ({ id: 'bookmark-123' }),
  useNavigate: () => mockNavigate,
}))

// Mock bookmarksApi
vi.mock('../../lib/api', () => ({
  bookmarksApi: {
    getArchive: vi.fn(),
    updateArchive: vi.fn(),
    retryArchive: vi.fn(),
  },
}))

describe('BookmarkReader', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading state initially and then completed archive content', async () => {
    vi.mocked(bookmarksApi.getArchive).mockResolvedValueOnce({
      data: {
        bookmark_id: 'bookmark-123',
        url: 'https://example.com/article',
        domain: 'example.com',
        title: 'Interesting Tech Article',
        archive_content: '# Heading 1\n\nThis is the body content.',
        archive_format: 'markdown',
        archive_status: 'completed',
        archive_error: null,
        archived_at: '2026-06-01T12:00:00Z',
        archive_word_count: 7,
        archive_char_count: 38,
      },
    } as any)

    render(<BookmarkReader />)

    expect(screen.getByText(/loading saved copy/i)).toBeDefined()

    await waitFor(() => {
      expect(screen.getByText('Interesting Tech Article')).toBeDefined()
      expect(screen.getByText('This is the body content.')).toBeDefined()
      expect(screen.getByText(/edit copy/i)).toBeDefined()
    })
  })

  it('allows switching to edit mode, typing new content, and saving changes', async () => {
    vi.mocked(bookmarksApi.getArchive).mockResolvedValueOnce({
      data: {
        bookmark_id: 'bookmark-123',
        url: 'https://example.com/article',
        domain: 'example.com',
        title: 'Original Title',
        archive_content: 'Original content with bad formatting',
        archive_format: 'markdown',
        archive_status: 'completed',
        archive_error: null,
        archived_at: '2026-06-01T12:00:00Z',
        archive_word_count: 5,
        archive_char_count: 36,
      },
    } as any)

    vi.mocked(bookmarksApi.updateArchive).mockResolvedValueOnce({
      data: {
        bookmark_id: 'bookmark-123',
        url: 'https://example.com/article',
        domain: 'example.com',
        title: 'Original Title',
        archive_content: '## Clean Summary\n\n- Key point 1\n- Key point 2',
        archive_format: 'markdown',
        archive_status: 'completed',
        archive_error: null,
        archived_at: '2026-06-01T12:00:00Z',
        archive_word_count: 8,
        archive_char_count: 45,
      },
    } as any)

    render(<BookmarkReader />)

    await waitFor(() => {
      expect(screen.getByText(/edit copy/i)).toBeDefined()
    })

    // Click Edit copy
    fireEvent.click(screen.getByText(/edit copy/i))

    // Verify editor is visible
    const textarea = screen.getByPlaceholderText(/paste your formatted article copy/i)
    expect(textarea).toBeDefined()
    expect((textarea as HTMLTextAreaElement).value).toBe('Original content with bad formatting')

    // Change content
    fireEvent.change(textarea, {
      target: { value: '## Clean Summary\n\n- Key point 1\n- Key point 2' },
    })

    // Click preview tab
    fireEvent.click(screen.getByText(/preview/i))
    expect(screen.getByText('Clean Summary')).toBeDefined()
    expect(screen.getByText('Key point 1')).toBeDefined()

    // Save changes
    fireEvent.click(screen.getByText(/save changes/i))

    await waitFor(() => {
      expect(bookmarksApi.updateArchive).toHaveBeenCalledWith('bookmark-123', {
        archive_content: '## Clean Summary\n\n- Key point 1\n- Key point 2',
        archive_format: 'markdown',
      })
      expect(screen.getByText(/offline article copy updated and saved successfully/i)).toBeDefined()
    })
  })

  it('renders failed state with manual paste button', async () => {
    vi.mocked(bookmarksApi.getArchive).mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          bookmark_id: 'bookmark-123',
          url: 'https://example.com/blocked',
          domain: 'example.com',
          title: 'Blocked Article',
          archive_content: null,
          archive_format: null,
          archive_status: 'failed',
          archive_error: 'Page blocked by paywall',
          archived_at: null,
          archive_word_count: null,
          archive_char_count: null,
        },
      },
    })

    render(<BookmarkReader />)

    await waitFor(() => {
      expect(screen.getByText(/saved copy unavailable/i)).toBeDefined()
      expect(screen.getByText(/page blocked by paywall/i)).toBeDefined()
      expect(screen.getByText(/paste article \/ summary/i)).toBeDefined()
    })

    // Clicking paste button opens editor
    fireEvent.click(screen.getByText(/paste article \/ summary/i))
    expect(screen.getByPlaceholderText(/paste your formatted article copy/i)).toBeDefined()
  })
})
