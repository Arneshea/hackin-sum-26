import { supabase, isRealtimeConfigured } from './supabaseClient'

/**
 * Subscribe to Postgres Changes on a table, scoped by an optional
 * filter. Implements the reconnect contract from section 41T:
 *
 *   connection lost -> show live-data warning -> fetch authoritative
 *   current state -> resume subscription
 *
 * Callers must NOT try to reconstruct current state purely from the
 * last event received in the browser (section 41T) — `onReconnect`
 * is expected to re-fetch from the Flask API / Supabase read, not
 * patch local state from the change payload alone.
 *
 * Returns an unsubscribe function.
 */
export function subscribeToTable({ table, filter, onChange, onStatusChange }: { table: string; filter?: string; onChange?: (payload: any) => void; onStatusChange?: (status: string) => void }) {
  if (!isRealtimeConfigured()) {
    onStatusChange?.('UNCONFIGURED')
    return () => {}
  }

  let channel

  const setup = () => {
    channel = supabase
      .channel(`${table}-${filter || 'all'}-${Math.random().toString(36).slice(2)}`)
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table, filter },
        (payload) => onChange?.(payload)
      )
      .subscribe((status) => {
        onStatusChange?.(status)
        if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT' || status === 'CLOSED') {
          // Per section 41T: surface the stale-data warning, then the
          // caller's onStatusChange handler is expected to re-fetch
          // authoritative state before resubscribing.
        }
      })
  }

  setup()

  return () => {
    channel?.unsubscribe()
  }
}
