// Format a number as Indian rupees with no decimals, e.g. 12345 -> ₹12,345.
export const inr = (n) =>
  '₹' + Number(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })

// Format a number as a percentage with one decimal, e.g. 81.48 -> 81.5%.
export const pct = (n) => `${Number(n || 0).toFixed(1)}%`

// Turn a date into a short relative label: today, yesterday, 5d ago, 3mo ago, 2y ago.
export const timeAgo = (dateStr) => {
  if (!dateStr) return '—'
  const days = Math.floor((Date.now() - new Date(dateStr)) / 86400000)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 30) return `${days}d ago`
  if (days < 365) return `${Math.floor(days / 30)}mo ago`
  return `${Math.floor(days / 365)}y ago`
}

// Coloured pill for a campaign or message status; 'running' gets a pulsing dot.
export function StatusBadge({ status }) {
  const map = {
    completed: ['badge-green', null],
    running: ['badge-amber', true],
    draft: ['badge-gray', null],
    failed: ['badge-red', null],
    delivered: ['badge-green', null],
    sent: ['badge-teal', null],
    queued: ['badge-gray', null],
    opened: ['badge-teal', null],
    read: ['badge-teal', null],
    clicked: ['badge-amber', null],
    converted: ['badge-green', null],
  }
  const [cls, pulse] = map[status] || ['badge-gray', null]
  return (
    <span className={`badge ${cls}`}>
      {pulse && <span className="pulse-dot" />}
      {status}
    </span>
  )
}

// Coloured pill for a customer tag (vip, loyal, at-risk, ...).
export function TagBadge({ tag }) {
  const map = {
    vip: 'badge-amber',
    loyal: 'badge-green',
    new: 'badge-teal',
    'at-risk': 'badge-red',
    lapsed: 'badge-gray',
    'weekend-visitor': 'badge-teal',
  }
  return <span className={`badge ${map[tag] || 'badge-gray'}`}>{tag}</span>
}

// Pill showing a channel name (WHATSAPP, SMS, EMAIL, RCS).
export function ChannelBadge({ channel }) {
  return <span className="badge badge-teal" style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>{channel}</span>
}

// Centered spinner shown while data is loading.
export function Loader() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
      <div className="spinner" />
    </div>
  )
}
