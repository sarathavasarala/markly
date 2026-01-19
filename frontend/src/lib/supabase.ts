import { createClient } from '@supabase/supabase-js'

// Try to get config from window (injected by backend) or environment variables (local dev)
const config = (window as any).MARKLY_CONFIG || {}
const supabaseUrl = config.VITE_SUPABASE_URL || import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = config.VITE_SUPABASE_ANON_KEY || import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
    console.warn('Missing Supabase environment variables')
}

export const supabase = createClient(supabaseUrl || '', supabaseAnonKey || '')
