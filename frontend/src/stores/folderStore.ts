import { create } from 'zustand'
import { Folder, foldersApi } from '../lib/api'

interface FolderState {
    folders: Folder[]
    isLoading: boolean
    error: string | null
    selectedFolderId: string | null; // null = Everything, UUID = Folder
    fetchFolders: () => Promise<void>
    setSelectedFolderId: (id: string | null) => void
    createFolder: (name: string, icon?: string, color?: string) => Promise<Folder>
    updateFolder: (id: string, data: Partial<Folder>) => Promise<void>
    deleteFolder: (id: string) => Promise<void>
}

export const useFolderStore = create<FolderState>((set) => ({
    folders: [],
    isLoading: false,
    error: null,
    selectedFolderId: null,

    fetchFolders: async () => {
        set({ isLoading: true, error: null })
        try {
            const res = await foldersApi.list()
            set({ folders: res.data })
        } catch (err: any) {
            set({ error: err.response?.data?.error || 'Failed to fetch folders' })
        } finally {
            set({ isLoading: false })
        }
    },

    setSelectedFolderId: (id) => set({ selectedFolderId: id }),

    createFolder: async (name, icon, color) => {
        try {
            const res = await foldersApi.create({ name, icon, color })
            set((state) => ({ folders: [...state.folders, res.data].sort((a, b) => a.name.localeCompare(b.name)) }))
            return res.data
        } catch (err: any) {
            const msg = err.response?.data?.error || 'Failed to create folder'
            set({ error: msg })
            throw new Error(msg)
        }
    },

    updateFolder: async (id, data) => {
        try {
            const res = await foldersApi.update(id, data)
            set((state) => ({
                folders: state.folders.map((f) => (f.id === id ? res.data : f)).sort((a, b) => a.name.localeCompare(b.name))
            }))
        } catch (err: any) {
            const msg = err.response?.data?.error || 'Failed to update folder'
            set({ error: msg })
            throw new Error(msg)
        }
    },

    deleteFolder: async (id) => {
        try {
            await foldersApi.delete(id)
            set((state) => ({
                folders: state.folders.filter((f) => f.id !== id),
                selectedFolderId: state.selectedFolderId === id ? null : state.selectedFolderId
            }))
        } catch (err: any) {
            const msg = err.response?.data?.error || 'Failed to delete folder'
            set({ error: msg })
            throw new Error(msg)
        }
    }
}))
