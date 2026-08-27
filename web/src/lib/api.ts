const API_BASE = '/api'

export interface LoginResponse {
  token: string
  user_id: string
  is_platform_admin?: boolean
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

async function throwApiError(res: Response, fallback: string): Promise<never> {
  const err = (await res.json().catch(() => ({ detail: fallback }))) as { detail?: unknown }
  const detail = err.detail
  let msg = fallback
  if (typeof detail === 'string') msg = detail
  else if (Array.isArray(detail)) {
    msg = detail
      .map((d) =>
        typeof d === 'object' && d && 'msg' in d ? String((d as { msg: string }).msg) : String(d),
      )
      .join('; ')
  }
  throw new Error(msg || fallback)
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
  if (!res.ok) await throwApiError(res, 'Busca falhou')
  return res.json()
}

export async function apiTimeline(
  caseId: string,
  limit: number = 100,
  offset: number = 0,
  kind?: string,
  app?: string,
  startDate?: string,
  endDate?: string,
): Promise<TimelineResponse> {
  const params = new URLSearchParams({ case_id: caseId, limit: String(limit), offset: String(offset) })
  if (kind) params.set('kind', kind)
  if (app) params.set('app', app)
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  const res = await fetch(`${API_BASE}/events/timeline?${params}`, { headers: authHeaders() })
  if (!res.ok) return { events: [], total: 0, case_id: caseId }
  return res.json()
}

export async function apiEventApps(caseId: string): Promise<string[]> {
  const res = await fetch(`${API_BASE}/events/apps?case_id=${caseId}`, { headers: authHeaders() })
  if (!res.ok) return []
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
  if (!res.ok) await throwApiError(res, 'Falha no Agent')
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
  event_id?: string | null
  event_summary?: string | null
  event_kind?: string | null
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
  if (!res.ok) await throwApiError(res, 'Falha ao criar bookmark')
  return res.json()
}

export async function apiDeleteBookmark(bookmarkId: string) {
  const res = await fetch(`${API_BASE}/reports/bookmarks/${bookmarkId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) await throwApiError(res, 'Falha ao remover bookmark')
  return res.json()
}

export async function apiGenerateReport(caseId: string, title: string) {
  const res = await fetch(`${API_BASE}/reports?case_id=${encodeURIComponent(caseId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ title }),
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
  if (!res.ok) await throwApiError(res, 'Falha ao criar watchlist')
  return res.json()
}

export async function apiDeleteWatchlist(watchlistId: string) {
  const res = await fetch(`${API_BASE}/watchlists/${watchlistId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) await throwApiError(res, 'Falha ao remover watchlist')
  return res.json()
}

export async function apiToggleWatchlist(watchlistId: string) {
  const res = await fetch(`${API_BASE}/watchlists/${watchlistId}/toggle`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) await throwApiError(res, 'Falha ao alterar watchlist')
  return res.json() as Promise<{ is_active: boolean }>
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

export interface MediaListResponse {
  items: MediaItem[]
  total: number
  cache_files?: number
}

export async function apiListMedia(
  caseId: string,
  opts?: { limit?: number; offset?: number; mimeType?: string },
): Promise<MediaListResponse> {
  const params = new URLSearchParams()
  if (opts?.limit) params.set('limit', String(opts.limit))
  if (opts?.offset) params.set('offset', String(opts.offset))
  if (opts?.mimeType) params.set('mime_type', opts.mimeType)
  const res = await fetch(`${API_BASE}/media/${caseId}?${params}`, { headers: authHeaders() })
  if (!res.ok) return { items: [], total: 0, cache_files: 0 }
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

// ── Pipeline ─────────────────────────────────────────────────────────────
export interface PipelineJob {
  job_id: string
  kind: string
  status: string
  progress: number
  message: string
}

export async function apiLaunchPipeline(
  caseId: string,
  opts?: { mode?: 'sample' | 'all'; sample_images?: number; sample_audios?: number },
): Promise<{
  jobs_launched: number
  job_ids: Record<string, string>
  skipped?: Record<string, string>
  warnings?: string[]
  mode?: string
  image_count?: number
  audio_count?: number
  missing_files?: number
}> {
  const params = new URLSearchParams()
  params.set('mode', opts?.mode ?? 'sample')
  if (opts?.sample_images) params.set('sample_images', String(opts.sample_images))
  if (opts?.sample_audios) params.set('sample_audios', String(opts.sample_audios))
  const res = await fetch(`${API_BASE}/detect/pipeline/${caseId}?${params}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) await throwApiError(res, 'Falha ao iniciar pipeline')
  return res.json()
}

export async function apiBackfillChunks(caseId: string): Promise<{ chunks_created: number }> {
  const res = await fetch(`${API_BASE}/detect/chunk/${caseId}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) await throwApiError(res, 'Falha ao indexar texto')
  return res.json()
}

export async function apiPipelineStatus(caseId: string): Promise<PipelineJob[]> {
  const res = await fetch(`${API_BASE}/detect/status/${caseId}`, { headers: authHeaders() })
  if (!res.ok) return []
  return res.json()
}

// ── Plates ───────────────────────────────────────────────────────────────
export interface PlateDetection {
  id: string
  case_id: string
  media_hash: string
  plate_text: string
  confidence: number | null
  label: string | null
  created_at: string
}

export async function apiListPlates(caseId: string): Promise<PlateDetection[]> {
  const res = await fetch(`${API_BASE}/plates/${caseId}`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`Placas falhou (${res.status})`)
  return res.json()
}

export async function apiLabelPlate(plateId: string, label: string) {
  const res = await fetch(`${API_BASE}/plates/${plateId}/label?label=${encodeURIComponent(label)}`, {
    method: 'PUT',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error('Label plate failed')
  return res.json()
}

// ── Transcriptions ───────────────────────────────────────────────────────
export interface Transcription {
  id: string
  case_id: string
  media_hash: string
  text: string
  language: string | null
  created_at: string
  mime_type?: string | null
  size_bytes?: number | null
  file_name?: string | null
  source_member?: string | null
  original_path?: string | null
  document_title?: string | null
  app?: string | null
  sender?: string | null
  counterpart?: string | null
  chat_id?: string | null
  whatsapp_id?: string | null
}

export async function apiListTranscriptions(caseId: string, search?: string): Promise<Transcription[]> {
  const params = new URLSearchParams()
  if (search) params.set('search', search)
  const res = await fetch(`${API_BASE}/transcriptions/${caseId}?${params}`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`Transcrições falhou (${res.status})`)
  return res.json()
}

// ── OCR Results ────────────────────────────────────────────────────────
export interface OCRResult {
  id: string
  case_id: string
  media_hash: string
  mime_type: string | null
  text: string
  confidence: number | null
  language: string | null
  lines: Array<{ text: string; bbox: number[]; confidence: number }>
  created_at: string
}

export async function apiListOCR(caseId: string, search?: string): Promise<OCRResult[]> {
  const params = new URLSearchParams()
  if (search) params.set('search', search)
  const res = await fetch(`${API_BASE}/ocr/${caseId}?${params}`, { headers: authHeaders() })
  if (!res.ok) return []
  return res.json()
}

// ── Face Subjects ──────────────────────────────────────────────────────
export interface FaceSubject {
  subject_id: string
  label: string | null
  face_count: number
  representative_face: FaceEmbedding
  faces: FaceEmbedding[]
}

export async function apiListSubjects(caseId: string, threshold = 0.55): Promise<FaceSubject[]> {
  const params = new URLSearchParams({ threshold: String(threshold) })
  const res = await fetch(`${API_BASE}/faces/${caseId}/subjects?${params}`, { headers: authHeaders() })
  if (!res.ok) return []
  return res.json()
}

// ── Geo Events ────────────────────────────────────────────────────────
export interface GeoEvent {
  id: string
  ts: string | null
  summary: string
  lat: number
  lon: number
  meta: Record<string, unknown> | null
}

export async function apiGeoEvents(caseId: string): Promise<GeoEvent[]> {
  const res = await fetch(`${API_BASE}/events/geo?case_id=${caseId}`, { headers: authHeaders() })
  if (!res.ok) return []
  return res.json()
}

// ── Cross-Case Analysis ───────────────────────────────────────────────
export interface SharedSelector {
  value: string
  cases: Record<string, number>
  confidence: number
}

export interface SharedLocation {
  case_id_a: string
  case_id_b: string
  event_id_a: string
  event_id_b: string
  ts_a: string | null
  ts_b: string | null
  distance_m: number
  confidence: number
}

export interface CrossCaseResult {
  case_ids: string[]
  shared_phones: SharedSelector[]
  shared_emails: SharedSelector[]
  shared_locations: SharedLocation[]
  similarity_score: number
  indicator_note: string
}

export async function apiCrossCase(
  caseIds: string[],
  justification: string,
): Promise<CrossCaseResult> {
  const res = await fetch(`${API_BASE}/analysis/cross-case`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ case_ids: caseIds, justification }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Error ${res.status}`)
  }
  return res.json()
}

// ── Entity Resolution ───────────────────────────────────────────────────

export interface ResolutionSuggestion {
  entity_a: string
  entity_b: string
  kind_a: string
  kind_b: string
  display_a: string | null
  display_b: string | null
  value_a?: string | null
  value_b?: string | null
  reason: string
  confidence: number
  indicator_note: string
}

export interface ResolveSuggestionsResponse {
  case_id: string
  suggestions: ResolutionSuggestion[]
  total: number
}

export async function apiSuggestResolutions(caseId: string): Promise<ResolveSuggestionsResponse> {
  const res = await fetch(`${API_BASE}/entities/resolve?case_id=${caseId}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Error ${res.status}`)
  }
  return res.json()
}

