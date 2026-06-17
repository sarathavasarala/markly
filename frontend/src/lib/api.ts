import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
  paramsSerializer: {
    indexes: null
  }
})

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api

export interface AuthUser {
  id: string
  email: string
  username: string
  user_metadata?: {
    full_name?: string | null
    name?: string | null
    avatar_url?: string | null
    picture?: string | null
  }
}

export const authApi = {
  me: () => api.get<{ user: AuthUser | null; is_authenticated: boolean }>('/auth/me'),
  logout: () => api.post<{ success: boolean }>('/auth/logout'),
  loginWithGoogle: () => {
    window.location.href = '/api/auth/google/login'
  },
}

// Bookmarks API
export interface Bookmark {
  id: string
  url: string
  domain: string
  original_title: string
  clean_title: string | null
  ai_summary: string | null
  raw_notes: string | null
  auto_tags: string[]
  favicon_url: string | null
  thumbnail_url: string | null
  content_type: string | null
  intent_type: string | null
  technical_level: string | null
  key_quotes: string[] | null
  created_at: string
  updated_at: string
  last_accessed_at: string | null
  access_count: number
  enrichment_status: 'pending' | 'processing' | 'completed' | 'failed'
  enrichment_error: string | null
  archive_status?: 'pending' | 'processing' | 'completed' | 'failed' | 'unavailable' | null
  archive_format?: 'markdown' | 'text' | null
  archive_error?: string | null
  archived_at?: string | null
  archive_word_count?: number | null
  archive_char_count?: number | null
  is_public: boolean
  folder_id: string | null
  suggested_folder_name: string | null
  is_saved_by_viewer?: boolean
}

export interface BookmarkArchive {
  bookmark_id: string
  url: string
  domain: string | null
  title: string
  archive_content: string | null
  archive_format: 'markdown' | 'text' | null
  archive_status: Bookmark['archive_status']
  archive_error: string | null
  archived_at: string | null
  archive_word_count: number | null
  archive_char_count: number | null
}

export interface BookmarkListResponse {
  bookmarks: Bookmark[]
  total: number
  page: number
  per_page: number
  pages: number
}

export const bookmarksApi = {
  create: (url: string, notes?: string, description?: string, extraData?: any) =>
    api.post<{ bookmark: Bookmark; already_exists?: boolean }>('/bookmarks', {
      url,
      notes,
      description,
      ...extraData,
    }),

  get: (id: string) => api.get<Bookmark>(`/bookmarks/${id}`),

  list: (params?: {
    page?: number
    per_page?: number
    domain?: string
    content_type?: string
    tag?: string[]
    status?: string
    sort?: string
    order?: 'asc' | 'desc'
    folder_id?: string
  }) => api.get<BookmarkListResponse>('/bookmarks', { params }),

  analyze: (url: string, notes?: string) =>
    api.post<any>('/bookmarks/analyze', { url, notes }),

  delete: (id: string) => api.delete(`/bookmarks/${id}`),
  update: (id: string, data: Partial<Bookmark>) => api.patch<Bookmark>(`/bookmarks/${id}`, data),
  trackAccess: (id: string) => api.post(`/bookmarks/${id}/access`),
  retry: (id: string) => api.post(`/bookmarks/${id}/retry`),
  savePublic: (id: string) => api.post<{ bookmark: Bookmark; already_exists?: boolean }>('/bookmarks/save-public', { bookmark_id: id }),
  getArchive: (id: string) => api.get<BookmarkArchive>(`/bookmarks/${id}/archive`),
  retryArchive: (id: string) => api.post(`/bookmarks/${id}/archive/retry`),
  deleteAccount: () => api.delete('/public/account'),
}

export interface Feed {
  id: string
  feed_url: string
  title: string | null
  site_url: string | null
  favicon_url: string | null
  last_fetched_at: string | null
  failure_count: number
  last_error: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  new_item_count?: number
}

export interface FeedItem {
  id: string
  feed_id: string
  guid: string
  url: string
  title: string
  author: string | null
  published_at: string | null
  summary: string | null
  content?: string | null
  content_format?: string | null
  status: 'new' | 'dismissed' | 'saved'
  bookmark_id: string | null
  first_seen_at: string
  updated_at: string
  feed_title: string | null
  feed_site_url: string | null
  feed_favicon_url: string | null
  bookmark_thumbnail_url?: string | null
}

export interface FeedRefreshResult {
  feeds_checked: number
  feeds_skipped: number
  feeds_failed: number
  feeds_unchanged: number
  items_added: number
}

export const feedsApi = {
  list: () => api.get<{ feeds: Feed[] }>('/feeds'),
  create: (url: string) => api.post<Feed>('/feeds', { url }),
  delete: (id: string) => api.delete(`/feeds/${id}`),
  refresh: (data?: { force?: boolean; stale_after_minutes?: number }) =>
    api.post<FeedRefreshResult>('/feeds/refresh', data || {}),
  inbox: (params?: { limit?: number; offset?: number; feed_id?: string }) =>
    api.get<{ items: FeedItem[]; total: number }>('/feeds/inbox', { params }),
  dismissItem: (id: string) => api.post(`/feeds/items/${id}/dismiss`),
  markItemSaved: (id: string, bookmarkId: string) =>
    api.post<FeedItem>(`/feeds/items/${id}/saved`, { bookmark_id: bookmarkId }),
  getItemContent: (id: string, params?: { fetch_clean?: boolean }) =>
    api.get<{ content: string | null; content_format: string | null }>(`/feeds/items/${id}/content`, { params }),
}

