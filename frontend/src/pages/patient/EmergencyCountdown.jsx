import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../../services/api'
import { useLocalState } from '../../hooks/useLocalState'

const COUNTDOWN_SECONDS = 5

function getLocation() {
    return new Promise((resolve) => {
        if (!navigator.geolocation) {
            resolve({ lat: 28.6139, lon: 77.209 })
            return
        }
        navigator.geolocation.getCurrentPosition(
            (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
            () => resolve({ lat: 28.6139, lon: 77.209 }),
            { timeout: 4000 }
        )
    })
}

export default function EmergencyCountdown() {
    const [patientId] = useLocalState('demo.patientId', null)
    const [, setJourneyId] = useLocalState('demo.journeyId', null)
    const [secondsLeft, setSecondsLeft] = useState(COUNTDOWN_SECONDS)
    const [cancelled, setCancelled] = useState(false)
    const navigate = useNavigate()
    const locationPromiseRef = useRef(null)

    useEffect(() => {
        // Start fetching location immediately so it's ready by the time
        // the countdown hits zero, rather than adding extra delay then.
        locationPromiseRef.current = getLocation()
    }, [])

    useEffect(() => {
        if (cancelled) return
        if (secondsLeft <= 0) {
            dispatch()
            return
        }
        const timer = setTimeout(() => setSecondsLeft((s) => s - 1), 1000)
        return () => clearTimeout(timer)
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [secondsLeft, cancelled])

    async function dispatch() {
        try {
            const loc = await locationPromiseRef.current
            const result = await api.emergencyDispatch({
                patient_id: patientId || undefined,
                location_lat: loc.lat,
                location_lon: loc.lon,
            })
            setJourneyId(result.journey_id)
            navigate('/patient/emergency-status', { state: result, replace: true })
        } catch (err) {
            navigate('/patient/emergency-status', {
                state: { status: 'ERROR', warning: 'Could not reach the dispatch service. Call your local emergency number now.' },
                replace: true,
            })
        }
    }

    function handleCancel() {
        setCancelled(true)
        navigate(-1)
    }

    return (
        <div className="emergency-countdown-shell">
            <p className="emergency-countdown-label">Calling ambulance in</p>
            <div className="emergency-countdown-number">{secondsLeft}</div>
            <p className="footnote" style={{ color: 'rgba(255,255,255,0.7)' }}>
                Dispatching the nearest emergency-capable hospital automatically.
            </p>
            <button className="emergency-cancel-button" onClick={handleCancel}>
                Cancel
            </button>
        </div>
    )
}