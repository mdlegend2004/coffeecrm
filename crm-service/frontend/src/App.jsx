import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import Dashboard from './pages/Dashboard'
import Customers from './pages/Customers'
import Segments from './pages/Segments'
import Campaigns from './pages/Campaigns'
import CampaignDetail from './pages/CampaignDetail'
import Assistant from './pages/Assistant'

// Small coffee-cup SVG used in the sidebar logo.
const CoffeeIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <path d="M5 3h11l1.5 9H5L6.5 3z" fill="rgba(3,32,29,0.9)" stroke="rgba(3,32,29,0.5)" strokeWidth="0.5" />
    <path d="M5 12c0 3.5 2.5 6 6 6s6-2.5 6-6" stroke="rgba(3,32,29,0.7)" strokeWidth="1.2" fill="none" strokeLinecap="round" />
    <path d="M16.5 7.5 C18 7.5 19.5 8.5 19.5 10 C19.5 11.5 18 12.5 16.5 12.5" stroke="rgba(3,32,29,0.7)" strokeWidth="1.2" fill="none" strokeLinecap="round" />
    <rect x="4" y="18" width="13" height="2" rx="1" fill="rgba(3,32,29,0.7)" />
  </svg>
)

const nav = [
  { to: '/', label: 'Dashboard', icon: '▦', end: true },
  { to: '/customers', label: 'Customers', icon: '◎' },
  { to: '/segments', label: 'Segments', icon: '◈' },
  { to: '/campaigns', label: 'Campaigns', icon: '◁' },
  { to: '/assistant', label: 'AI Assistant', icon: '✦' },
]

// Scroll to the top and replay the page-enter animation whenever the URL changes.
function PageWrapper({ children }) {
  const location = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [location.pathname])
  return <div key={location.pathname} className="page-enter">{children}</div>
}

// App shell: sidebar navigation on the left, the current page (chosen by URL) on the right.
export default function App() {
  return (
    <div className="app">
      <div className="orbs">
        <div className="orb orb-1" />
        <div className="orb orb-2" />
        <div className="orb orb-3" />
      </div>

      <aside className="sidebar">
        <div className="logo">
          <div className="logo-mark">
            <div className="steam-wrap">
              <div className="steam" />
              <div className="steam" />
              <div className="steam" />
            </div>
            <CoffeeIcon />
          </div>
          BrewCo CRM
        </div>

        {nav.map(({ to, label, icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <span style={{ fontSize: 16, opacity: 0.85 }}>{icon}</span>
            {label}
          </NavLink>
        ))}

        <div className="sidebar-foot">
          AI-native CRM for <b>BrewCo</b> coffee chain.
        </div>
      </aside>

      <main className="main">
        <PageWrapper>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/customers" element={<Customers />} />
            <Route path="/segments" element={<Segments />} />
            <Route path="/campaigns" element={<Campaigns />} />
            <Route path="/campaigns/:id" element={<CampaignDetail />} />
            <Route path="/assistant" element={<Assistant />} />
          </Routes>
        </PageWrapper>
      </main>
    </div>
  )
}
