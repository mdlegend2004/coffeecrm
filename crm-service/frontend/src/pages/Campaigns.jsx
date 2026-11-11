import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Sparkles, Rocket, X, MessageCircle, Mail, MessageSquare, Radio } from 'lucide-react'
import { getAnalyticsCampaigns, getSegments, createCampaign, launchCampaign, aiWriteMessage } from '../api'
import { StatusBadge, ChannelBadge, Loader, timeAgo } from '../components/ui'

const CHANNELS = [
  { id: 'whatsapp', label: 'WhatsApp', icon: MessageCircle },
  { id: 'sms', label: 'SMS', icon: MessageSquare },
  { id: 'email', label: 'Email', icon: Mail },
  { id: 'rcs', label: 'RCS', icon: Radio },
]

// Campaigns page: list of campaigns with delivery progress bars, plus the 'New campaign' wizard.
export default function Campaigns() {
  const [campaigns, setCampaigns] = useState(null)
  const [showWizard, setShowWizard] = useState(false)

  // Reload all campaigns with their funnel stats.
  const load = () => getAnalyticsCampaigns().then((d) => setCampaigns(Array.isArray(d) ? d : [])).catch(() => setCampaigns([]))
  useEffect(() => { load() }, [])

  // Launch a draft campaign; show the server's reason if it refuses (e.g. already running).
  const launch = async (id) => {
    try {
      await launchCampaign(id)
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Launch failed'
      alert(detail)
    }
    load()
  }

  if (!campaigns) return <Loader />

  return (
    <>
      <div className="page-head page-head-row">
        <div>
          <h1>Campaigns</h1>
          <p>Reach your shoppers across channels.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowWizard(true)}><Plus size={15} /> New campaign</button>
      </div>

      {campaigns.length === 0 ? (
        <div className="card"><div className="empty">No campaigns yet — create one to start reaching shoppers.</div></div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {campaigns.map((c) => {
            const sent = c.sent ?? c.sent_count ?? 0
            const delivered = c.delivered ?? c.delivered_count ?? 0
            const failed = c.failed ?? c.failed_count ?? 0
            // failed messages drop out of "sent", so include them in the denominator
            const fillPct = sent + failed > 0 ? (delivered / (sent + failed)) * 100 : 0
            return (
              <div key={c.campaign_id || c.id} className="card lift">
                <div className="spread">
                  <div>
                    <Link to={`/campaigns/${c.campaign_id || c.id}`} style={{ color: 'var(--text)', textDecoration: 'none', fontWeight: 600, fontSize: 15 }}>
                      {c.name}
                    </Link>
                    <div className="row mt-4" style={{ gap: 8 }}>
                      <ChannelBadge channel={c.channel} />
                      <StatusBadge status={c.status} />
                      <span className="tiny">{timeAgo(c.created_at)}</span>
                    </div>
                  </div>
                  <div className="row">
                    {c.status === 'draft' && (
                      <button className="btn btn-primary btn-sm" onClick={() => launch(c.campaign_id || c.id)}><Rocket size={13} /> Launch</button>
                    )}
                    <Link to={`/campaigns/${c.campaign_id || c.id}`} className="btn btn-ghost btn-sm">Details</Link>
                  </div>
                </div>
                {sent > 0 && (
                  <>
                    <div className="row mt-4" style={{ gap: 20, fontSize: 12.5 }}>
                      <span className="muted">Sent <b style={{ color: 'var(--text)' }}>{sent}</b></span>
                      <span className="muted">Delivered <b style={{ color: 'var(--teal)' }}>{delivered}</b></span>
                      {(c.opened ?? 0) > 0 && <span className="muted">Opened <b style={{ color: 'var(--text)' }}>{c.opened}</b></span>}
                      {(c.failed ?? c.failed_count ?? 0) > 0 && <span className="muted">Failed <b style={{ color: 'var(--red)' }}>{c.failed ?? c.failed_count}</b></span>}
                    </div>
                    <div className="funnel-bar"><div className="funnel-fill" style={{ width: `${fillPct}%` }} /></div>
                  </>
                )}
              </div>
            )
          })}
        </div>
      )}

      {showWizard && <Wizard onClose={() => { setShowWizard(false); load() }} />}
    </>
  )
}

