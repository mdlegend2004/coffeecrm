import { useEffect, useState } from 'react'
import { Sparkles, Plus, Trash2, Users, X } from 'lucide-react'
import { getSegments, createSegment, previewSegment, deleteSegment, aiBuildSegment } from '../api'
import { Loader, timeAgo } from '../components/ui'

const FIELDS = ['total_spent', 'purchase_count', 'last_purchase_date', 'city', 'age', 'gender', 'tags']
const OPS = ['eq', 'neq', 'gte', 'lte', 'gt', 'lt', 'in', 'not_in', 'days_ago_lte', 'days_ago_gte', 'contains']

// Turn segment rules into readable text, e.g. 'city eq Mumbai AND total_spent gte 2000'.
const ruleText = (rules) => {
  if (!rules?.conditions?.length) return 'No conditions'
  return rules.conditions
    .map((c) => `${c.field} ${c.op} ${Array.isArray(c.value) ? c.value.join(', ') : c.value}`)
    .join(` ${rules.operator} `)
}

// Segments page: grid of saved segments, plus buttons to build one manually or with AI.
export default function Segments() {
  const [segments, setSegments] = useState(null)
  const [showAI, setShowAI] = useState(false)
  const [showManual, setShowManual] = useState(false)

  // Reload the list of segments from the API.
  const load = () => getSegments().then((d) => setSegments(Array.isArray(d) ? d : d?.items || [])).catch(() => setSegments([]))
  useEffect(() => { load() }, [])

  // Ask for confirmation, delete the segment, then refresh the list.
  const remove = async (id) => {
    if (!confirm('Delete this segment?')) return
    await deleteSegment(id).catch(() => {})
    load()
  }

  if (!segments) return <Loader />

  return (
    <>
      <div className="page-head page-head-row">
        <div>
          <h1>Segments</h1>
          <p>Carve out audiences from your shopper base.</p>
        </div>
        <div className="row">
          <button className="btn btn-ghost" onClick={() => setShowManual(true)}><Plus size={15} /> Manual rules</button>
          <button className="btn btn-primary" onClick={() => setShowAI(true)}><Sparkles size={15} /> Build with AI</button>
        </div>
      </div>

      {segments.length === 0 ? (
        <div className="card"><div className="empty">No segments yet — describe one to the AI and it'll build it for you.</div></div>
      ) : (
        <div className="grid-3">
          {segments.map((s) => (
            <div key={s.id} className="card lift">
              <div className="spread mb-3">
                <span style={{ fontWeight: 600, fontSize: 15 }}>{s.name}</span>
                {s.ai_generated && <span className="badge badge-teal"><Sparkles size={11} /> AI</span>}
              </div>
              <p className="tiny mb-4" style={{ lineHeight: 1.6 }}>{ruleText(s.rules)}</p>
              <div className="spread">
                <span className="row" style={{ gap: 6, color: 'var(--teal)', fontWeight: 600, fontSize: 13 }}>
                  <Users size={14} /> {(s.customer_count ?? 0).toLocaleString('en-IN')}
                </span>
                <div className="row" style={{ gap: 8 }}>
                  <span className="tiny">{timeAgo(s.created_at)}</span>
                  <button className="btn btn-ghost btn-sm" onClick={() => remove(s.id)}><Trash2 size={13} /></button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showAI && <AIBuilderModal onClose={() => { setShowAI(false); load() }} />}
      {showManual && <ManualBuilderModal onClose={() => { setShowManual(false); load() }} />}
    </>
  )
}

// Modal: describe an audience in English, let the AI turn it into rules, preview, then save.
function AIBuilderModal({ onClose }) {
  const [prompt, setPrompt] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [name, setName] = useState('')

  // Send the prompt to the AI and show the generated rules and match count.
  const generate = async () => {
    setBusy(true)
    try {
      const r = await aiBuildSegment(prompt)
      setResult(r)
      setName(prompt.slice(0, 60))
    } catch (e) {
      alert('AI generation failed — check OPENAI_API_KEY in backend .env')
    }
    setBusy(false)
  }

  // Save the AI-generated rules as a new segment and close the modal.
  const save = async () => {
    setBusy(true)
    try {
      await createSegment({ name: name || 'AI Segment', description: prompt, rules: result.rules, ai_generated: true })
      onClose()
    } catch { alert('Save failed'); setBusy(false) }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="spread">
          <h2><Sparkles size={17} style={{ verticalAlign: -2, color: 'var(--teal)' }} /> Build segment with AI</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={14} /></button>
        </div>
        <p className="sub">Describe your audience in plain English.</p>

        <textarea
          className="textarea mb-3"
          placeholder="e.g. customers from Mumbai who spent over ₹5000 and haven't ordered in 60 days"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <button className="btn btn-primary" disabled={busy || !prompt.trim()} onClick={generate}>
          {busy && !result ? <div className="spinner" style={{ width: 14, height: 14 }} /> : <Sparkles size={14} />}
          Generate segment
        </button>

        {result && (
          <div className="mt-4">
            <div className="card" style={{ padding: 16, marginBottom: 14 }}>
              <div className="tiny mb-3">Generated rules</div>
              <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}>
                {(result.rules?.conditions || []).map((c, i) => (
                  <span key={i} className="badge badge-teal">{c.field} {c.op} {Array.isArray(c.value) ? c.value.join(',') : String(c.value)}</span>
                ))}
              </div>
              <div className="mt-4" style={{ fontWeight: 600, color: 'var(--teal)' }}>
                Preview: {result.preview_count ?? result.count ?? 0} customers match
              </div>
              {(result.sample_customers || []).length > 0 && (
                <div className="tiny mt-4">
                  e.g. {(result.sample_customers || []).slice(0, 3).map((c) => c.name).join(', ')}
                </div>
              )}
            </div>
            <input className="input mb-3" placeholder="Segment name" value={name} onChange={(e) => setName(e.target.value)} />
            <button className="btn btn-primary" disabled={busy} onClick={save}>Save segment</button>
          </div>
        )}
      </div>
    </div>
  )
}

// Modal: build segment rules by hand (field / operator / value rows joined by AND or OR).
function ManualBuilderModal({ onClose }) {
  const [name, setName] = useState('')
  const [operator, setOperator] = useState('AND')
  const [conditions, setConditions] = useState([{ field: 'total_spent', op: 'gte', value: '' }])
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)

  // Convert the form rows into the rules JSON the API expects (drops empty rows, splits lists, parses numbers).
  const buildRules = () => ({
    operator,
    conditions: conditions
      .filter((c) => c.value !== '')
      .map((c) => ({
        ...c,
        value: ['in', 'not_in'].includes(c.op)
          ? String(c.value).split(',').map((v) => v.trim())
          : isNaN(Number(c.value)) ? c.value : Number(c.value),
      })),
  })

  // Ask the API how many customers match the current rules, without saving.
  const doPreview = async () => {
    setBusy(true)
    try { setPreview(await previewSegment(buildRules())) } catch { alert('Preview failed') }
    setBusy(false)
  }

  // Save the hand-built rules as a new segment and close the modal.
  const save = async () => {
    setBusy(true)
    try {
      await createSegment({ name: name || 'New segment', description: '', rules: buildRules(), ai_generated: false })
      onClose()
    } catch { alert('Save failed'); setBusy(false) }
  }

  // Change one field of one condition row.
  const update = (i, key, val) => {
    const next = [...conditions]
    next[i] = { ...next[i], [key]: val }
    setConditions(next)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="spread">
          <h2>Manual segment</h2>
          <button className="btn btn-ghost btn-sm" onClick={onClose}><X size={14} /></button>
        </div>
        <p className="sub">Combine conditions with AND / OR.</p>

        <input className="input mb-3" placeholder="Segment name" value={name} onChange={(e) => setName(e.target.value)} />

        <div className="row mb-3">
          <span className="tiny">Match</span>
          <select className="select" style={{ width: 90 }} value={operator} onChange={(e) => setOperator(e.target.value)}>
            <option>AND</option><option>OR</option>
          </select>
          <span className="tiny">of the following:</span>
        </div>

        {conditions.map((c, i) => (
          <div key={i} className="row mb-3" style={{ gap: 8 }}>
            <select className="select" value={c.field} onChange={(e) => update(i, 'field', e.target.value)}>
              {FIELDS.map((f) => <option key={f}>{f}</option>)}
            </select>
            <select className="select" style={{ width: 140 }} value={c.op} onChange={(e) => update(i, 'op', e.target.value)}>
              {OPS.map((o) => <option key={o}>{o}</option>)}
            </select>
            <input className="input" placeholder="value" value={c.value} onChange={(e) => update(i, 'value', e.target.value)} />
            <button className="btn btn-ghost btn-sm" onClick={() => setConditions(conditions.filter((_, x) => x !== i))}><Trash2 size={13} /></button>
          </div>
        ))}

        <button className="btn btn-ghost btn-sm mb-4" onClick={() => setConditions([...conditions, { field: 'city', op: 'eq', value: '' }])}>
          <Plus size={13} /> Add condition
        </button>

        <div className="row">
          <button className="btn btn-ghost" disabled={busy} onClick={doPreview}>Preview</button>
          <button className="btn btn-primary" disabled={busy} onClick={save}>Save segment</button>
          {preview && <span style={{ color: 'var(--teal)', fontWeight: 600 }}>{preview.count ?? preview.preview_count ?? 0} customers match</span>}
        </div>
      </div>
    </div>
  )
}