export async function apiConfirmResolution(
  entityId: string,
  identityId: string,
): Promise<{ link_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/entities/${entityId}/resolve-to`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ identity_id: identityId, confirmed_by_user: true }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Error ${res.status}`)
  }
  return res.json()
}

export async function apiRejectResolution(
  entityAId: string,
  entityBId: string,
): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/entities/${entityAId}/reject-resolution`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ entity_b_id: entityBId }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Error ${res.status}`)
  }
  return res.json()
}

export interface AgendaContact {
  id: string
  name: string
  phones: string[]
  emails: string[]
}

export async function apiListAgenda(caseId: string): Promise<{
  case_id: string
  contacts: AgendaContact[]
  total: number
}> {
  const res = await fetch(`${API_BASE}/entities/agenda/${caseId}`, { headers: authHeaders() })
  if (!res.ok) return { case_id: caseId, contacts: [], total: 0 }
  return res.json()
}

export async function apiBackfillContacts(caseId: string): Promise<{
  persons_created: number
  links_created: number
}> {
  const res = await fetch(`${API_BASE}/entities/backfill-contacts/${caseId}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) await throwApiError(res, 'Falha ao materializar contatos')
  return res.json()
}

// ── Conversations / Messages ────────────────────────────────────────────

export function getMediaUrl(hash: string, caseId: string): string {
  const token = getToken()
  return `${API_BASE}/media/file/${hash}?case_id=${caseId}${token ? `&token=${token}` : ''}`
}

export function getThumbnailUrl(hash: string, caseId: string): string {
  const token = getToken()
  return `${API_BASE}/media/thumbnail/${hash}?case_id=${caseId}${token ? `&token=${token}` : ''}`
}

export interface ChatSummary {
  chat_id: string | null
  app: string | null
  participant: string | null
  message_count: number
  first_ts: string | null
  last_ts: string | null
}

export interface MessageItem {
  id: string
  app: string | null
  chat_id: string | null
  sender: string | null
  counterpart: string | null
  ts: string | null
  direction: string | null
  text: string | null
  media_hash: string | null
  is_forwarded: boolean | null
}

export interface MessagesResponse {
  messages: MessageItem[]
  total: number
  case_id: string
}

export async function apiListChats(caseId: string, app?: string): Promise<ChatSummary[]> {
  const params = new URLSearchParams({ case_id: caseId })
  if (app) params.set('app', app)
  const res = await fetch(`${API_BASE}/conversations/chats?${params}`, { headers: authHeaders() })
  if (!res.ok) return []
  return res.json()
}

export async function apiListMessages(
  caseId: string,
  opts?: { app?: string; chatId?: string; q?: string; limit?: number; offset?: number },
): Promise<MessagesResponse> {
  const params = new URLSearchParams({ case_id: caseId })
  if (opts?.app) params.set('app', opts.app)
  if (opts?.chatId) params.set('chat_id', opts.chatId)
  if (opts?.q) params.set('q', opts.q)
  if (opts?.limit) params.set('limit', String(opts.limit))
  if (opts?.offset) params.set('offset', String(opts.offset))
  const res = await fetch(`${API_BASE}/conversations/messages?${params}`, { headers: authHeaders() })
  if (!res.ok) return { messages: [], total: 0, case_id: caseId }
  return res.json()
}

// ── Analytics (heatmaps, contact frequency) ─────────────────────────────

export interface HeatmapCell {
  dow: number
  hour: number
  count: number
}

export interface ActivityHeatmap {
  case_id: string
  timezone: string
  cells: HeatmapCell[]
  total_events: number
}

export interface LocationCell {
  lat: number
  lon: number
  count: number
}

export interface LocationHeatmap {
  case_id: string
  points: LocationCell[]
  total: number
}

export interface MonthCount {
  month: string
  count: number
}

export interface ContactFrequency {
  counterpart: string
  total: number
  kinds: Record<string, number>
  monthly: MonthCount[]
}

export async function apiActivityHeatmap(caseId: string, kind?: string): Promise<ActivityHeatmap> {
  const params = kind ? `?kind=${kind}` : ''
  const res = await fetch(`${API_BASE}/analytics/${caseId}/activity-heatmap${params}`, { headers: authHeaders() })
  if (!res.ok) return { case_id: caseId, timezone: '', cells: [], total_events: 0 }
  return res.json()
}

export async function apiLocationHeatmap(caseId: string): Promise<LocationHeatmap> {
  const res = await fetch(`${API_BASE}/analytics/${caseId}/location-heatmap`, { headers: authHeaders() })
  if (!res.ok) return { case_id: caseId, points: [], total: 0 }
  return res.json()
}

export async function apiContactFrequency(caseId: string, top = 15): Promise<ContactFrequency[]> {
  const res = await fetch(`${API_BASE}/analytics/${caseId}/contact-frequency?top=${top}`, { headers: authHeaders() })
  if (!res.ok) return []
  const data = await res.json()
  return data.contacts ?? []
}

// ── Anomalies ───────────────────────────────────────────────────────────

export interface Anomaly {
  id: string
  case_id: string
  kind: string
  severity: string
  score: number
  explanation: string
  ref_event_ids: string[]
  dismissed: boolean
  created_at: string
  indicator_note: string
}

export async function apiAnalyzeAnomalies(caseId: string): Promise<{ created: number; by_kind: Record<string, number> }> {
  const res = await fetch(`${API_BASE}/anomalies/${caseId}/analyze`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Error ${res.status}`)
  }
  return res.json()
}

