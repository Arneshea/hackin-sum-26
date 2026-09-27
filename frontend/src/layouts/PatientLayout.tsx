import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import EmergencyButton from '../components/EmergencyButton.jsx'

function NavItem({ to, children }) {
  return (
    <NavLink to={to} end className={({ isActive }) => (isActive ? 'active' : '')}>
      {children}
    </NavLink>
  )
}

export default function PatientLayout() {
  const navigate = useNavigate()

  return (
    <div className="app-shell">
      <EmergencyButton />
      <aside className="app-nav">
        <h1>Patient / Attendant</h1>
        <span className="prototype-tag">Prototype — simulated data</span>

        <nav>
          <NavItem to="/patient">Home</NavItem>
          <NavItem to="/patient/assessment">Assessment</NavItem>
          <NavItem to="/patient/options">Hospital Options</NavItem>
          <NavItem to="/patient/journey">Journey Tracking</NavItem>
          <NavItem to="/patient/referral">Get a Referral</NavItem>
        </nav>

        <a className="switch-role-link" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
          ← Switch role
        </a>
      </aside>

      <main className="app-main">
        <Outlet />
      </main>
    </div>
  )
}
