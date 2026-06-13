import { Navigate, useSearchParams } from 'react-router-dom'

/**
 * Redirects old /radar URLs to the canonical /sources path.
 * Translates the legacy tab=signal query value to tab=brief.
 * All other tab values are preserved as-is.
 */
export default function LegacyRadarRedirect() {
  const [searchParams] = useSearchParams()
  const tab = searchParams.get('tab')
  const mappedTab = tab === 'signal' ? 'brief' : tab
  const newSearch = mappedTab ? `?tab=${mappedTab}` : ''
  return <Navigate to={`/sources${newSearch}`} replace />
}