export async function apiListAnomalies(caseId: string, dismissed = false): Promise<Anomaly[]> {
  const res = await fetch(`${API_BASE}/anomalies/${caseId}?dismissed=${dismissed}`, { headers: authHeaders() })
  if (!res.ok) return []
  return res.json()
}

export async function apiDismissAnomaly(anomalyId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/anomalies/${anomalyId}/dismiss`, {
    method: 'PATCH',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(`Error ${res.status}`)
}

export interface WatchlistHitsSummary {
  total_hits: number
  unacknowledged: number
  watchlists_with_hits: number
}

export async function apiWatchlistHitsSummary(caseId: string): Promise<WatchlistHitsSummary> {
  const res = await fetch(`${API_BASE}/watchlists/${caseId}/hits/summary`, { headers: authHeaders() })
  if (!res.ok) return { total_hits: 0, unacknowledged: 0, watchlists_with_hits: 0 }
  return res.json()
}

// ── Comments (working notes — never in laudo) ─────────────────────────────
export type CommentTargetKind = 'case' | 'event' | 'media'

export interface CaseComment {
  id: string
  case_id: string
  author_user_id: string
  author_username: string
  target_kind: CommentTargetKind
  target_id: string | null
  body: string
  created_at: string
  edited_at: string | null
}

export interface CommentListResponse {
  comments: CaseComment[]
  viewer_role: string
  viewer_user_id: string
  can_write: boolean
}

export async function apiListComments(
  caseId: string,
  opts?: { target_kind?: CommentTargetKind; target_id?: string },
): Promise<CommentListResponse> {
  const params = new URLSearchParams()
  if (opts?.target_kind) params.set('target_kind', opts.target_kind)
  if (opts?.target_id) params.set('target_id', opts.target_id)
  const qs = params.toString()
  const res = await fetch(`${API_BASE}/comments/${caseId}${qs ? `?${qs}` : ''}`, {
    headers: authHeaders(),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Error ${res.status}`)
  }
  return res.json()
}

