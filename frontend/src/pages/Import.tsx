import { useEffect, useMemo, useState } from 'react'
import { Upload, Loader2, CheckSquare, Sparkles, AlertCircle, Info, SkipForward, Trash2, StopCircle } from 'lucide-react'
import { ImportedBookmark, parseFirefoxJSON, parseNetscapeHTML, shouldEnrich } from '../lib/importParser'
import { useBookmarksStore } from '../stores/bookmarksStore'

export default function ImportPage() {
  const [bookmarks, setBookmarks] = useState<ImportedBookmark[]>([])
  const [selected, setSelected] = useState<Record<string, boolean>>({})
  const [useNanoModel, setUseNanoModel] = useState(true)
  const [isParsing, setIsParsing] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  const {
    startImport,
    importJobId,
    importJob,
    fetchImportJob,
    importCurrentItem,
    stopImportJob,
    deleteImportJob,
    skipImportItem,
    importItems,
  } = useBookmarksStore()

  const parsedCount = useMemo(() => bookmarks.length, [bookmarks])
  const selectedCount = useMemo(
    () => bookmarks.filter((b) => selected[b.url]).length,
    [bookmarks, selected]
  )

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null

    const poll = async () => {
      if (importJobId) {
        await fetchImportJob(importJobId)
      }
    }

    if (importJobId) {
      poll()
      interval = setInterval(poll, 3000)
    }

    return () => {
      if (interval) clearInterval(interval)
    }
  }, [importJobId, fetchImportJob])

  const handleFile = async (file: File) => {
    setIsParsing(true)
    setError('')
    try {
      const text = await file.text()
      let parsed: ImportedBookmark[] = []

      if (file.name.toLowerCase().endsWith('.html')) {
        parsed = parseNetscapeHTML(text)
      } else if (file.name.toLowerCase().endsWith('.json')) {
        parsed = parseFirefoxJSON(JSON.parse(text))
      }

      const unique = new Map<string, ImportedBookmark>()
      parsed.forEach((item) => {
        if (item.url && !unique.has(item.url)) {
          unique.set(item.url, {
            ...item,
            enrich: item.enrich ?? !!shouldEnrich(item.url, item.title),
          })
        }
      })

      const list = Array.from(unique.values())
      setBookmarks(list)
      setSelected(list.reduce<Record<string, boolean>>((acc, cur) => {
        acc[cur.url] = true
        return acc
      }, {}))
    } catch (parseError) {
      setError('Could not parse the file. Please use a browser bookmarks HTML or Firefox JSON export.')
    } finally {
      setIsParsing(false)
    }
  }

  const toggleSelect = (url: string) => {
    setSelected((prev) => ({ ...prev, [url]: !prev[url] }))
  }

  const toggleEnrich = (url: string) => {
    setBookmarks((prev) => prev.map((b) => (b.url === url ? { ...b, enrich: !b.enrich } : b)))
  }

  const selectAll = (value: boolean) => {
    setSelected(bookmarks.reduce<Record<string, boolean>>((acc, cur) => {
      acc[cur.url] = value
      return acc
    }, {}))
  }

  const handleSubmit = async () => {
    if (!selectedCount) {
      setError('Select at least one bookmark to import')
      return
    }
    setIsSubmitting(true)
    setError('')
    const payload = bookmarks
      .filter((b) => selected[b.url])
      .map((b) => ({ url: b.url, title: b.title, tags: b.tags, enrich: b.enrich }))

    const jobId = await startImport(payload, useNanoModel)
    if (!jobId) {
      setError('Failed to start import')
    }
    setIsSubmitting(false)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Import Bookmarks</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Upload your browser export (HTML or Firefox JSON). Folders become tags automatically.</p>
        </div>
      </div>

      {importJob && (
        <div className="flex items-center gap-3 p-3 bg-primary-50 dark:bg-primary-900/20 text-primary-800 dark:text-primary-200 rounded-lg border border-primary-100 dark:border-primary-800">
          <Info className="w-4 h-4" />
          <div className="flex-1 text-sm">
            Job {importJob.id.slice(0, 8)} — status: {importJob.status}. Imported {importJob.imported_count}, skipped {importJob.skipped_count}. Enrichment {importJob.enrich_completed}/{importJob.enqueue_enrich_count}.
          </div>
          <div className="flex items-center gap-2">
            {importJob.status === 'processing' && <Loader2 className="w-4 h-4 animate-spin text-primary-600" />}
            {importCurrentItem && (
              <button
                onClick={() => skipImportItem(importJob.id, importCurrentItem.id)}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-gray-100 dark:bg-gray-700 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
              >
                <SkipForward className="w-4 h-4" /> Skip current
              </button>
            )}
            <button
              onClick={() => stopImportJob(importJob.id)}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-orange-100 text-orange-700 rounded hover:bg-orange-200"
            >
              <StopCircle className="w-4 h-4" /> Stop
            </button>
            <button
              onClick={() => deleteImportJob(importJob.id, false)}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200"
            >
              <Trash2 className="w-4 h-4" /> Delete
            </button>
          </div>
        </div>
      )}

      {importCurrentItem && (
        <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 text-sm">
          <Info className="w-4 h-4 text-gray-500" />
          <div className="flex-1">
            <div className="font-medium text-gray-800 dark:text-gray-100">Processing</div>
            <div className="text-gray-600 dark:text-gray-300 truncate">{importCurrentItem.title || importCurrentItem.url}</div>
            <div className="text-xs text-gray-500 dark:text-gray-400">{importCurrentItem.url}</div>
          </div>
          <button
            onClick={() => {
              const jobId = importJob?.id || importJobId
              if (!jobId) return
              skipImportItem(jobId, importCurrentItem.id)
            }}
            className="flex items-center gap-1 px-3 py-1 text-xs bg-gray-100 dark:bg-gray-700 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
          >
            <SkipForward className="w-4 h-4" /> Skip
          </button>
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 p-3 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded-lg text-sm">
          <AlertCircle className="w-4 h-4 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <label className="flex items-center justify-center w-full border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg px-6 py-10 text-center cursor-pointer hover:border-primary-400 hover:bg-primary-50/50 dark:hover:bg-primary-900/10 transition">
        <div className="space-y-2">
          {isParsing ? <Loader2 className="w-6 h-6 animate-spin text-primary-600 mx-auto" /> : <Upload className="w-6 h-6 text-primary-600 mx-auto" />}
          <div className="text-sm text-gray-700 dark:text-gray-300">
            {isParsing ? 'Parsing bookmarks...' : 'Drop a bookmarks file or click to browse'}
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400">Accepts .html (Chrome/Safari) or .json (Firefox backup)</p>
        </div>
        <input
          type="file"
          accept=".html,.json,text/html,application/json"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) handleFile(file)
          }}
        />
      </label>

      {parsedCount > 0 ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-gray-700 dark:text-gray-300">
            <div className="flex items-center gap-2">
              <CheckSquare className="w-4 h-4" />
              <span>{selectedCount} of {parsedCount} selected</span>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={() => selectAll(true)} className="text-primary-600 hover:underline">Select all</button>
              <button onClick={() => selectAll(false)} className="text-gray-500 hover:underline">Deselect all</button>
              <label className="inline-flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={useNanoModel}
                  onChange={(e) => setUseNanoModel(e.target.checked)}
                />
                Use fast gpt-5-nano for enrichment
              </label>
            </div>
          </div>

          <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <div className="max-h-[70vh] overflow-y-auto overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-900/40 text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  <tr>
                    <th className="px-3 py-2 text-left">Import</th>
                    <th className="px-3 py-2 text-left">Enrich</th>
                    <th className="px-3 py-2 text-left">Title</th>
                    <th className="px-3 py-2 text-left">URL</th>
                    <th className="px-3 py-2 text-left">Tags</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-gray-700 text-sm">
                  {bookmarks.map((b) => (
                    <tr key={b.url} className="hover:bg-gray-50 dark:hover:bg-gray-800/40">
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={!!selected[b.url]}
                          onChange={() => toggleSelect(b.url)}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          checked={!!b.enrich}
                          onChange={() => toggleEnrich(b.url)}
                          disabled={!selected[b.url]}
                        />
                      </td>
                      <td className="px-3 py-2 font-medium text-gray-900 dark:text-white truncate max-w-[220px]" title={b.title}>
                        {b.title}
                      </td>
                      <td className="px-3 py-2 text-gray-500 dark:text-gray-400 truncate max-w-[260px]" title={b.url}>
                        {b.url}
                      </td>
                      <td className="px-3 py-2 text-gray-500 dark:text-gray-400">
                        {b.tags.join(', ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-2 p-3 bg-gray-50 dark:bg-gray-800/60 rounded-lg text-sm text-gray-600 dark:text-gray-300">
          <Sparkles className="w-4 h-4 text-primary-500" />
          <div>
            <div className="font-medium text-gray-800 dark:text-white">Tips</div>
            <ul className="list-disc list-inside text-sm space-y-1">
              <li>Export bookmarks from Chrome/Safari as HTML or Firefox as JSON (Backup).</li>
              <li>Folder names become tags automatically.</li>
              <li>We pre-select content-heavy links for enrichment; you can toggle per item.</li>
            </ul>
          </div>
        </div>
      )}

      <div className="flex justify-end gap-3 pt-2">
        <button
          onClick={handleSubmit}
          disabled={isSubmitting || selectedCount === 0}
          className="flex items-center gap-2 px-5 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
        >
          {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
          Import {selectedCount > 0 ? `(${selectedCount})` : ''}
        </button>
      </div>

      {importItems.length > 0 && (
        <div className="border border-gray-200 dark:border-gray-700 rounded-lg">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 text-sm text-gray-700 dark:text-gray-200">Recent items</div>
          <div className="max-h-[40vh] overflow-y-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 text-sm">
              <thead className="bg-gray-50 dark:bg-gray-900/40 text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                <tr>
                  <th className="px-3 py-2 text-left">Status</th>
                  <th className="px-3 py-2 text-left">Title</th>
                  <th className="px-3 py-2 text-left">URL</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {importItems.map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/40">
                    <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{item.status}</td>
                    <td className="px-3 py-2 text-gray-900 dark:text-white truncate max-w-[240px]" title={item.title}>{item.title || 'Untitled'}</td>
                    <td className="px-3 py-2 text-gray-500 dark:text-gray-400 truncate max-w-[260px]" title={item.url}>{item.url}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
