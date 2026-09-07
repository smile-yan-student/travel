const BASE = import.meta.env.VITE_API_BASE || '/api'

// 从 localStorage 取 token（与 src/utils/user.js 保持一致）
const TOKEN_KEY = 'travel_token'
function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}
function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem('travel_username')
}

async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    // 401：token 失效，清除本地登录态
    if (res.status === 401) {
      clearToken()
    }
    throw new Error(text || `请求失败(${res.status})`)
  }
  return res.json()
}

/** 自动带 token 的请求（从 localStorage 取），401 自动清除登录态 */
function authedRequest(path, options = {}) {
  const token = getToken()
  return request(path, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, ...(options.headers || {}) },
  })
}

// ---- 公开接口（无需登录） ----
export function getStatus() {
  return request('/status')
}
export function getSiteConfig() {
  return request('/site/config')
}

// ---- 核心业务接口（需登录，自动带 token） ----
export function createPlan(payload) {
  return authedRequest('/plan', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function chatPlan(messages) {
  return authedRequest('/chat/plan', {
    method: 'POST',
    body: JSON.stringify({ messages }),
  })
}

export function getRoute(origin, destination, trafficMode = '混合') {
  return authedRequest('/route', {
    method: 'POST',
    body: JSON.stringify({ origin, destination, traffic_mode: trafficMode }),
  })
}

export function exploreAround(payload) {
  return authedRequest('/explore', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function poiSearch(city, categories) {
  const params = new URLSearchParams({ city, categories })
  return authedRequest(`/poi/search?${params.toString()}`, { method: 'POST' })
}

// ---- 认证接口 ----
export function register(payload) {
  return request('/auth/register', { method: 'POST', body: JSON.stringify(payload) })
}
export function checkUsername(username) {
  return request(`/auth/check-username?username=${encodeURIComponent(username)}`)
}
export function checkEmail(email) {
  return request(`/auth/check-email?email=${encodeURIComponent(email)}`)
}
export function login(payload) {
  return request('/auth/login', { method: 'POST', body: JSON.stringify(payload) })
}
// ---- 邮箱验证码登录/注册 ----
export function sendEmailCode(payload) {
  return request('/auth/email/send-code', { method: 'POST', body: JSON.stringify(payload) })
}
export function emailLogin(payload) {
  return request('/auth/email/login', { method: 'POST', body: JSON.stringify(payload) })
}
export function authMe() {
  return authedRequest('/auth/me')
}

// ---- 出行足迹（需登录） ----
export function reportTrip(payload) {
  return authedRequest('/trips', { method: 'POST', body: JSON.stringify(payload) })
}
export function getTrips() {
  return authedRequest('/trips')
}

// ---- 对话历史（登录用户） ----
export function listConversations(params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
  ).toString()
  return authedRequest(`/conversations${qs ? `?${qs}` : ''}`)
}
export function conversationStream(params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
  ).toString()
  return authedRequest(`/conversations/stream${qs ? `?${qs}` : ''}`)
}
export function getConversation(id) {
  return authedRequest(`/conversations/${id}`)
}
export function saveConversation(payload) {
  return authedRequest('/conversations', { method: 'POST', body: JSON.stringify(payload) })
}
export function deleteConversation(id) {
  return authedRequest(`/conversations/${id}`, { method: 'DELETE' })
}

// ---- 管理后台 /api/admin/* ----
export function adminLogin(payload) {
  return request('/admin/login', { method: 'POST', body: JSON.stringify(payload) })
}
export function adminRequest(path, options = {}, token) {
  // 后台用独立 token，不走 localStorage 的 C 端 token
  return request(`/admin${path}`, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, ...(options.headers || {}) },
  })
}

