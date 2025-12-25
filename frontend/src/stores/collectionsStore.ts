import { create } from 'zustand'
import { collectionsApi, Collection, CollectionProposal } from '../lib/api'

interface CollectionsState {
  collections: Collection[]
  proposals: CollectionProposal[]
  isLoading: boolean
  isGenerating: boolean
  error: string | null
  
  // Actions
  fetchCollections: () => Promise<void>
  createCollection: (data: { name: string; description?: string; icon?: string; color?: string }) => Promise<Collection | null>
  updateCollection: (id: string, data: { name?: string; description?: string; icon?: string; color?: string }) => Promise<void>
  deleteCollection: (id: string) => Promise<void>
  removeBookmarkFromCollection: (collectionId: string, bookmarkId: string) => Promise<void>
  generateProposals: () => Promise<void>
  acceptProposals: (proposals: CollectionProposal[]) => Promise<void>
  clearProposals: () => void
}

export const useCollectionsStore = create<CollectionsState>((set) => ({
  collections: [],
  proposals: [],
  isLoading: false,
  isGenerating: false,
  error: null,
  
  fetchCollections: async () => {
    set({ isLoading: true, error: null })
    
    try {
      const response = await collectionsApi.list()
      set({
        collections: response.data.collections,
        isLoading: false,
      })
    } catch (error: unknown) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to fetch collections',
      })
    }
  },
  
  createCollection: async (data) => {
    try {
      const response = await collectionsApi.create(data)
      const newCollection = response.data
      
      set((state) => ({
        collections: [newCollection, ...state.collections],
      }))
      
      return newCollection
    } catch (error: unknown) {
      set({
        error: error instanceof Error ? error.message : 'Failed to create collection',
      })
      return null
    }
  },
  
  updateCollection: async (id, data) => {
    try {
      const response = await collectionsApi.update(id, data)
      const updated = response.data
      
      set((state) => ({
        collections: state.collections.map((c) =>
          c.id === id ? { ...c, ...updated } : c
        ),
      }))
    } catch (error: unknown) {
      set({
        error: error instanceof Error ? error.message : 'Failed to update collection',
      })
    }
  },
  
  deleteCollection: async (id) => {
    try {
      await collectionsApi.delete(id)
      
      set((state) => ({
        collections: state.collections.filter((c) => c.id !== id),
      }))
    } catch (error: unknown) {
      set({
        error: error instanceof Error ? error.message : 'Failed to delete collection',
      })
    }
  },
  
  removeBookmarkFromCollection: async (collectionId, bookmarkId) => {
    try {
      await collectionsApi.removeBookmark(collectionId, bookmarkId)
      
      // Update collection bookmark count
      set((state) => ({
        collections: state.collections.map((c) =>
          c.id === collectionId
            ? { ...c, bookmark_count: Math.max(0, (c.bookmark_count || 0) - 1) }
            : c
        ),
      }))
    } catch (error: unknown) {
      set({
        error: error instanceof Error ? error.message : 'Failed to remove bookmark',
      })
    }
  },
  
  generateProposals: async () => {
    set({ isGenerating: true, error: null })
    
    try {
      const response = await collectionsApi.generateProposals()
      set({
        proposals: response.data.proposals,
        isGenerating: false,
      })
    } catch (error: unknown) {
      set({
        isGenerating: false,
        error: error instanceof Error ? error.message : 'Failed to generate proposals',
      })
    }
  },
  
  acceptProposals: async (proposals) => {
    try {
      const response = await collectionsApi.acceptProposals(proposals)
      
      set((state) => ({
        collections: [...response.data.collections, ...state.collections],
        proposals: [],
      }))
    } catch (error: unknown) {
      set({
        error: error instanceof Error ? error.message : 'Failed to accept proposals',
      })
    }
  },
  
  clearProposals: () => {
    set({ proposals: [] })
  },
}))