// Folders API
export interface Folder {
  id: string
  user_id: string
  name: string
  icon: string | null
  color: string | null
  created_at: string
  updated_at: string
  bookmark_count?: number
}

export const foldersApi = {
  list: () => api.get<Folder[]>('/folders'),
  create: (data: { name: string; icon?: string; color?: string }) =>
    api.post<Folder>('/folders', data),
  update: (id: string, data: Partial<Folder>) =>
    api.patch<Folder>(`/folders/${id}`, data),
  delete: (id: string) => api.delete(`/folders/${id}`),
}

// Search API
export interface SearchResult {
  query: string
  mode: 'keyword' | 'semantic'
  results: Bookmark[]
  count: number
}

export const searchApi = {
  search: (params: {
    q: string
    mode?: 'keyword' | 'semantic'
    limit?: number
    domain?: string
    content_type?: string
    tag?: string
  }) => api.get<SearchResult>('/search', { params }),
}

// Stats API
export const statsApi = {
  getTopTags: (limit?: number, folderId?: string | null) =>
    api.get<{ tags: { tag: string; count: number }[] }>('/stats/tags', {
      params: { limit, folder_id: folderId },
    }),
}

export const publicApi = {
  listSubscribers: (username: string) =>
    api.get<{ subscribers: { email: string; subscribed_at: string }[] }>(`/public/@${username}/subscribers`),
  getTags: (username: string, limit?: number) =>
    api.get<{ tags: { tag: string; count: number }[] }>(`/public/@${username}/tags`, { params: { limit } }),
  unsubscribe: (username: string, email?: string) =>
    api.post(`/public/@${username}/unsubscribe`, { email }),
  checkSubscription: (username: string) =>
    api.get<{ is_subscribed: boolean }>(`/public/@${username}/subscription/check`),
  deleteSubscriber: (username: string, subscriberEmail: string) =>
    api.delete(`/public/@${username}/subscribers/${subscriberEmail}`),
}

// Signal API
export interface SignalBrief {
  id: string
  user_id: string
  content: string
  title: string | null
  article_count: number | null
  created_at: string
}

export interface SignalSettings {
  taste_profile: string
  signal_candidate_limit: number | null
  signal_synthesis_limit: number | null
  signal_filter_prompt: string | null
  signal_planning_prompt: string | null
  signal_synthesis_prompt: string | null
  signal_planning_enabled?: boolean
  signal_humanizer_enabled?: boolean
  default_filter_prompt?: string
  default_planning_prompt?: string
  default_synthesis_prompt?: string
  default_synthesis_limit?: number
  signal_web_search_enabled?: boolean
}

export const signalApi = {
  getTasteProfile: () => api.get<SignalSettings>('/signal/taste-profile'),
  updateTasteProfile: (settings: Partial<SignalSettings>) =>
    api.put<{ success: boolean } & SignalSettings>('/signal/taste-profile', settings),
  listBriefs: () => api.get<{ briefs: SignalBrief[] }>('/signal/briefs'),
  generateBrief: () => api.post<SignalBrief | { success: boolean; reason: string; message: string }>('/signal/briefs'),
  generateBriefStream: () =>
    fetch(`${API_BASE_URL}/signal/briefs/generate`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    }),
  deleteBrief: (id: string) => api.delete<{ success: boolean }>(`/signal/briefs/${id}`),
}

export interface SignalCluster {
  id: string
  title: string
  summary: string | null
  topic_key: string | null
  status: 'active' | 'archived'
  article_count: number
  source_count: number
  first_seen_at: string
  last_seen_at: string
  last_report_generated_at: string | null
  created_at: string
  updated_at: string
  new_since_last_report?: number
  items?: FeedItem[]
  latest_report?: SignalClusterReport | null
}

export interface SignalClusterDetail extends SignalCluster {
  items: FeedItem[]
  latest_report: SignalClusterReport | null
}

export interface SignalClusterReport {
  id: string
  cluster_id: string
  title: string | null
  content: string
  article_count: number
  source_count: number
  generated_at: string
}

export const clustersApi = {
  list: () => api.get<{ clusters: SignalCluster[] }>('/clusters'),
  refresh: () => api.post<{ clusters: SignalCluster[]; created: number; updated: number; archived: number }>('/clusters/refresh'),
  get: (id: string) => api.get<SignalClusterDetail>(`/clusters/${id}`),
  listReports: (id: string) => api.get<{ reports: SignalClusterReport[] }>(`/clusters/${id}/reports`),
  generateReport: (id: string) => api.post<SignalClusterReport>(`/clusters/${id}/reports/generate`),
  delete: (id: string) => api.delete<{ success: boolean }>(`/clusters/${id}`),
}