// 3-step modal to create a campaign: 1) pick a segment, 2) pick channel + write the message, 3) review and save or launch.
function Wizard({ onClose }) {
  const [step, setStep] = useState(1)
  const [segments, setSegments] = useState([])
  const [segmentId, setSegmentId] = useState('')
  const [channel, setChannel] = useState('whatsapp')
  const [name, setName] = useState('')
  const [message, setMessage] = useState('')
  const [variants, setVariants] = useState(null)
  const [aiUsed, setAiUsed] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    getSegments().then((d) => setSegments(Array.isArray(d) ? d : d?.items || [])).catch(() => {})
  }, [])

  const seg = segments.find((s) => s.id === segmentId)

  // Ask the AI for 3 message variants for the chosen segment and channel.
  const writeWithAI = async () => {
    setBusy(true)
    try {
      const r = await aiWriteMessage({
        brand_name: 'BrewCo',
        segment_description: seg?.description || seg?.name || 'coffee shoppers',
        channel,
        goal: 'bring customers back with a personalised offer',
      })
      setVariants(r.variants || r)
    } catch { alert('AI write failed — check backend OPENAI_API_KEY') }
    setBusy(false)
  }

  // Save the campaign as a draft, and launch it straight away if `launch` is true.
  const createAndLaunch = async (launch) => {
    setBusy(true)
    try {
      const c = await createCampaign({
        name: name || `${seg?.name || 'Campaign'} · ${channel}`,
        segment_id: segmentId || null,   // never send empty string — Pydantic expects UUID or null
        channel,
        message_template: message,
        ai_generated_message: aiUsed,
      })
      if (launch) await launchCampaign(c.id)
      onClose()
    } catch { alert('Failed to create campaign'); setBusy(false) }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="spread">
          <h2>New campaign</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={14} /></button>
        </div>
        <p className="sub">Step {step} of 3 — {['Audience', 'Message', 'Review & launch'][step - 1]}</p>

        {step === 1 && (
          <>
            <div className="tiny mb-3">Choose a segment</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 18 }}>
              {segments.length === 0 && <div className="empty">No segments — build one first on the Segments page.</div>}
              {segments.map((s) => {
                const count = s.customer_count ?? 0
                const isEmpty = count === 0
                return (
                  <div
                    key={s.id}
                    className="card"
                    onClick={() => setSegmentId(s.id)}
                    style={{
                      padding: '14px 16px', cursor: 'pointer',
                      borderColor: segmentId === s.id ? 'var(--teal-strong)' : undefined,
                      background: segmentId === s.id ? 'var(--teal-dim)' : undefined,
                      opacity: isEmpty ? 0.6 : 1,
                    }}
                  >
                    <div className="spread">
                      <span style={{ fontWeight: 600 }}>{s.name}</span>
                      <span className="tiny" style={{ color: isEmpty ? 'var(--red, #f87171)' : undefined }}>
                        {count.toLocaleString('en-IN')} customers{isEmpty ? ' — no matches' : ''}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
            {seg && (seg.customer_count ?? 0) === 0 && (
              <div style={{
                background: 'rgba(248,113,113,0.12)',
                border: '1px solid rgba(248,113,113,0.35)',
                borderRadius: 10,
                padding: '10px 14px',
                fontSize: 13,
                color: 'var(--red, #f87171)',
                marginBottom: 14,
              }}>
                ⚠️ This segment currently has <b>0 matching customers</b>. The campaign will fail to send. Update the segment rules or choose a different segment.
              </div>
            )}
            <button
              className="btn btn-primary"
              disabled={!segmentId || (seg && (seg.customer_count ?? 0) === 0)}
              onClick={() => setStep(2)}
            >Continue</button>
          </>
        )}

        {step === 2 && (
          <>
            <div className="tiny mb-3">Channel</div>
            <div className="row mb-4" style={{ gap: 10 }}>
              {CHANNELS.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  className={`btn ${channel === id ? 'btn-primary' : 'btn-ghost'} btn-sm`}
                  onClick={() => setChannel(id)}
                ><Icon size={14} /> {label}</button>
              ))}
            </div>

            <input className="input mb-3" placeholder="Campaign name" value={name} onChange={(e) => setName(e.target.value)} />

            <textarea
              className="textarea mb-3"
              placeholder="Write your message… use {name} for personalisation"
              value={message}
              onChange={(e) => { setMessage(e.target.value); setAiUsed(false) }}
            />

            <button className="btn btn-ghost btn-sm mb-4" disabled={busy} onClick={writeWithAI}>
              {busy ? <div className="spinner" style={{ width: 13, height: 13 }} /> : <Sparkles size={13} />} Write with AI
            </button>

            {variants && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 18 }}>
                {variants.map((v, i) => (
                  <div
                    key={i}
                    className="card"
                    style={{ padding: 14, cursor: 'pointer', borderColor: message === v.message ? 'var(--teal-strong)' : undefined }}
                    onClick={() => { setMessage(v.message); setAiUsed(true) }}
                  >
                    <span className="badge badge-teal mb-3" style={{ marginBottom: 8 }}>{v.tone}</span>
                    <p style={{ fontSize: 13, lineHeight: 1.55, marginTop: 8 }}>{v.message}</p>
                  </div>
                ))}
              </div>
            )}

            <div className="row">
              <button className="btn btn-ghost" onClick={() => setStep(1)}>Back</button>
              <button className="btn btn-primary" disabled={!message.trim()} onClick={() => setStep(3)}>Continue</button>
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <div className="card mb-4" style={{ padding: 18 }}>
              <div className="spread mb-3"><span className="tiny">Audience</span><b>{seg?.name} · {(seg?.customer_count ?? 0).toLocaleString('en-IN')} customers</b></div>
              <div className="spread mb-3"><span className="tiny">Channel</span><ChannelBadge channel={channel} /></div>
              <div className="tiny mb-3">Message</div>
              <p style={{ fontSize: 13, lineHeight: 1.6, background: 'rgba(255,255,255,0.04)', padding: 14, borderRadius: 12 }}>{message}</p>
            </div>
            <div className="row">
              <button className="btn btn-ghost" onClick={() => setStep(2)}>Back</button>
              <button className="btn btn-ghost" disabled={busy} onClick={() => createAndLaunch(false)}>Save draft</button>
              <button className="btn btn-primary" disabled={busy} onClick={() => createAndLaunch(true)}>
                <Rocket size={14} /> Launch now
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
