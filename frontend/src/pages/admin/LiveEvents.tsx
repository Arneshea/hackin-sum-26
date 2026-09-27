import { useEffect, useState } from 'react'

import { subscribeToTable } from '../../services/realtime.js'
import { isRealtimeConfigured } from '../../services/supabaseClient.js'

export default function LiveEvents() {
  const [events, setEvents] = useState([])
  const [status, setStatus] = useState('UNCONFIGURED')

  useEffect(() => {
    const unsubscribe = subscribeToTable({
      table: 'hospital_state_events',
      onChange: (payload) => {
        setEvents((prev) => [payload, ...prev].slice(0, 30))
      },
      onStatusChange: setStatus,
    })
    return unsubscribe
  }, [])

  return (
    <div>
      <h2>Live Events</h2>
      <p className="subtitle">
        Raw <span className="mono">hospital_state_events</span> change stream via Supabase Realtime
        (section 8) — a change-notification mechanism, not the source of truth; the database remains
        authoritative.
      </p>

      {!isRealtimeConfigured() && (
        <div className="warning-banner">
          Supabase Realtime is not configured (VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY). Set these
          in frontend/.env to see a live feed here.
        </div>
      )}
      {isRealtimeConfigured() && status !== 'SUBSCRIBED' && (
        <div className="warning-banner">Connection status: {status}</div>
      )}

      <div className="panel">
        {events.length === 0 && <p className="footnote">No events yet — trigger one from the Hospital State Simulator.</p>}
        {events.map((e, i) => (
          <div className="list-row" key={i}>
            <span className="mono">{e.eventType} on {e.table}</span>
            <span className="mono">{JSON.stringify(e.new || e.record || {}).slice(0, 120)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
