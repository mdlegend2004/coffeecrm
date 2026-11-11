import { useEffect, useState } from 'react'
import { Search, X } from 'lucide-react'
import { getCustomers, getCustomer } from '../api'
import { inr, timeAgo, TagBadge, StatusBadge, Loader } from '../components/ui'

const CITIES = ['Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Hyderabad', 'Pune', 'Kolkata']

// Customers page: searchable, filterable, paginated table; click a row for details.
export default function Customers() {
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [city, setCity] = useState('')
  const [minSpent, setMinSpent] = useState('')
  const [selected, setSelected] = useState(null)

  // Fetch the current page of customers using the active search / city / spend filters.
  const load = () => {
    const params = { page, limit: 20 }
    if (search) params.search = search
    if (city) params.city = city
    if (minSpent) params.min_spent = minSpent
    getCustomers(params).then(setData).catch(() => setData({ items: [], total: 0 }))
  }

  useEffect(() => { load() }, [page, city, minSpent])

  // Open the detail modal immediately, then fill in the customer's recent orders from the API.
  const openDetail = async (c) => {
    setSelected({ ...c, loading: true })
    try {
      const full = await getCustomer(c.id)
      setSelected(full)
    } catch {
      setSelected(c)
    }
  }

  if (!data) return <Loader />
  const totalPages = Math.max(1, Math.ceil((data.total || 0) / 20))

  return (
    <>
      <div className="page-head">
        <h1>Customers</h1>
        <p>{(data.total || 0).toLocaleString('en-IN')} shoppers in your base</p>
      </div>

      <div className="card mb-4">
        <div className="row" style={{ flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: 1, minWidth: 220 }}>
            <Search size={15} style={{ position: 'absolute', left: 14, top: 13, color: 'var(--text-3)' }} />
            <input
              className="input"
              style={{ paddingLeft: 38 }}
              placeholder="Search name or email…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (setPage(1), load())}
            />
          </div>
          <select className="select" style={{ width: 160 }} value={city} onChange={(e) => { setCity(e.target.value); setPage(1) }}>
            <option value="">All cities</option>
            {CITIES.map((c) => <option key={c}>{c}</option>)}
          </select>
          <select className="select" style={{ width: 170 }} value={minSpent} onChange={(e) => { setMinSpent(e.target.value); setPage(1) }}>
            <option value="">Any spend</option>
            <option value="1000">₹1,000+</option>
            <option value="5000">₹5,000+</option>
            <option value="10000">₹10,000+</option>
          </select>
        </div>
      </div>

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Customer</th><th>City</th><th>Age</th><th>Total spent</th><th>Orders</th><th>Last purchase</th><th>Tags</th></tr>
            </thead>
            <tbody>
              {data.items.map((c) => (
                <tr key={c.id} onClick={() => openDetail(c)} style={{ cursor: 'pointer' }}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{c.name}</div>
                    <div className="tiny">{c.email}</div>
                  </td>
                  <td>{c.city}</td>
                  <td>{c.age}</td>
                  <td style={{ fontWeight: 600, color: 'var(--teal)' }}>{inr(c.total_spent)}</td>
                  <td>{c.purchase_count}</td>
                  <td className="muted">{timeAgo(c.last_purchase_date)}</td>
                  <td>
                    <div className="row" style={{ gap: 5, flexWrap: 'wrap' }}>
                      {(c.tags || []).map((t) => <TagBadge key={t} tag={t} />)}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="spread mt-4">
          <span className="tiny">Page {page} of {totalPages}</span>
          <div className="row">
            <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
            <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        </div>
      </div>

      {selected && (
        <div className="modal-overlay" onClick={() => setSelected(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="spread mb-4">
              <div>
                <h2>{selected.name}</h2>
                <div className="sub" style={{ marginBottom: 0 }}>{selected.email} · {selected.phone}</div>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => setSelected(null)}><X size={14} /></button>
            </div>

            <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: 20 }}>
              <div className="card" style={{ padding: 16 }}>
                <div className="tiny mb-3">Total spent</div>
                <div style={{ fontFamily: 'Sora', fontSize: 20, fontWeight: 700, color: 'var(--teal)' }}>{inr(selected.total_spent)}</div>
              </div>
              <div className="card" style={{ padding: 16 }}>
                <div className="tiny mb-3">Orders</div>
                <div style={{ fontFamily: 'Sora', fontSize: 20, fontWeight: 700 }}>{selected.purchase_count}</div>
              </div>
              <div className="card" style={{ padding: 16 }}>
                <div className="tiny mb-3">Last purchase</div>
                <div style={{ fontFamily: 'Sora', fontSize: 20, fontWeight: 700 }}>{timeAgo(selected.last_purchase_date)}</div>
              </div>
            </div>

            <div className="section-title">Recent orders</div>
            {selected.loading ? <Loader /> : (selected.orders || []).length === 0 ? (
              <div className="empty">No order history loaded.</div>
            ) : (
              <table>
                <thead><tr><th>Product</th><th>Amount</th><th>Status</th><th>Date</th></tr></thead>
                <tbody>
                  {(selected.orders || []).map((o) => (
                    <tr key={o.id}>
                      <td>{o.product_name}</td>
                      <td>{inr(o.amount)}</td>
                      <td><StatusBadge status={o.status} /></td>
                      <td className="muted">{timeAgo(o.ordered_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </>
  )
}