export async function apiCreateComment(
  caseId: string,
  body: { target_kind: CommentTargetKind; target_id?: string | null; body: string },
): Promise<CaseComment> {
  const res = await fetch(`${API_BASE}/comments/${caseId}`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Error ${res.status}`)
  }
  return res.json()
}

export async function apiUpdateComment(commentId: string, body: string): Promise<CaseComment> {
  const res = await fetch(`${API_BASE}/comments/${commentId}`, {
    method: 'PATCH',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ body }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Error ${res.status}`)
  }
  return res.json()
}

export async function apiDeleteComment(commentId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/comments/${commentId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Error ${res.status}`)
  }
}

export type BulkExportKind =
  | 'timeline.csv'
  | 'contacts.vcf'
  | 'contacts.csv'
  | 'locations.kml'
  | 'zip'

/** Download a bulk export file for the case (triggers browser save dialog). */
export async function apiDownloadCaseExport(
  caseId: string,
  kind: BulkExportKind,
  opts?: { startDate?: string; endDate?: string },
): Promise<void> {
  let url: string
  let filename: string
  switch (kind) {
    case 'timeline.csv': {
      const params = new URLSearchParams()
      if (opts?.startDate) params.set('start_date', opts.startDate)
      if (opts?.endDate) params.set('end_date', opts.endDate)
      const qs = params.toString()
      url = `${API_BASE}/export/${caseId}/timeline.csv${qs ? `?${qs}` : ''}`
      filename = `case_${caseId}_timeline.csv`
      break
    }
    case 'contacts.vcf':
      url = `${API_BASE}/export/${caseId}/contacts.vcf`
      filename = `case_${caseId}_contacts.vcf`
      break
    case 'contacts.csv':
      url = `${API_BASE}/export/${caseId}/contacts.csv`
      filename = `case_${caseId}_contacts.csv`
      break
    case 'locations.kml':
      url = `${API_BASE}/export/${caseId}/locations.kml`
      filename = `case_${caseId}_locations.kml`
      break
    case 'zip':
      url = `${API_BASE}/cases/${caseId}/export`
      filename = `case_${caseId}.zip`
      break
    default: {
      const _exhaustive: never = kind
      throw new Error(`Unknown export kind: ${_exhaustive}`)
    }
  }

  const res = await fetch(url, { headers: authHeaders() })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail ?? `Error ${res.status}`)
  }
  const blob = await res.blob()
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(link.href)
}

// ── Admin / plataforma ───────────────────────────────────────────────────
export interface AdminModelInfo {
  id: string
  provider: string
  model: string
  enabled?: boolean
  active?: boolean
}

export interface AdminModelsResponse {
  llm_models: AdminModelInfo[]
  embedding_models: AdminModelInfo[]
  rerank_models: AdminModelInfo[]
  effective_llm_model?: string
  llm_n_ctx?: number
}

export async function apiAdminModels(): Promise<AdminModelsResponse> {
  const res = await fetch(`${API_BASE}/admin/models`, { headers: authHeaders() })
  if (!res.ok) await throwApiError(res, 'Falha ao listar modelos')
  return res.json()
}

export async function apiSwitchLlm(modelId: string) {
  const res = await fetch(`${API_BASE}/admin/models/llm/switch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ model_id: modelId }),
  })
  if (!res.ok) await throwApiError(res, 'Falha ao trocar LLM')
  return res.json()
}

