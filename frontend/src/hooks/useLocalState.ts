import { useState } from 'react'

/**
 * Persists demo-session values (current patient id, current journey
 * id, "acting as hospital X" selection) in the browser's own
 * localStorage. This is a real standalone app the user runs in their
 * own browser (not a claude.ai artifact sandbox), so normal browser
 * storage is fine here — it just keeps the demo usable across page
 * reloads without needing auth wired up yet (auth is Phase 10 /
 * section 19, added after the core workflow is functional).
 */
export function useLocalState(key, initialValue) {
  const [value, setValue] = useState(() => {
    try {
      const stored = window.localStorage.getItem(key)
      return stored !== null ? JSON.parse(stored) : initialValue
    } catch {
      return initialValue
    }
  })

  const setAndStore = (next) => {
    setValue(next)
    try {
      window.localStorage.setItem(key, JSON.stringify(next))
    } catch {
      // ignore storage failures in the demo
    }
  }

  return [value, setAndStore]
}