// ---- RAG人文知识库（需登录） ----
export function getPoiKnowledge(poiName) {
  return authedRequest(`/rag/poi/${encodeURIComponent(poiName)}/knowledge`)
}
export function getPoiCardInfo(poiName) {
  return authedRequest(`/rag/poi/${encodeURIComponent(poiName)}/card-info`)
}
export function generatePoiExplanation(poiName, style = 'default') {
  return authedRequest('/rag/poi/explain', {
    method: 'POST',
    body: JSON.stringify({ poi_name: poiName, style }),
  })
}
export function ragQa(poiName, question) {
  return authedRequest('/rag/poi/qa', {
    method: 'POST',
    body: JSON.stringify({ poi_name: poiName, question }),
  })
}
export function ragSearch(query, poiName = null, nResults = 5) {
  const params = new URLSearchParams({ query, n_results: nResults })
  if (poiName) params.set('poi_name', poiName)
  return authedRequest(`/rag/search?${params.toString()}`)
}
export function getRagStats() {
  return authedRequest('/rag/admin/stats')
}
export function importAllPois() {
  return authedRequest('/rag/admin/import-all', {
    method: 'POST',
  })
}
export function importPoi(poiName) {
  return authedRequest('/rag/admin/import-poi', {
    method: 'POST',
    body: JSON.stringify({ poi_name: poiName }),
  })
}
export function deletePoiKnowledge(poiName) {
  return authedRequest(`/rag/admin/poi/${encodeURIComponent(poiName)}`, {
    method: 'DELETE',
  })
}

// ---- 用户画像（需登录） ----
export function getMyProfile() {
  return authedRequest('/profile/me')
}
export function getMyPreferences() {
  return authedRequest('/profile/preferences')
}
export function getMyUsage() {
  return authedRequest('/profile/usage')
}
export function learnFromPlan(planParams) {
  return authedRequest('/profile/learn/plan', {
    method: 'POST',
    body: JSON.stringify({ plan_params: planParams }),
  })
}
export function learnFromModification(modType, modParams = {}) {
  return authedRequest('/profile/learn/modification', {
    method: 'POST',
    body: JSON.stringify({ mod_type: modType, mod_params: modParams }),
  })
}
export function getPlanParamsWithPreferences(baseParams = {}) {
  return authedRequest('/profile/plan-params', {
    method: 'POST',
    body: JSON.stringify({ base_params: baseParams }),
  })
}
export function getProfileStats() {
  return authedRequest('/profile/stats')
}

// ---- 行程工作记忆（需登录） ----
export function createItinerarySession(sessionId = '') {
  return authedRequest('/itinerary/session', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  })
}
export function getItinerarySession(sessionId) {
  return authedRequest(`/itinerary/session/${sessionId}`)
}
export function deleteItinerarySession(sessionId) {
  return authedRequest(`/itinerary/session/${sessionId}`, { method: 'DELETE' })
}
export function saveItineraryPlan(sessionId, plan, originalParams = {}) {
  return authedRequest('/itinerary/plan', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, plan, original_params: originalParams }),
  })
}
export function getItineraryPlan(sessionId) {
  return authedRequest(`/itinerary/${sessionId}/plan`)
}
export function applyItineraryModification(sessionId, modType, params = {}, userInstruction = '') {
  return authedRequest('/itinerary/modify', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, mod_type: modType, params, user_instruction: userInstruction }),
  })
}
export function getItineraryModifications(sessionId, limit = 20) {
  return authedRequest(`/itinerary/${sessionId}/modifications?limit=${limit}`)
}

// ---- 评价体系接口 ----
export function createTripReview(payload) {
  return authedRequest('/reviews/trip', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
export function getTripReviews(tripId, page = 1, pageSize = 10) {
  return request(`/reviews/trip/${tripId}?page=${page}&page_size=${pageSize}`)
}
export function getMyTripReviews(page = 1, pageSize = 10) {
  return authedRequest(`/reviews/trip/user/my?page=${page}&page_size=${pageSize}`)
}
export function createPoiReview(payload) {
  return authedRequest('/reviews/poi', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
export function getPoiReviews(poiId, page = 1, pageSize = 10) {
  return request(`/reviews/poi/${poiId}?page=${page}&page_size=${pageSize}`)
}
export function createFeedback(payload) {
  return authedRequest('/reviews/feedback', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
export function getMyFeedback(page = 1, pageSize = 10) {
  return authedRequest(`/reviews/feedback/my?page=${page}&page_size=${pageSize}`)
}
