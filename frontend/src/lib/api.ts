import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
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

// Auth API
export const authApi = {
  login: (secretPhrase: string) =>
    api.post<{ token: string; expires_at: string }>('/auth/login', {
      secret_phrase: secretPhrase,
    }),
  logout: () => api.post('/auth/logout'),
  verify: () => api.get<{ valid: boolean; expires_at?: string }>('/auth/verify'),
}

// Bookmarks API
export interface Bookmark {
  id: string
  url: string
  domain: string
  original_title: string
  clean_title: string
  ai_summary: string
  raw_notes: string | null
  auto_tags: string[]
  favicon_url: string
  thumbnail_url: string
  content_type: string
  intent_type: string
  technical_level: string
  key_quotes: string[]
  created_at: string
  updated_at: string
  last_accessed_at: string | null
  access_count: number
  enrichment_status: 'pending' | 'processing' | 'completed' | 'failed'
  enrichment_error: string | null
}

export interface BookmarkListResponse {
  bookmarks: Bookmark[]
  total: number
  page: number
  per_page: number
  pages: number
}

export const bookmarksApi = {
  create: (url: string, notes?: string, description?: string) =>
    api.post<Bookmark>('/bookmarks', { url, notes, description }),

  get: (id: string) => api.get<Bookmark>(`/bookmarks/${id}`),
  
  list: (params?: {
    page?: number
    per_page?: number
    domain?: string
    content_type?: string
    tag?: string
    status?: string
    sort?: string
    order?: 'asc' | 'desc'
  }) => api.get<BookmarkListResponse>('/bookmarks', { params }),
  
  delete: (id: string) => api.delete(`/bookmarks/${id}`),
  
  trackAccess: (id: string) => api.post(`/bookmarks/${id}/access`),
  
  retry: (id: string) => api.post(`/bookmarks/${id}/retry`),
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
  getTopDomains: (limit?: number) =>
    api.get<{ domains: { domain: string; count: number }[] }>('/stats/domains', {
      params: { limit },
    }),
  
  getTopTags: (limit?: number) =>
    api.get<{ tags: { tag: string; count: number }[] }>('/stats/tags', {
      params: { limit },
    }),
  
  getRecent: (limit?: number) =>
    api.get<{ bookmarks: Bookmark[] }>('/stats/recent', { params: { limit } }),
  
  getResurface: () =>
    api.get<{ suggestions: ResurfaceSuggestion[] }>('/stats/resurface'),
}
