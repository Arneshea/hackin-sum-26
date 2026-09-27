import { useEffect, useState, useRef } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet'
import L from 'leaflet'

import { api } from '../../services/api.js'
import { useLocalState } from '../../hooks/useLocalState.js'
import { subscribeToTable } from '../../services/realtime.js'

// Fix Leaflet default marker icons broken by bundlers
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

const patientIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})

const JOURNEY_STAGES = [
  'AT_HOME', 'REQUESTING_HOSPITAL', 'MATCHED_TO_HOSPITAL_1', 'EN_ROUTE_TO_HOSPITAL_1',
  'ARRIVED_AT_HOSPITAL_1', 'UNDER_CARE', 'REFERRAL_INITIATED', 'TRANSFER_TO_HOSPITAL_2', 'COMPLETED',
]

const TRANSPORT_LABEL: Record<string, { icon: string; text: string; className: string }> = {
  AMBULANCE: { icon: '🚑', text: 'Ambulance dispatched', className: 'badge bad' },
  SELF_DRIVE: { icon: '🚗', text: 'Self-drive / walk', className: 'badge neutral' },
}

// Auto-fit map to bounds when routeCoords or markers change
function FitBounds({ coords }: { coords: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (coords.length >= 2) {
      map.fitBounds(coords, { padding: [40, 40] })
    } else if (coords.length === 1) {
      map.setView(coords[0], 13)
    }
  }, [coords, map])
  return null
}

export default function PatientJourneyTracking() {
  const [journeyId] = useLocalState('demo.journeyId', null)
  const [patientLat] = useLocalState('demo.patientLat', null)
  const [patientLon] = useLocalState('demo.patientLon', null)
  const [transportMode] = useLocalState('demo.transportMode', null)
  const [journey, setJourney] = useState(null)
  const [error, setError] = useState(null)
  const [routeCoords, setRouteCoords] = useState<[number, number][]>([])
  const routeFetchedFor = useRef<string | null>(null)

  async function refresh() {
    if (!journeyId) return
    try {
      const data = await api.getJourney(journeyId)
      setJourney(data)
    } catch {
      setError('Could not load journey')
    }
  }

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 5000)
    const unsubscribe = subscribeToTable({ table: 'journeys', filter: `journey_id=eq.${journeyId}`, onChange: refresh })
    return () => {
      clearInterval(interval)
      unsubscribe()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [journeyId])

  // Fetch OSRM route between patient location and hospital
  useEffect(() => {
    if (!journey?.stage1_hospital) return
    if (!patientLat || !patientLon) return
    const h = journey.stage1_hospital
    const cacheKey = `${patientLat},${patientLon}->${h.latitude},${h.longitude}`
    if (routeFetchedFor.current === cacheKey) return
    routeFetchedFor.current = cacheKey

    const osrmUrl = `https://router.project-osrm.org/route/v1/driving/${patientLon},${patientLat};${h.longitude},${h.latitude}?overview=full&geometries=geojson`

    fetch(osrmUrl)
      .then((r) => r.json())
      .then((data) => {
        if (data.routes?.[0]?.geometry?.coordinates) {
          const coords: [number, number][] = data.routes[0].geometry.coordinates.map(
            ([lng, lat]: [number, number]) => [lat, lng]
          )
          setRouteCoords(coords)
        }
      })
      .catch(() => {
        // Fallback: draw straight line if OSRM is unreachable
        setRouteCoords([
          [patientLat, patientLon],
          [h.latitude, h.longitude],
        ])
      })
  }, [journey, patientLat, patientLon])

  if (!journeyId) return <div className="panel">No active journey yet.</div>
  if (error) return <div className="error-banner">{error}</div>
  if (!journey) return <p>Loading…</p>

  const currentIndex = JOURNEY_STAGES.indexOf(journey.current_status)
  const hospitalMarkers = [journey.stage1_hospital, journey.stage2_hospital].filter(Boolean)
  const transport = transportMode ? TRANSPORT_LABEL[transportMode] : null

  // Build all coords for FitBounds: route or fallback to markers + patient
  const allMapCoords: [number, number][] = routeCoords.length > 0
    ? routeCoords
    : [
        ...(patientLat && patientLon ? [[patientLat, patientLon] as [number, number]] : []),
        ...hospitalMarkers.map((m) => [m.latitude, m.longitude] as [number, number]),
      ]

  const mapCenter: [number, number] = allMapCoords.length > 0
    ? allMapCoords[0]
    : [20.5937, 78.9629] // India center fallback

  return (
    <div>
      <h2>Journey Tracking</h2>
      <p className="subtitle">
        Journey <span className="mono">{journeyId}</span> — status only changes through backend
        state transitions (step 4.9), never inferred from the UI alone.
      </p>

      {transport && (
        <div className="panel" style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px' }}>
          <span style={{ fontSize: 22 }}>{transport.icon}</span>
          <div>
            <strong>Transport mode:</strong>{' '}
            <span className={transport.className}>{transport.text}</span>
          </div>
        </div>
      )}

      <div className="stepper">
        {JOURNEY_STAGES.map((stage, i) => (
          <span key={stage} className={i < currentIndex ? 'done' : i === currentIndex ? 'active' : ''}>
            {stage.replaceAll('_', ' ')}
          </span>
        ))}
      </div>

      {(hospitalMarkers.length > 0 || (patientLat && patientLon)) && (
        <div className="panel">
          <h3>Navigation Map</h3>
          {routeCoords.length > 0 && (
            <p className="footnote" style={{ marginBottom: 8 }}>
              Route shown via OSRM · {Math.round(routeCoords.length > 0 && journey.stage1_hospital
                ? haversineKm(patientLat, patientLon, journey.stage1_hospital.latitude, journey.stage1_hospital.longitude)
                : 0)} km approx.
            </p>
          )}
          <div className="map-wrap">
            <MapContainer center={mapCenter} zoom={11} style={{ height: '100%', width: '100%' }}>
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution="&copy; OpenStreetMap contributors"
              />
              <FitBounds coords={allMapCoords} />

              {/* Patient location marker (red) */}
              {patientLat && patientLon && (
                <Marker position={[patientLat, patientLon]} icon={patientIcon}>
                  <Popup>📍 Your location</Popup>
                </Marker>
              )}

              {/* Hospital markers */}
              {hospitalMarkers.map((m) => (
                <Marker key={m.id} position={[m.latitude, m.longitude]}>
                  <Popup>🏥 {m.name}</Popup>
                </Marker>
              ))}

              {/* Route polyline */}
              {routeCoords.length > 0 && (
                <Polyline
                  positions={routeCoords}
                  pathOptions={{ color: '#0e6e63', weight: 4, opacity: 0.85 }}
                />
              )}
            </MapContainer>
          </div>
        </div>
      )}

      <div className="panel">
        <h3>Details</h3>
        {journey.stage1_hospital && <p>Hospital 1: <strong>{journey.stage1_hospital.name}</strong></p>}
        {journey.stage2_hospital && <p>Referred to: <strong>{journey.stage2_hospital.name}</strong></p>}
        {journey.transfer && (
          <p>Transfer status: <span className="badge neutral">{journey.transfer.status}</span></p>
        )}
        {journey.current_status === 'COMPLETED' && (
          <div className="warning-banner" style={{ background: 'var(--green-bg)', color: 'var(--green)' }}>
            Journey completed. This coordination request has closed.
          </div>
        )}
      </div>
    </div>
  )
}

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLon = ((lon2 - lon1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2
  return Math.round(R * 2 * Math.asin(Math.sqrt(a)))
}
