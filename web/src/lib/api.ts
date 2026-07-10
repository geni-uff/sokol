const API_BASE = '/api'

export interface LoginResponse {
  token: string
  user_id: string
}

export interface Case {
  id: string
  name: string
  legal_ref: string | null
  status: string
  reference_timezone: string
  created_at: string
}

export interface HealthResponse {
  status: string
  version: string
  services: Record<string, string>
}

export interface Event {
  id: string
  ts: string | null
  tz_original: string | null
  kind: string
  actor: string | null
  counterpart: string | null
  app: string | null
  ref_table: string | null
  ref_id: string | null
  summary: string
  meta: Record<string, unknown> | null
}

export interface TimelineResponse {
  events: Event[]
  total: number
  case_id: string
}

export interface CaseStats {
  events: number
  messages: number
  chunks: number
  entities: number
  media: number
}

export interface SearchResult {
  chunk_id: string
  text: string
  score: number
  ref: Record<string, unknown>
  message_ids: string[]
  source_type: string
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
  total: number
  mode: string
  embedding_model_id: string | null
}

export interface ChatResponse {
  response: string
  tool_calls: Array<{ name: string; arguments: string; round: number }>
  sources: Array<{ ref_table: string; ref_id: string; summary: string }>
  validation_warnings: string[]
}

function getToken(): string | null {
  return localStorage.getItem('sokol_token')
}

function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function apiLogin(username: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Login failed' }))
    throw new Error(err.detail || 'Credenciais inválidas')
  }
  return res.json()
}

export async function apiHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`)
  return res.json()
}

export async function apiListCases(): Promise<Case[]> {
  const res = await fetch(`${API_BASE}/cases`, { headers: authHeaders() })
  if (!res.ok) throw new Error('Failed to list cases')
  return res.json()
}

export async function apiCreateCase(name: string, legalRef?: string): Promise<Case> {
  const res = await fetch(`${API_BASE}/cases`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ name, legal_ref: legalRef }),
  })
  if (!res.ok) throw new Error('Failed to create case')
  return res.json()
}

export async function apiGetCase(caseId: string): Promise<Case> {
  const res = await fetch(`${API_BASE}/cases/${caseId}`, { headers: authHeaders() })
  if (!res.ok) throw new Error('Case not found')
  return res.json()
}

export async function apiSearch(
  caseId: string,
  query: string,
  mode: string = 'hybrid',
  k: number = 20,
): Promise<SearchResponse> {
  const res = await fetch(`${API_BASE}/search/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ case_id: caseId, query, mode, k }),
  })
  if (!res.ok) throw new Error('Search failed')
  return res.json()
}

export async function apiTimeline(
  caseId: string,
  limit: number = 100,
  offset: number = 0,
  kind?: string,
  app?: string,
): Promise<TimelineResponse> {
  const params = new URLSearchParams({ case_id: caseId, limit: String(limit), offset: String(offset) })
  if (kind) params.set('kind', kind)
  if (app) params.set('app', app)
  const res = await fetch(`${API_BASE}/events/timeline?${params}`, { headers: authHeaders() })
  if (!res.ok) return { events: [], total: 0, case_id: caseId }
  return res.json()
}

export async function apiCaseStats(caseId: string): Promise<CaseStats> {
  const res = await fetch(`${API_BASE}/events/stats?case_id=${caseId}`, { headers: authHeaders() })
  if (!res.ok) return { events: 0, messages: 0, chunks: 0, entities: 0, media: 0 }
  return res.json()
}

