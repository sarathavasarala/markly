import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  paramsSerializer: {
    indexes: null
  }
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('markly_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('markly_token')
      localStorage.removeItem('markly_expires')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api

// Auth API removed - using Supabase Auth directly

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
  is_public: boolean
  folder_id: string | null
  suggested_folder_name: string | null
  is_saved_by_viewer?: boolean
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
  deleteAccount: () => api.delete('/public/account'),
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

  getHistory: (limit?: number) =>
    api.get<{ history: { query: string; results_count: number; created_at: string }[] }>(
      '/search/history',
      { params: { limit } }
    ),
}

// Stats API
export interface ResurfaceSuggestion extends Bookmark {
  resurface_reason: string
}

export const statsApi = {
  getTopTags: (limit?: number, folderId?: string | null) =>
    api.get<{ tags: { tag: string; count: number }[] }>('/stats/tags', {
      params: { limit, folder_id: folderId },
    }),

  getResurface: () =>
    api.get<{ suggestions: ResurfaceSuggestion[] }>('/stats/resurface'),
}

export const publicApi = {
  listSubscribers: (username: string) =>
    api.get<{ subscribers: { email: string; subscribed_at: string }[] }>(`/public/@${username}/subscribers`),
  unsubscribe: (username: string, email?: string) =>
    api.post(`/public/@${username}/unsubscribe`, { email }),
  checkSubscription: (username: string) =>
    api.get<{ is_subscribed: boolean }>(`/public/@${username}/subscription/check`),
  deleteSubscriber: (username: string, subscriberEmail: string) =>
    api.delete(`/public/@${username}/subscribers/${subscriberEmail}`),
}