export async function apiSwitchEmbed(modelId: string) {
  const res = await fetch(`${API_BASE}/admin/models/embedding/switch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ model_id: modelId }),
  })
  if (!res.ok) await throwApiError(res, 'Falha ao trocar embedding')
  return res.json()
}

export async function apiSwitchReranker(modelId: string) {
  const res = await fetch(`${API_BASE}/admin/models/reranker/switch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ model_id: modelId }),
  })
  if (!res.ok) await throwApiError(res, 'Falha ao trocar reranker')
  return res.json()
}

export async function apiListBackups(): Promise<{ backups: Array<Record<string, unknown>> }> {
  const res = await fetch(`${API_BASE}/backup/list`, { headers: authHeaders() })
  if (!res.ok) await throwApiError(res, 'Falha ao listar backups')
  return res.json()
}

export async function apiCreateBackup() {
  const res = await fetch(`${API_BASE}/backup`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) await throwApiError(res, 'Falha ao criar backup')
  return res.json()
}

export async function apiBackupSchedule(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/backup/schedule`, { headers: authHeaders() })
  if (!res.ok) await throwApiError(res, 'Falha ao ler agendamento')
  return res.json()
}

export async function apiSetBackupSchedule(body: {
  frequency: string
  retention_days: number
  enabled: boolean
}) {
  const res = await fetch(`${API_BASE}/backup/schedule`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) await throwApiError(res, 'Falha ao agendar backup')
  return res.json()
}

export async function apiRestoreBackup(backupFile: string) {
  const res = await fetch(`${API_BASE}/backup/restore`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ backup_file: backupFile, confirm: true }),
  })
  if (!res.ok) await throwApiError(res, 'Falha no restore')
  return res.json()
}

export async function apiAuditVerify(): Promise<{ valid: boolean; errors: unknown[] }> {
  const res = await fetch(`${API_BASE}/admin/audit/verify`, { headers: authHeaders() })
  if (!res.ok) await throwApiError(res, 'Falha na verificação de auditoria')
  return res.json()
}

export interface InboxFile {
  path: string
  name: string
  size: number
  is_dir: boolean
  ready?: boolean
  not_ready_reason?: string | null
}

export interface IngestJob {
  job_id: string
  document_id: string | null
  status: string
  inbox_ref: string | null
  error: string | null
  created_at: string
  updated_at: string | null
  parse_coverage?: {
    model_type_counts?: Record<string, number>
    ignored_model_types?: Record<string, number>
    fs_walk?: Record<string, number>
  } | null
}

export interface BatchIngestResponse {
  results: Array<{ job_id: string; document_id: string; status: string }>
  total: number
  queued: number
}

export async function apiListInbox(prefix?: string, kind: 'ufdr' | 'pdf' | 'all' = 'ufdr'): Promise<InboxFile[]> {
  const params = new URLSearchParams()
  if (prefix) params.set('prefix', prefix)
  params.set('kind', kind)
  const res = await fetch(`${API_BASE}/ingest/inbox?${params.toString()}`, {
    headers: authHeaders(),
  })
  if (!res.ok) await throwApiError(res, 'Falha ao listar o inbox')
  return res.json()
}

export async function apiListIngestJobs(caseId: string): Promise<IngestJob[]> {
  const res = await fetch(`${API_BASE}/ingest/jobs?case_id=${caseId}&limit=50`, {
    headers: authHeaders(),
  })
  if (!res.ok) await throwApiError(res, 'Falha ao listar jobs de ingestão')
  return res.json()
}

export async function apiBatchIngest(
  caseId: string,
  inboxRefs: string[],
  sourceType = 'ufdr',
): Promise<BatchIngestResponse> {
  const res = await fetch(`${API_BASE}/ingest/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      case_id: caseId,
      source_type: sourceType,
      inbox_refs: inboxRefs,
    }),
  })
  if (!res.ok) await throwApiError(res, 'Falha ao enfileirar ingestão')
  return res.json()
}