export async function apiChat(
  caseId: string,
  message: string,
): Promise<ChatResponse> {
  const res = await fetch(`${API_BASE}/chat/agent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ case_id: caseId, message }),
  })
  if (!res.ok) throw new Error('Chat failed')
  return res.json()
}

// ── Ops endpoints ──────────────────────────────────────────────────────────
export interface OpsOverview {
  services: Array<{ name: string; status: string; latency_ms?: number }>
  queues: Array<{ stage: string; pending: number; processing: number; failed: number }>
  alerts: string[]
  disk_usage?: { percent_used: number }
}

export async function apiOpsHealth(): Promise<OpsOverview> {
  const res = await fetch(`${API_BASE}/ops/health`, { headers: authHeaders() })
  if (!res.ok) throw new Error('Ops health failed')
  return res.json()
}

export async function apiOpsFailedJobs(limit = 20) {
  const res = await fetch(`${API_BASE}/ops/failed-jobs?limit=${limit}`, { headers: authHeaders() })
  if (!res.ok) return []
  return res.json()
}

// ── Bookmarks & Reports ───────────────────────────────────────────────────
export interface Bookmark {
  id: string
  case_id: string
  label: string
  note?: string
  color: string
  created_at: string
}

export async function apiListBookmarks(caseId: string): Promise<Bookmark[]> {
  const res = await fetch(`${API_BASE}/reports/bookmarks/${caseId}`, { headers: authHeaders() })
  if (!res.ok) return []
  return res.json()
}

export async function apiCreateBookmark(caseId: string, label: string, eventId?: string) {
  const res = await fetch(`${API_BASE}/reports/bookmarks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ case_id: caseId, label, event_id: eventId }),
  })
  if (!res.ok) throw new Error('Create bookmark failed')
  return res.json()
}

export async function apiGenerateReport(caseId: string, title: string) {
  const res = await fetch(`${API_BASE}/reports/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ case_id: caseId, title }),
  })
  if (!res.ok) throw new Error('Generate report failed')
  return res.json()
}

// ── Watchlists ────────────────────────────────────────────────────────────
export interface Watchlist {
  id: string
  name: string
  watch_type: string
  patterns: string[]
  is_active: boolean
  created_at: string
}

export async function apiListWatchlists(caseId: string): Promise<Watchlist[]> {
  const res = await fetch(`${API_BASE}/watchlists/${caseId}`, { headers: authHeaders() })
  if (!res.ok) return []
  return res.json()
}

export async function apiCreateWatchlist(caseId: string, name: string, watchType: string, patterns: string[]) {
  const res = await fetch(`${API_BASE}/watchlists/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ case_id: caseId, name, watch_type: watchType, patterns }),
  })
  if (!res.ok) throw new Error('Create watchlist failed')
  return res.json()
}

// ── Pendências ────────────────────────────────────────────────────────────
export interface Pendencia {
  id: string
  title: string
  description?: string
  priority: string
  status: string
  due_date?: string
  created_at: string
}

export async function apiListPendencias(caseId: string): Promise<Pendencia[]> {
  const res = await fetch(`${API_BASE}/pendencias/${caseId}`, { headers: authHeaders() })
  if (!res.ok) return []
  return res.json()
}

