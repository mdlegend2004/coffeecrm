import { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Sparkles, Lightbulb, TrendingUp } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { getCampaignStats, aiInsights } from '../api'
import { StatusBadge, ChannelBadge, Loader, pct } from '../components/ui'

// Campaign detail page: rate tiles, funnel chart (refreshes every 4s), and on-demand AI insights.
export default function CampaignDetail() {
  const { id } = useParams()
  const [stats, setStats] = useState(null)
  const [insights, setInsights] = useState(null)
  const [insightsBusy, setInsightsBusy] = useState(false)
  const timer = useRef(null)

  // Fetch the latest funnel stats for this campaign.
  const load = () => getCampaignStats(id).then(setStats).catch(() => {})

  useEffect(() => {
    load()
    // live polling — callbacks from the channel service update stats in real time
    timer.current = setInterval(load, 4000)
    return () => clearInterval(timer.current)
  }, [id])

  // Ask the AI to analyse this campaign's performance.
  const fetchInsights = async () => {
    setInsightsBusy(true)
    try {
      const r = await aiInsights(id)
      setInsights(r.insights || r)
    } catch { alert('Insights failed — check backend OPENAI_API_KEY') }
    setInsightsBusy(false)
  }

  if (!stats) return <Loader />

  const funnel = [
    { stage: 'Sent', value: stats.sent ?? 0 },
    { stage: 'Delivered', value: stats.delivered ?? 0 },
    { stage: 'Opened', value: stats.opened ?? 0 },
    { stage: 'Clicked', value: stats.clicked ?? 0 },
    { stage: 'Converted', value: stats.converted ?? 0 },
  ]

  const rates = [
    { label: 'Delivery rate', value: pct(stats.delivery_rate) },
    { label: 'Open rate', value: pct(stats.open_rate) },
    { label: 'Click rate', value: pct(stats.click_rate) },
    { label: 'Conversion', value: pct(stats.conversion_rate) },
  ]

  return (
    <>
      <Link to="/campaigns" className="row tiny mb-4" style={{ textDecoration: 'none', color: 'var(--text-2)', gap: 6 }}>
        <ArrowLeft size={14} /> All campaigns
      </Link>

      <div className="page-head page-head-row">
        <div>
          <h1>{stats.name || 'Campaign'}</h1>
          <div className="row mt-4" style={{ gap: 8 }}>
            <ChannelBadge channel={stats.channel} />
            <StatusBadge status={stats.status} />
            {stats.status === 'running' && <span className="tiny">stats refresh live every 4s</span>}
          </div>
        </div>
      </div>

      <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))' }}>
        {rates.map((r) => (
          <div key={r.label} className="card lift" style={{ padding: 18 }}>
            <div className="stat-label">{r.label}</div>
            <div className="stat-value" style={{ fontSize: 24, color: 'var(--teal)' }}>{r.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: 16 }}>
        <div className="card">
          <div className="section-title"><TrendingUp size={15} /> Funnel</div>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={funnel} layout="vertical" margin={{ left: 10 }}>
              <XAxis type="number" tick={{ fill: '#5a7d78', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="stage" tick={{ fill: '#8fb3ae', fontSize: 12 }} axisLine={false} tickLine={false} width={78} />
              <Tooltip
                cursor={{ fill: 'rgba(45,212,191,0.05)' }}
                contentStyle={{ background: '#0a1817', border: '1px solid rgba(45,212,191,0.2)', borderRadius: 12, fontSize: 12 }}
              />
              <Bar dataKey="value" fill="#14b8a6" radius={[0, 8, 8, 0]} barSize={22} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="spread mb-4">
            <div className="section-title" style={{ marginBottom: 0 }}><Sparkles size={15} color="#2dd4bf" /> AI insights</div>
            <button className="btn btn-ghost btn-sm" disabled={insightsBusy} onClick={fetchInsights}>
              {insightsBusy ? <div className="spinner" style={{ width: 13, height: 13 }} /> : 'Generate'}
            </button>
          </div>
          {!insights ? (
            <div className="empty">Click generate for an AI read on this campaign's performance.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {insights.map((it, i) => (
                <div key={i} className="row" style={{ alignItems: 'flex-start', gap: 10 }}>
                  <span className="stat-icon" style={{ flexShrink: 0, width: 26, height: 26 }}>
                    {it.type === 'recommendation' ? <Lightbulb size={13} /> : <TrendingUp size={13} />}
                  </span>
                  <div>
                    <span className={`badge ${it.type === 'recommendation' ? 'badge-amber' : 'badge-teal'}`} style={{ marginBottom: 5 }}>{it.type}</span>
                    <p style={{ fontSize: 13, lineHeight: 1.55, marginTop: 5 }}>{it.text}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
