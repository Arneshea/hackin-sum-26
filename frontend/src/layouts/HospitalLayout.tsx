import { NavLink, Outlet, useNavigate } from 'react-router-dom'

function NavItem({ to, children }) {
  return (
    <NavLink to={to} end className={({ isActive }) => (isActive ? 'active' : '')}>
      {children}
    </NavLink>
  )
}

export default function HospitalLayout() {
  const navigate = useNavigate()

  return (
    <div className="app-shell">
      <aside className="app-nav">
        <h1>Hospital Staff</h1>
        <span className="prototype-tag">Prototype — simulated data</span>

        <nav>
          <NavItem to="/hospital">Dashboard</NavItem>
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
