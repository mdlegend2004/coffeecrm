import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { getOverview, getAnalyticsCampaigns } from '../api'
import { StatusBadge, ChannelBadge, Loader, pct } from '../components/ui'
import { useCountUp } from '../components/useCountUp'

// Shows a number that counts up from 0 when the dashboard opens.
function AnimatedCount({ value, decimals = 0, suffix = '' }) {
  const animated = useCountUp(value)
  return <>{animated.toFixed(decimals)}{suffix}</>
}

// One KPI tile: label with icon, big value, and a small caption.
function StatCard({ label, display, sub, icon, delay = 0 }) {
  return (
    <div className="card lift card-enter" style={{ animationDelay: `${delay}ms` }}>
      <div className="stat-label"><span className="stat-icon">{icon}</span>{label}</div>
      <div className="stat-value">{display}</div>
      <div className="stat-sub">{sub}</div>
    </div>
  )
}

// Home page: KPI tiles, the 6 most recent campaigns, and a sent/delivered/opened chart.
export default function Dashboard() {
  const [overview, setOverview] = useState(null)
  const [campaigns, setCampaigns] = useState(null)

  useEffect(() => {
    getOverview().then(setOverview).catch(() => setOverview({}))
    getAnalyticsCampaigns()
      .then((d) => setCampaigns(Array.isArray(d) ? d : d?.campaigns || []))
      .catch(() => setCampaigns([]))
  }, [])

  if (!overview || !campaigns) return <Loader />

  const chartData = campaigns.slice(0, 6).map((c) => ({
    name: (c.name || 'Campaign').slice(0, 12),
    Sent: c.sent || 0,
    Delivered: c.delivered || 0,
    Opened: c.opened || 0,
  }))

  return (
    <>
      <div className="page-head page-head-row">
        <div>
          <h1>Good morning, BrewCo ☕</h1>
          <p>Here's how your shoppers are being reached today.</p>
        </div>
        <div className="row">
          <Link to="/assistant" className="btn btn-ghost">✦ Ask AI</Link>
          <Link to="/campaigns" className="btn btn-primary">+ New campaign</Link>
        </div>
      </div>

      <div className="stats-grid">
        <StatCard label="Total customers" delay={40} sub="in your shopper base" icon="◎"
          display={<AnimatedCount value={overview.total_customers ?? 0} />} />
        <StatCard label="Campaigns this month" delay={100} sub="across all channels" icon="◁"
          display={<AnimatedCount value={overview.campaigns_this_month ?? 0} />} />
        <StatCard label="Avg delivery rate" delay={160} sub="completed campaigns" icon="✓"
          display={<AnimatedCount value={overview.avg_delivery_rate ?? 0} decimals={1} suffix="%" />} />
        <StatCard label="Top channel" delay={220} sub="by campaign volume" icon="★"
          display={<span style={{ textTransform:'capitalize', fontSize:26 }}>{overview.top_channel || '—'}</span>} />
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1.4fr 1fr', gap:16 }}>
        <div className="card card-enter" style={{ animationDelay:'280ms' }}>
          <div className="section-title">Recent campaigns</div>
          {campaigns.length === 0 ? (
            <div className="empty">No campaigns yet — launch your first one →</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Name</th><th>Channel</th><th>Status</th><th>Sent</th><th>Delivered</th></tr></thead>
                <tbody>
                  {campaigns.slice(0, 6).map((c) => (
                    <tr key={c.campaign_id || c.id}>
                      <td><Link to={`/campaigns/${c.campaign_id || c.id}`} style={{ color:'var(--coffee-light)', textDecoration:'none', fontWeight:500 }}>{c.name}</Link></td>
                      <td><ChannelBadge channel={c.channel} /></td>
                      <td><StatusBadge status={c.status} /></td>
                      <td>{c.sent ?? 0}</td>
                      <td>{c.delivered ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card card-enter" style={{ animationDelay:'340ms' }}>
          <div className="section-title">Campaign performance</div>
          {chartData.length === 0 ? (
            <div className="empty">Performance shows after campaigns run.</div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={chartData} barGap={2}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(200,135,63,0.08)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill:'#7a5c38', fontSize:11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill:'#7a5c38', fontSize:11 }} axisLine={false} tickLine={false} width={32} />
                <Tooltip
                  cursor={{ fill:'rgba(200,135,63,0.05)' }}
                  contentStyle={{ background:'#130c07', border:'1px solid rgba(200,135,63,0.25)', borderRadius:12, fontSize:12 }}
                />
                <Bar dataKey="Sent" fill="#5c3210" radius={[6,6,0,0]} />
                <Bar dataKey="Delivered" fill="#b8732a" radius={[6,6,0,0]} />
                <Bar dataKey="Opened" fill="#e8a85a" radius={[6,6,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </>
  )
}