export async function apiCreatePendencia(caseId: string, title: string, priority = 'medium') {
  const res = await fetch(`${API_BASE}/pendencias/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ case_id: caseId, title, priority }),
  })
  if (!res.ok) throw new Error('Create pendencia failed')
  return res.json()
}

// ── Graph ─────────────────────────────────────────────────────────────────
export interface GraphData {
  nodes: Array<{ id: string; label: string; type: string; size?: number }>
  edges: Array<{ source: string; target: string; relationship: string; weight?: number }>
  stats: Record<string, unknown>
}

export async function apiGetGraph(caseId: string, maxNodes = 100): Promise<GraphData> {
  const res = await fetch(`${API_BASE}/graph/${caseId}?max_nodes=${maxNodes}`, { headers: authHeaders() })
  if (!res.ok) return { nodes: [], edges: [], stats: {} }
  return res.json()
}

// ── Playbooks ─────────────────────────────────────────────────────────────
export interface Playbook {
  id: string
  name: string
  description?: string
  category: string
  steps: Array<{ id: string; name: string; action: string }>
  is_template: boolean
  created_at: string
}

export async function apiListPlaybooks(): Promise<Playbook[]> {
  const res = await fetch(`${API_BASE}/playbooks/`, { headers: authHeaders() })
  if (!res.ok) return []
  return res.json()
}

export async function apiExecutePlaybook(playbookId: string, caseId: string) {
  const res = await fetch(`${API_BASE}/playbooks/${playbookId}/execute?case_id=${caseId}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error('Execute playbook failed')
  return res.json()
}

// ── Media ─────────────────────────────────────────────────────────────────
interface MediaItem {
  hash: string
  mime_type: string | null
  size_bytes: number | null
  thumbnail_available: boolean
  usage_count: number
}

export async function apiListMedia(caseId: string): Promise<MediaItem[]> {
  const res = await fetch(`${API_BASE}/media/${caseId}`, { headers: authHeaders() })
  if (!res.ok) return []
  return res.json()
}

// ── Vision Detection API ──────────────────────────────────────────────────
export interface DetectionItem {
  id: string
  media_hash: string
  model_name: string
  class_name: string
  class_id: number
  confidence: number
  bbox: number[]
  pipeline_version: string | null
  created_at: string
}

export interface DetectionStats {
  class_name: string
  count: number
  avg_confidence: number
  max_confidence: number
}

export interface MediaWithDetections extends MediaItem {
  detections: DetectionItem[]
  max_confidence: number
  detection_count: number
}

export async function apiListDetections(
  caseId: string,
  options?: {
    class_name?: string
    min_confidence?: number
    model_name?: string
    limit?: number
  }
): Promise<DetectionItem[]> {
  const params = new URLSearchParams()
  if (options?.class_name) params.set('class_name', options.class_name)
  if (options?.min_confidence !== undefined) params.set('min_confidence', String(options.min_confidence))
  if (options?.model_name) params.set('model_name', options.model_name)
  if (options?.limit) params.set('limit', String(options.limit))

  const res = await fetch(
    `${API_BASE}/vision/${caseId}/detections?${params}`,
    { headers: authHeaders() }
  )
  if (!res.ok) return []
  return res.json()
}

export async function apiDetectionStats(
  caseId: string,
  minConfidence = 0.0
): Promise<DetectionStats[]> {
  const res = await fetch(
    `${API_BASE}/vision/${caseId}/detections/stats?min_confidence=${minConfidence}`,
    { headers: authHeaders() }
  )
  if (!res.ok) return []
  return res.json()
}

export async function apiMediaWithDetections(
  caseId: string,
  className?: string,
  minConfidence = 0.0,
  limit = 100
): Promise<MediaWithDetections[]> {
  const params = new URLSearchParams({
    min_confidence: String(minConfidence),
    limit: String(limit),
  })
  if (className) params.set('class_name', className)

  const res = await fetch(
    `${API_BASE}/vision/${caseId}/media/detections?${params}`,
    { headers: authHeaders() }
  )
  if (!res.ok) return []
  return res.json()
}

export async function apiDetectionClasses(caseId: string): Promise<{ class_name: string; count: number }[]> {
  const res = await fetch(
    `${API_BASE}/vision/${caseId}/detections/classes`,
    { headers: authHeaders() }
  )
  if (!res.ok) return []
  return res.json()
}

export function logout() {
  localStorage.removeItem('sokol_token')
  localStorage.removeItem('sokol_user_id')
}

export function isLoggedIn(): boolean {
  return !!getToken()
}

// ── Faces ─────────────────────────────────────────────────────────────────
export interface FaceEmbedding {
  id: string
  case_id: string
  media_hash: string
  bbox: number[]
  confidence: number | null
  label: string | null
  age: number | null
  gender: string | null
  created_at: string
}

export interface FaceSearchResult {
  face_id: string
  case_id: string
  case_name: string
  media_hash: string
  bbox: number[]
  similarity: number
  label: string | null
}

export async function apiDetectFaces(caseId: string, mediaHash: string) {
  const res = await fetch(
    `${API_BASE}/faces/detect/${caseId}?media_hash=${mediaHash}`,
    { method: 'POST', headers: authHeaders() }
  )
  if (!res.ok) throw new Error('Detect faces failed')
  return res.json()
}

export async function apiListFaces(caseId: string, label?: string): Promise<FaceEmbedding[]> {
  const params = new URLSearchParams()
  if (label) params.set('label', label)
  const res = await fetch(`${API_BASE}/faces/${caseId}?${params}`, { headers: authHeaders() })
  if (!res.ok) return []
  return res.json()
}

export async function apiSearchFaces(
  caseId: string,
  faceId: string,
  threshold = 0.4,
  limit = 20
): Promise<FaceSearchResult[]> {
  const params = new URLSearchParams({ face_id: faceId, threshold: String(threshold), limit: String(limit) })
  const res = await fetch(`${API_BASE}/faces/${caseId}/search`, {
    method: 'POST',
    headers: authHeaders(),
    body: params,
  })
  if (!res.ok) return []
  return res.json()
}

export async function apiLabelFace(faceId: string, label: string) {
  const res = await fetch(`${API_BASE}/faces/${faceId}/label?label=${encodeURIComponent(label)}`, {
    method: 'PUT',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error('Label face failed')
  return res.json()
}
