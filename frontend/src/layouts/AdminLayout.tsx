import { NavLink, Outlet, useNavigate } from 'react-router-dom'

function NavItem({ to, children }) {
  return (
    <NavLink to={to} end className={({ isActive }) => (isActive ? 'active' : '')}>
      {children}
    </NavLink>
  )
}

export default function AdminLayout() {
  const navigate = useNavigate()

  return (
    <div className="app-shell">
      <aside className="app-nav">
        <h1>Network Admin</h1>
        <span className="prototype-tag">Prototype — simulated data</span>

        <nav>
          <NavItem to="/admin/network">Network Overview</NavItem>
          <NavItem to="/admin/simulator">Hospital State Simulator</NavItem>
          <NavItem to="/admin/events">Live Events</NavItem>
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
