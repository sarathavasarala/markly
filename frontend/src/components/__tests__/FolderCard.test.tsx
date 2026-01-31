import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'
import FolderCard from '../FolderCard'
import { Folder } from '../../lib/api'

// Mock lucide-react
vi.mock('lucide-react', () => ({
    Folder: () => <div data-testid="folder-icon" />,
}))

const mockFolder: Folder = {
    id: 'folder-1',
    user_id: 'user-1',
    name: 'Learning Resources',
    icon: null,
    color: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    bookmark_count: 5,
}

describe('FolderCard', () => {
    it('renders folder name', () => {
        render(<FolderCard folder={mockFolder} onClick={() => { }} />)
        expect(screen.getByText('Learning Resources')).toBeInTheDocument()
    })

    it('renders bookmark count when present', () => {
        render(<FolderCard folder={mockFolder} onClick={() => { }} />)
        expect(screen.getByText('5 bookmarks')).toBeInTheDocument()
    })

    it('renders singular bookmark text for count of 1', () => {
        const singleBookmarkFolder = { ...mockFolder, bookmark_count: 1 }
        render(<FolderCard folder={singleBookmarkFolder} onClick={() => { }} />)
        expect(screen.getByText('1 bookmark')).toBeInTheDocument()
    })

    it('shows empty folder message when count is 0', () => {
        const emptyFolder = { ...mockFolder, bookmark_count: 0 }
        render(<FolderCard folder={emptyFolder} onClick={() => { }} />)
        expect(screen.getByText('Empty folder')).toBeInTheDocument()
    })

    it('shows empty folder message when count is undefined', () => {
        const noCountFolder = { ...mockFolder, bookmark_count: undefined }
        render(<FolderCard folder={noCountFolder} onClick={() => { }} />)
        expect(screen.getByText('Empty folder')).toBeInTheDocument()
    })

    it('calls onClick when clicked', () => {
        const handleClick = vi.fn()
        render(<FolderCard folder={mockFolder} onClick={handleClick} />)

        const card = screen.getByRole('button')
        fireEvent.click(card)

        expect(handleClick).toHaveBeenCalledTimes(1)
    })

    it('calls onClick when Enter key is pressed', () => {
        const handleClick = vi.fn()
        render(<FolderCard folder={mockFolder} onClick={handleClick} />)

        const card = screen.getByRole('button')
        fireEvent.keyDown(card, { key: 'Enter' })

        expect(handleClick).toHaveBeenCalledTimes(1)
    })

    it('renders folder icon', () => {
        render(<FolderCard folder={mockFolder} onClick={() => { }} />)
        expect(screen.getByTestId('folder-icon')).toBeInTheDocument()
    })
})
