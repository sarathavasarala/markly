export interface ImportedBookmark {
  url: string
  title: string
  tags: string[]
  addedAt?: number
  enrich?: boolean
}

const slugify = (value: string) =>
  value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')

const normalizeTags = (parts: string[]) =>
  parts
    .map((p) => slugify(p))
    .filter(Boolean)

export const shouldEnrich = (url: string, title: string) => {
  try {
    const parsed = new URL(url)
    const path = parsed.pathname || ''
    return (
      path.split('/').filter(Boolean).length > 2 ||
      /blog|article|docs|tutorial|guide|post|case-study/i.test(url) ||
      (title && title.length > 40)
    )
  } catch {
    return false
  }
}

export function parseNetscapeHTML(html: string): ImportedBookmark[] {
  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')
  const results: ImportedBookmark[] = []

  const walkList = (dl: Element, folderStack: string[]) => {
    dl.querySelectorAll(':scope > dt').forEach((dt) => {
      const folder = dt.querySelector('h3')
      const link = dt.querySelector('a')

      if (folder) {
        const name = folder.textContent || ''
        const next = folder.nextElementSibling
        if (next && next.tagName.toLowerCase() === 'dl') {
          walkList(next, [...folderStack, name])
        }
      }

      if (link && link.getAttribute('href')) {
        const url = link.getAttribute('href') as string
        const title = (link.textContent || url).trim()
        const addDateRaw = link.getAttribute('add_date')
        const addedAt = addDateRaw ? Number(addDateRaw) * 1000 : undefined
        const tags = normalizeTags(folderStack)

        results.push({
          url,
          title,
          tags,
          addedAt,
          enrich: !!shouldEnrich(url, title),
        })
      }
    })
  }

  doc.querySelectorAll('dl').forEach((dl) => walkList(dl, []))
  return results
}

type FirefoxNode = {
  title?: string
  uri?: string
  dateAdded?: number
  children?: FirefoxNode[]
}

export function parseFirefoxJSON(raw: unknown): ImportedBookmark[] {
  if (!raw || typeof raw !== 'object') return []
  const root = raw as FirefoxNode
  const results: ImportedBookmark[] = []

  const walk = (node: FirefoxNode, folderStack: string[]) => {
    if (node.uri) {
      const url = node.uri
      const title = node.title || url
      const tags = normalizeTags(folderStack)
      const addedAt = node.dateAdded ? Math.floor(node.dateAdded / 1000) : undefined
      results.push({
        url,
        title,
        tags,
        addedAt,
        enrich: !!shouldEnrich(url, title),
      })
    }

    if (node.children && Array.isArray(node.children)) {
      const nextStack = node.title ? [...folderStack, node.title] : folderStack
      node.children.forEach((child) => walk(child, nextStack))
    }
  }

  walk(root, [])
  return results
}
