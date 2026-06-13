import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { useEffect } from 'react'
import {
  createMemoryRouter,
  RouterProvider,
  MemoryRouter,
  useLocation,
  useSearchParams,
} from 'react-router-dom'
import LegacyRadarRedirect from '../LegacyRadarRedirect'
import Sidebar from '../Sidebar'

// ─── store mocks ────────────────────────────────────────────────────────────

vi.mock('../../stores/folderStore', () => ({
  useFolderStore: () => ({
    folders: [],
    isLoading: false,
    selectedFolderId: null,
    setSelectedFolderId: vi.fn(),
    createFolder: vi.fn(),
    deleteFolder: vi.fn(),
    updateFolder: vi.fn(),
  }),
}))

vi.mock('../../stores/uiStore', () => ({
  useUIStore: () => ({
    isSidebarOpen: true,
    setIsSidebarOpen: vi.fn(),
    setBookmarksViewMode: vi.fn(),
    applyTheme: vi.fn(),
  }),
}))

// ─── icon mocks (jsdom has no SVG layout engine) ────────────────────────────

vi.mock('lucide-react', () => ({
  Folder: () => null,
  FolderPlus: () => null,
  Edit2: () => null,
  Trash2: () => null,
  LayoutGrid: () => null,
  Radio: () => null,
}))

// ─── helpers ────────────────────────────────────────────────────────────────

/** Renders the current pathname + search so tests can assert on the final URL. */
function LocationDisplay() {
  const { pathname, search } = useLocation()
  return <div data-testid="location">{pathname}{search}</div>
}

/** Minimal component that replicates Radar.tsx's tab normalisation logic. */
function TabNormalizationHarness() {
  const [searchParams, setSearchParams] = useSearchParams()
  const rawTab = searchParams.get('tab')
  const activeTab = ((rawTab === 'signal' ? 'brief' : rawTab) ?? 'queue')

  useEffect(() => {
    if (rawTab === 'signal') {
      setSearchParams(
        (prev) => { const n = new URLSearchParams(prev); n.set('tab', 'brief'); return n },
        { replace: true },
      )
    }
  }, [rawTab, setSearchParams])

  return <div data-testid="active-tab">{activeTab}</div>
}

function makeRouter(initialEntry: string) {
  return createMemoryRouter(
    [
      { path: '/radar', element: <LegacyRadarRedirect /> },
      { path: '/sources', element: <LocationDisplay /> },
    ],
    { initialEntries: [initialEntry] },
  )
}

afterEach(() => {
  vi.clearAllMocks()
})

// ─── LegacyRadarRedirect ────────────────────────────────────────────────────

describe('LegacyRadarRedirect', () => {
  it('redirects /radar to /sources', () => {
    render(<RouterProvider router={makeRouter('/radar')} />)
    expect(screen.getByTestId('location').textContent).toBe('/sources')
  })

  it('translates /radar?tab=signal → /sources?tab=brief', () => {
    render(<RouterProvider router={makeRouter('/radar?tab=signal')} />)
    expect(screen.getByTestId('location').textContent).toBe('/sources?tab=brief')
  })

  it('preserves /radar?tab=queue as /sources?tab=queue', () => {
    render(<RouterProvider router={makeRouter('/radar?tab=queue')} />)
    expect(screen.getByTestId('location').textContent).toBe('/sources?tab=queue')
  })

  it('redirects /radar with no tab to /sources with no tab', () => {
    render(<RouterProvider router={makeRouter('/radar')} />)
    expect(screen.getByTestId('location').textContent).toBe('/sources')
  })
})

// ─── Sources page tab normalisation ─────────────────────────────────────────

describe('Sources page tab normalisation (Radar.tsx behaviour)', () => {
  function makeSourcesRouter(initialEntry: string) {
    return createMemoryRouter(
      [{ path: '/sources', element: <TabNormalizationHarness /> }],
      { initialEntries: [initialEntry] },
    )
  }

  it('shows brief tab immediately when arriving with tab=signal', () => {
    render(<RouterProvider router={makeSourcesRouter('/sources?tab=signal')} />)
    expect(screen.getByTestId('active-tab').textContent).toBe('brief')
  })

  it('replaces tab=signal in the URL with tab=brief (no history push)', async () => {
    const router = makeSourcesRouter('/sources?tab=signal')
    render(<RouterProvider router={router} />)
    await waitFor(() => {
      const { pathname, search } = router.state.location
      expect(pathname + search).toBe('/sources?tab=brief')
    })
  })

  it('leaves tab=brief unchanged', async () => {
    const router = makeSourcesRouter('/sources?tab=brief')
    render(<RouterProvider router={router} />)
    await waitFor(() => {
      const { pathname, search } = router.state.location
      expect(pathname + search).toBe('/sources?tab=brief')
    })
  })

  it('leaves tab=queue unchanged', async () => {
    const router = makeSourcesRouter('/sources?tab=queue')
    render(<RouterProvider router={router} />)
    await waitFor(() => {
      const { pathname, search } = router.state.location
      expect(pathname + search).toBe('/sources?tab=queue')
    })
  })

  it('defaults activeTab to queue when no tab param is given', () => {
    render(<RouterProvider router={makeSourcesRouter('/sources')} />)
    expect(screen.getByTestId('active-tab').textContent).toBe('queue')
  })
})

// ─── Sidebar ─────────────────────────────────────────────────────────────────

describe('Sidebar navigation', () => {
  it('renders the Sources link pointing to /sources', () => {
    render(
      <MemoryRouter initialEntries={['/sources']}>
        <Sidebar />
      </MemoryRouter>,
    )
    const link = screen.getByText('Sources').closest('a')
    expect(link).toHaveAttribute('href', '/sources')
  })

  it('marks the Sources link as active when the current path is /sources', () => {
    render(
      <MemoryRouter initialEntries={['/sources']}>
        <Sidebar />
      </MemoryRouter>,
    )
    const link = screen.getByText('Sources').closest('a')
    // Active items receive the standalone bg-white class (not hover:bg-white/60)
    expect(link?.className.split(' ')).toContain('bg-white')
  })

  it('does not mark Sources as active when on a different path', () => {
    render(
      <MemoryRouter initialEntries={['/bookmarks']}>
        <Sidebar />
      </MemoryRouter>,
    )
    const link = screen.getByText('Sources').closest('a')
    expect(link?.className.split(' ')).not.toContain('bg-white')
  })
})
