import axios from 'axios'

// In dev, Vite proxies /api -> http://localhost:8000 (see vite.config.js).
// In production set VITE_API_URL to your hosted backend URL.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
})

// ---------- customers ----------
// GET /api/customers — one page of customers; params: page, limit, city, min_spent, search.
export const getCustomers = (params = {}) =>
  api.get('/api/customers/', { params }).then((r) => r.data)

// GET /api/customers/:id — one customer with their last 10 orders.
export const getCustomer = (id) =>
  api.get(`/api/customers/${id}`).then((r) => r.data)

// ---------- segments ----------
// GET /api/segments — all saved segments.
export const getSegments = () => api.get('/api/segments/').then((r) => r.data)

// POST /api/segments — save a segment ({name, description, rules, ai_generated}).
export const createSegment = (payload) =>
  api.post('/api/segments/', payload).then((r) => r.data)

// POST /api/segments/preview — count + sample customers for some rules, without saving.
export const previewSegment = (rules) =>
  api.post('/api/segments/preview', rules).then((r) => r.data)

// DELETE /api/segments/:id — remove a segment.
export const deleteSegment = (id) =>
  api.delete(`/api/segments/${id}`).then((r) => r.data)

// ---------- campaigns ----------
// GET /api/campaigns — all campaigns (no stats).
export const getCampaigns = () => api.get('/api/campaigns/').then((r) => r.data)

// GET /api/campaigns/:id — one campaign.
export const getCampaign = (id) =>
  api.get(`/api/campaigns/${id}`).then((r) => r.data)

// POST /api/campaigns — save a draft campaign.
export const createCampaign = (payload) =>
  api.post('/api/campaigns/', payload).then((r) => r.data)

// POST /api/campaigns/:id/launch — start sending a draft campaign (returns immediately).
export const launchCampaign = (id) =>
  api.post(`/api/campaigns/${id}/launch`).then((r) => r.data)

// GET /api/campaigns/:id/stats — funnel counts and rates for one campaign.
export const getCampaignStats = (id) =>
  api.get(`/api/campaigns/${id}/stats`).then((r) => r.data)

// ---------- analytics ----------
// GET /api/analytics/overview — dashboard KPI numbers.
export const getOverview = () =>
  api.get('/api/analytics/overview').then((r) => r.data)

// GET /api/analytics/campaigns — every campaign with its funnel stats.
export const getAnalyticsCampaigns = () =>
  api.get('/api/analytics/campaigns').then((r) => r.data)

// ---------- ai ----------
// POST /api/ai/build-segment — plain English -> segment rules + preview.
export const aiBuildSegment = (prompt) =>
  api.post('/api/ai/build-segment', { prompt }).then((r) => r.data)

// POST /api/ai/write-message — 3 AI-written message variants.
export const aiWriteMessage = (payload) =>
  api.post('/api/ai/write-message', payload).then((r) => r.data)

// GET /api/ai/insights/:id — AI insights and recommendations for a campaign.
export const aiInsights = (campaignId) =>
  api.get(`/api/ai/insights/${campaignId}`).then((r) => r.data)

// POST /api/ai/create-campaign — one sentence -> saved segment + draft campaign.
export const aiCreateCampaign = (intent) =>
  api.post('/api/ai/create-campaign', { intent }).then((r) => r.data)

export default api
