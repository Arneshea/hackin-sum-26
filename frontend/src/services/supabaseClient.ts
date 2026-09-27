import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

// Client-safe credentials only (anon key). All writes that matter for
// the coordination workflow go through the Flask API so the atomic
// transitions in 002_atomic_transitions.sql are always used; this
// client is for read access under RLS and for Realtime subscriptions
// (section 8, "Supabase Realtime is a change-notification mechanism,
// not the source of truth").
export const supabase = url && anonKey ? createClient(url, anonKey) : null

export function isRealtimeConfigured() {
  return supabase !== null
}
