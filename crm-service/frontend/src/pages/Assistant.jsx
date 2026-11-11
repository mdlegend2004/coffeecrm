import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles, Send as SendIcon, Rocket, Users } from 'lucide-react'
import { aiCreateCampaign, launchCampaign } from '../api'
import { ChannelBadge } from '../components/ui'

const SUGGESTIONS = [
  'Re-engage customers from Delhi who haven\'t ordered in 90 days via WhatsApp',
  'Send a thank-you offer to VIP customers in Mumbai over email',
  'Win back lapsed shoppers who spent over ₹3000 with an SMS discount',
]

// AI Assistant page: chat where one sentence becomes a saved segment + draft campaign, with a launch button.
export default function Assistant() {
  const [messages, setMessages] = useState([
    { role: 'ai', text: 'Hi! Tell me who you want to reach and what you want to say — I\'ll build the segment, write the message, and set up the campaign for you.' },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [draft, setDraft] = useState(null)
  const [launched, setLaunched] = useState(false)
  const endRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), [messages, draft])

  // Send the user's request to the AI, then show the drafted campaign in the preview panel.
  const submit = async (text) => {
    const intent = (text ?? input).trim()
    if (!intent || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: intent }])
    setBusy(true)
    try {
      const r = await aiCreateCampaign(intent)
      setDraft(r)
      const seg = r.segment || {}
      setMessages((m) => [...m, {
        role: 'ai',
        text: `Done! I built the segment "${seg.name || 'AI Segment'}" matching ${seg.customer_count ?? '—'} customers and drafted the campaign "${r.campaign?.name || ''}". Review it on the right and launch when ready.`,
      }])
    } catch {
      setMessages((m) => [...m, { role: 'ai', text: 'Something went wrong — make sure the backend is running and OPENAI_API_KEY is set.' }])
    }
    setBusy(false)
  }

  // Launch the drafted campaign, then jump to its detail page to watch results arrive.
  const launch = async () => {
    if (!draft?.campaign?.id || launched) return
    setBusy(true)
    try {
      await launchCampaign(draft.campaign.id)
      setLaunched(true)
      setMessages((m) => [...m, { role: 'ai', text: 'Campaign launched! 🚀 Watching delivery callbacks roll in now…' }])
      setTimeout(() => navigate(`/campaigns/${draft.campaign.id}`), 1200)
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Launch failed'
      setMessages((m) => [...m, { role: 'ai', text: `❌ ${detail}` }])
    }
    setBusy(false)
  }

  return (
    <>
      <div className="page-head">
        <h1><Sparkles size={22} style={{ verticalAlign: -3, color: 'var(--teal)' }} /> AI Assistant</h1>
        <p>Describe a campaign in plain English — the AI handles audience, message and setup.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: draft ? '1.4fr 1fr' : '1fr', gap: 16 }}>
        <div className="card">
          <div className="chat-box">
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role === 'user' ? 'msg-user' : 'msg-ai'}`}>{m.text}</div>
            ))}
            {busy && <div className="msg msg-ai row"><div className="spinner" style={{ width: 14, height: 14 }} /> thinking…</div>}
            <div ref={endRef} />
          </div>

          <div className="row mt-4" style={{ flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
            {SUGGESTIONS.map((s) => (
              <span key={s} className="chip" onClick={() => submit(s)}>{s.slice(0, 52)}…</span>
            ))}
          </div>

          <div className="row">
            <input
              className="input"
              placeholder="e.g. Re-engage lapsed Chennai customers with a 20% off WhatsApp message"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submit()}
            />
            <button className="btn btn-primary" disabled={busy || !input.trim()} onClick={() => submit()}>
              <SendIcon size={15} />
            </button>
          </div>
        </div>

        {draft && (
          <div className="card" style={{ alignSelf: 'flex-start' }}>
            <div className="section-title"><Rocket size={15} /> Campaign preview</div>

            <div className="tiny mb-3">Segment</div>
            <div className="card mb-4" style={{ padding: 14 }}>
              <div className="spread">
                <b>{draft.segment?.name || 'AI Segment'}</b>
                <span className="row tiny" style={{ gap: 5, color: 'var(--teal)' }}>
                  <Users size={13} /> {draft.segment?.customer_count ?? '—'}
                </span>
              </div>
            </div>

            <div className="tiny mb-3">Channel</div>
            <div className="mb-4"><ChannelBadge channel={draft.campaign?.channel || 'whatsapp'} /></div>

            <div className="tiny mb-3">Message</div>
            <p className="mb-4" style={{ fontSize: 13, lineHeight: 1.6, background: 'rgba(255,255,255,0.04)', padding: 14, borderRadius: 12 }}>
              {draft.campaign?.message_template || draft.message_variants?.[0]?.message || '—'}
            </p>

            <button
              className={`btn ${launched ? 'btn-ghost' : 'btn-primary'}`}
              style={{ width: '100%', justifyContent: 'center' }}
              disabled={busy || launched}
              onClick={launch}
            >
              <Rocket size={15} /> {launched ? 'Launched ✓' : 'Launch campaign'}
            </button>
          </div>
        )}
      </div>
    </>
  )
}
