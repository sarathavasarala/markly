import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Mock Supabase environment variables
if (typeof process !== 'undefined') {
    process.env.VITE_SUPABASE_URL = 'https://test.supabase.co'
    process.env.VITE_SUPABASE_ANON_KEY = 'test-anon-key'
}

// Alternatively, for Vitest's environment
if (typeof globalThis !== 'undefined') {
    // @ts-ignore
    globalThis.vi_env = {
        VITE_SUPABASE_URL: 'https://test.supabase.co',
        VITE_SUPABASE_ANON_KEY: 'test-anon-key',
    }
}

// Mock the import.meta.env directly for tests if needed via vi.stubEnv
import { vi } from 'vitest'
vi.stubEnv('VITE_SUPABASE_URL', 'https://test.supabase.co')
vi.stubEnv('VITE_SUPABASE_ANON_KEY', 'test-anon-key')

// Runs a cleanup after each test case (e.g. clearing jsdom)
afterEach(() => {
    cleanup()
})
