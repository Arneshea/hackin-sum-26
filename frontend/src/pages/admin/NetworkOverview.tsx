import { useEffect, useState } from 'react'

import { api } from '../../services/api.js'
import { useLocalState } from '../../hooks/useLocalState.js'

export default function NetworkOverview() {
  const [token] = useLocalState('demo.adminToken', import.meta.env.VITE_DEMO_ADMIN_TOKEN || '')
  const [rows, setRows] = useState([])
  const [error, setError] = useState(null)

  async function refresh() {
    try {
      setRows(await api.simulatorNetworkOverview(token))
      setError(null)
    } catch {
      setError('Could not load network overview — check the demo admin token on the Simulator screen.')
    }
  }

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 4000)
    return () => clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  const byHospital = rows.reduce((acc, r) => {
    acc[r.name] = acc[r.name] || []
    if (r.resource_type) acc[r.name].push(r)
    return acc
  }, {})

  return (
    <div>
      <h2>Network Overview</h2>
      <p className="subtitle">All synthetic prototype hospital state, for the demo/admin audience only (section 6.6 / 41V).</p>
      {error && <div className="error-banner">{error}</div>}

      {Object.entries(byHospital).map(([name, resources]) => (
        <div className="panel" key={name}>
          <h3>{name}</h3>
          {(resources as any[]).map((r) => (
            <div className="list-row" key={r.resource_type}>
              <span>{r.resource_type}</span>
              <span style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <span className="mono">
                  {r.status}{r.available_count_optional != null ? ` (${r.available_count_optional}/${r.total_count_optional})` : ''}
                </span>
                <span className={`badge ${r.freshness === 'CURRENT' ? 'good' : r.freshness === 'STALE' ? 'bad' : 'neutral'}`}>{r.freshness}</span>
                <span className="mono">v{r.version}</span>
              </span>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
