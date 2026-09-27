import { useNavigate } from 'react-router-dom'

const ROLES = [
  {
    key: 'patient',
    icon: '🧑‍🤝‍🧑',
    title: 'Patient / Attendant',
    description: 'Get assessed, find a hospital, track your journey, or start a referral.',
    to: '/patient',
  },
  {
    key: 'hospital',
    icon: '🏥',
    title: 'Hospital Staff',
    description: 'Respond to incoming requests and referrals, manage transfers and handoffs.',
    to: '/hospital',
  },
  {
    key: 'admin',
    icon: '🛰️',
    title: 'Network Admin',
    description: 'Network overview, hospital state simulator, and live event feed.',
    to: '/admin',
  },
]

export default function Landing() {
  const navigate = useNavigate()

  return (
    <div className="landing-shell">
      <h1>National Patient Navigation &amp; Referral Coordination Network</h1>
      <p className="subtitle">Prototype — simulated data only. Choose how you're using it.</p>

      <div className="role-cards">
        {ROLES.map((r) => (
          <div key={r.key} className="role-card" onClick={() => navigate(r.to)}>
            <span className="role-icon">{r.icon}</span>
            <h3>{r.title}</h3>
            <p>{r.description}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
