import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  apiGetCase,
  apiSearch,
  apiChat,
  apiCaseStats,
  apiHealth,
  apiOpsHealth,
  apiListBookmarks,
  apiListWatchlists,
  apiListPendencias,
  apiGetGraph,
  apiListPlaybooks,
  apiExecutePlaybook,
  apiListMedia,
  apiLaunchPipeline,
  apiListPlates,
  apiLabelPlate,
  apiListTranscriptions,
  apiDetectionStats,
  apiMediaWithDetections,
  apiGenerateReport,
  type SearchResult,
  type CaseStats,
  type PlateDetection,
  type Transcription,
} from '@/lib/api'
import { useState } from 'react'
import {
  ChevronLeft,
  Search,
  MapPin,
  Clock,
  Database,
  Cpu,
  MessageSquare,
  FileText,
  BarChart3,
  Settings,
  Phone,
  Globe,
  Camera,
  Send,
  Loader2,
  AlertTriangle,
  CheckCircle,
  ExternalLink,
  Bookmark,
  Eye,
  AlertCircle,
  GitBranch,
  Play,
  Image,
  Scan,
  GitMerge,
  Crosshair,
  Sword,
  Bomb,
  Flame,
  User,
  Car,
  Smartphone,
  Mic,
  FileSearch,
  type LucideIcon,
} from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { Skeleton } from '@/components/ui/Skeleton'
import { cn } from '@/lib/cn'
import { healthLevelFromStatus, healthStatusLabel } from '@/lib/healthStatus'
import { MapTab } from '@/components/case/MapTab'
import { FacesTab } from '@/components/case/FacesTab'
import { OCRTab } from '@/components/case/OCRTab'
import { ReportsTab } from '@/components/case/ReportsTab'
import { CrossCaseTab } from '@/components/case/CrossCaseTab'

const NAV_ITEMS = [
  { icon: BarChart3, label: 'Timeline', id: 'timeline' },
  { icon: Search, label: 'Busca', id: 'search' },
  { icon: MessageSquare, label: 'Chat', id: 'chat' },
  { icon: Database, label: 'Dados', id: 'data' },
  { icon: Bookmark, label: 'Bookmarks', id: 'bookmarks' },
  { icon: Eye, label: 'Watchlists', id: 'watchlists' },
  { icon: AlertCircle, label: 'Pendências', id: 'pendencias' },
  { icon: Image, label: 'Mídia', id: 'media' },
  { icon: User, label: 'Rostos', id: 'faces' },
  { icon: Car, label: 'Placas', id: 'plates' },
  { icon: Mic, label: 'Voz', id: 'transcriptions' },
  { icon: FileSearch, label: 'OCR', id: 'ocr' },
  { icon: GitBranch, label: 'Grafo', id: 'graph' },
  { icon: Play, label: 'Playbooks', id: 'playbooks' },
  { icon: FileText, label: 'Relatórios', id: 'reports' },
  { icon: GitMerge, label: 'Análise Cruzada', id: 'cross-case' },
  { icon: Settings, label: 'Operação', id: 'ops' },
]

const KIND_ICONS: Record<string, LucideIcon> = {
  message: MessageSquare,
  call: Phone,
  location: MapPin,
  web_visit: Globe,
  media: Camera,
}

const KIND_COLORS: Record<string, string> = {
  message: 'text-blue-400',
  call: 'text-green-400',
  location: 'text-yellow-400',
  web_visit: 'text-purple-400',
  media: 'text-pink-400',
}

const BOOKMARK_DOT_COLORS: Record<string, string> = {
  red: 'bg-red-500',
  blue: 'bg-blue-500',
  green: 'bg-green-500',
  yellow: 'bg-yellow-500',
  purple: 'bg-purple-500',
  orange: 'bg-orange-500',
  pink: 'bg-pink-500',
}

const MEDIA_CLASS_ICONS: Record<string, LucideIcon> = {
  gun: Crosshair,
  knife: Sword,
  grenade: Bomb,
  explosive: Flame,
  person: User,
  car: Car,
  'cell phone': Smartphone,
}

const MEDIA_CLASSES = [
  { class_name: 'gun', label: 'Arma de fogo' },
  { class_name: 'knife', label: 'Faca' },
  { class_name: 'grenade', label: 'Granada' },
  { class_name: 'explosive', label: 'Explosivo' },
  { class_name: 'person', label: 'Pessoa' },
  { class_name: 'car', label: 'Carro' },
  { class_name: 'cell phone', label: 'Celular' },
]

const MEDIA_CLASS_SHORT: Record<string, string> = {
  gun: 'Arma',
  knife: 'Faca',
  grenade: 'Granada',
  explosive: 'Explosivo',
  person: 'Pessoa',
  car: 'Carro',
  'cell phone': 'Celular',
}

const INPUT_CLASS =
  'h-11 rounded-lg border border-border bg-surface-elevated px-4 text-sm text-foreground placeholder:text-dim transition-colors duration-150 hover:border-border-hover focus:border-border-hover focus:outline-none focus:ring-1 focus:ring-white/10 disabled:opacity-50'

const SELECT_CLASS = INPUT_CLASS + ' py-0'

export default function CaseDetail() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('timeline')

  const { data: caseData, isLoading } = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => apiGetCase(caseId!),
    enabled: !!caseId,
  })

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: apiHealth,
    refetchInterval: 30000,
  })

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['stats', caseId],
    queryFn: () => apiCaseStats(caseId!),
    enabled: !!caseId,
  })

  const healthLevel = healthLevelFromStatus(health?.status)

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-5 w-5 animate-spin text-muted" />
      </div>
    )
  }

  if (!caseData) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <EmptyState
          icon={AlertCircle}
          title="Caso não encontrado"
          action={
            <Button variant="secondary" onClick={() => navigate('/cases')}>
              Voltar aos casos
            </Button>
          }
        />
      </div>
    )
  }

  const isChat = activeTab === 'chat'

  return (
    <AppShell
      navItems={NAV_ITEMS}
      activeNavId={activeTab}
      onNavChange={setActiveTab}
      breadcrumbs={[
        { label: 'SOKOL', href: '/cases' },
        { label: 'Casos', href: '/cases' },
        { label: caseData.name },
      ]}
      backButton={
        <button
          type="button"
          onClick={() => navigate('/cases')}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-muted transition-colors duration-150 hover:bg-white/5 hover:text-foreground"
        >
          <ChevronLeft className="h-4 w-4" />
          Voltar
        </button>
      }
      footerStatus={{
        level: healthLevel,
        label: healthStatusLabel(healthLevel),
      }}
      hideFooter={isChat}
      bare={isChat}
      fullWidth={isChat}
      contentClassName={
        isChat ? 'flex min-h-0 flex-1 flex-col overflow-hidden p-0' : undefined
      }
    >
      {activeTab === 'timeline' && <MapTab caseId={caseId!} />}
      {activeTab === 'search' && <SearchTab caseId={caseId!} />}
      {activeTab === 'chat' && <ChatTab caseId={caseId!} />}
      {activeTab === 'data' && <DataTab stats={stats} isLoading={statsLoading} />}
      {activeTab === 'bookmarks' && <BookmarksTab caseId={caseId!} />}
      {activeTab === 'watchlists' && <WatchlistsTab caseId={caseId!} />}
      {activeTab === 'pendencias' && <PendenciasTab caseId={caseId!} />}
      {activeTab === 'media' && <MediaTab caseId={caseId!} />}
      {activeTab === 'faces' && <FacesTab caseId={caseId!} />}
      {activeTab === 'plates' && <PlatesTab caseId={caseId!} />}
      {activeTab === 'transcriptions' && <TranscriptionsTab caseId={caseId!} />}
      {activeTab === 'ocr' && <OCRTab caseId={caseId!} />}
      {activeTab === 'graph' && <GraphTab caseId={caseId!} />}
      {activeTab === 'playbooks' && <PlaybooksTab caseId={caseId!} />}
      {activeTab === 'reports' && <ReportsTab caseId={caseId!} />}
      {activeTab === 'cross-case' && <CrossCaseTab caseId={caseId!} />}
      {activeTab === 'ops' && <OpsTab />}
    </AppShell>
  )
}

function SearchTab({ caseId }: { caseId: string }) {
  const [query, setQuery] = useState('')
  const [mode] = useState('hybrid')
  const [results, setResults] = useState<SearchResult[] | null>(null)
  const [searching, setSearching] = useState(false)

  const handleSearch = async () => {
    if (!query) return
    setSearching(true)
    try {
      const res = await apiSearch(caseId, query, mode)
      setResults(res.results)
    } catch {
      setResults([])
    } finally {
      setSearching(false)
    }
  }

  return (
    <>
      <PageHeader
        icon={Search}
        title="Busca Avançada"
        description="Busque informações nos dados do caso"
      />

      <div className="mb-8 flex gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="Buscar nos dados do caso..."
          className={cn('flex-1', INPUT_CLASS)}
        />
        <Button className="h-11 shrink-0" onClick={handleSearch} disabled={!query || searching}>
          {searching ? 'Buscando...' : 'Buscar'}
        </Button>
      </div>

      {searching ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-muted" />
        </div>
      ) : !results || results.length === 0 ? (
        <EmptyState
          icon={Search}
          title={query ? 'Nenhum resultado encontrado' : 'Digite uma busca para começar'}
          description={query ? 'Tente outros termos ou sinônimos.' : undefined}
        />
      ) : (
        <div className="space-y-3">
          {results.map((r) => {
            const extended = r as SearchResult & { ts?: string; source?: string }
            return (
              <Card key={r.chunk_id} className="hover:border-border-hover">
                <CardContent>
                  <div className="mb-3 flex items-center gap-3">
                    <span className="font-mono text-xs text-dim">{extended.ts || 'N/A'}</span>
                    <Badge>{extended.source || 'N/A'}</Badge>
                    <span className="ml-auto font-mono text-xs font-medium text-foreground">
                      {Math.round(r.score * 100)}%
                    </span>
                  </div>
                  <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-foreground">
                    {r.text}
                  </p>
                  {r.message_ids.length > 0 && (
                    <p className="mt-2 text-xs text-dim">
                      {r.message_ids.length} mensagens vinculadas
                    </p>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </>
  )
}

interface ChatMessage {
  role: string
  content: string
  toolCalls?: Array<{ name: string; arguments: string; round: number }>
  sources?: Array<{ ref_table: string; ref_id: string; summary: string }>
}

function ChatTab({ caseId }: { caseId: string }) {
  const [input, setInput] = useState('')
  const [history, setHistory] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    setHistory((prev) => [...prev, { role: 'user', content: userMsg }])
    setLoading(true)

    try {
      const res = await apiChat(caseId, userMsg)
      setHistory((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: res.response,
          toolCalls: res.tool_calls,
          sources: res.sources,
        },
      ])
    } catch {
      setHistory((prev) => [...prev, { role: 'assistant', content: 'Erro ao processar pergunta.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="space-y-5 px-10 py-10 lg:px-14">
          {history.length === 0 && (
            <EmptyState
              icon={MessageSquare}
              title="Nenhuma pergunta ainda"
              description="Digite uma pergunta para começar a análise."
              size="compact"
            />
          )}
          {history.map((msg, i) => (
            <div key={i} className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
              <div
                className={cn(
                  'max-w-[80%] rounded-lg border px-5 py-4',
                  msg.role === 'user'
                    ? 'border-border bg-white/5 text-foreground'
                    : 'border-border bg-surface-elevated text-foreground',
                )}
              >
                <p className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content}</p>

                {msg.toolCalls && msg.toolCalls.length > 0 && (
                  <div className="mt-4 border-t border-border pt-4">
                    <p className="mb-2 text-xs font-medium text-muted">Ferramentas</p>
                    <div className="flex flex-wrap gap-2">
                      {msg.toolCalls.map((tc, j) => (
                        <Badge key={j} variant="accent">
                          {tc.name}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-4 border-t border-border pt-4">
                    <p className="mb-2 text-xs font-medium text-muted">
                      Fontes ({msg.sources.length})
                    </p>
                    <div className="space-y-2">
                      {msg.sources.slice(0, 5).map((src, j) => (
                        <div key={j} className="flex items-start gap-2 text-xs text-dim">
                          <ExternalLink className="mt-0.5 h-3 w-3 shrink-0" />
                          <span className="break-words">{src.summary}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="flex items-center gap-3 rounded-lg border border-border bg-surface-elevated px-5 py-4">
                <Loader2 className="h-4 w-4 animate-spin text-muted" />
                <span className="text-sm text-muted">Processando...</span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="shrink-0 border-t border-border bg-surface px-10 pt-6 pb-[max(2.5rem,calc(env(safe-area-inset-bottom,0px)+1.25rem))] lg:px-14">
        <div className="flex gap-4">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            placeholder="Faça uma pergunta..."
            disabled={loading}
            className={cn('min-w-0 flex-1', INPUT_CLASS)}
          />
          <Button
            variant="secondary"
            className="h-11 shrink-0 px-5"
            onClick={handleSend}
            disabled={loading || !input.trim()}
          >
            <Send className="h-4 w-4" />
            <span className="hidden sm:inline">Enviar</span>
          </Button>
        </div>
      </div>
    </div>
  )
}

function DataTab({ stats, isLoading }: { stats: CaseStats | undefined; isLoading: boolean }) {
  const items = [
    { label: 'Eventos', value: stats?.events ?? 0, icon: BarChart3 },
    { label: 'Mensagens', value: stats?.messages ?? 0, icon: MessageSquare },
    { label: 'Chunks', value: stats?.chunks ?? 0, icon: Database },
    { label: 'Entidades', value: stats?.entities ?? 0, icon: User },
    { label: 'Mídia', value: stats?.media ?? 0, icon: Camera },
  ]

  return (
    <>
      <PageHeader
        icon={Database}
        title="Dados do Caso"
        description="Resumo das informações armazenadas"
      />
      <div className="grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-5">
        {isLoading
          ? items.map(({ label }) => <Skeleton key={label} className="h-32 w-full" />)
          : items.map(({ label, value, icon: Icon }) => (
              <Card key={label}>
                <CardContent className="p-6">
                  <div className="mb-4 flex h-9 w-9 items-center justify-center rounded-lg bg-white/5">
                    <Icon className="h-4 w-4 text-muted" />
                  </div>
                  <div className="text-3xl font-semibold tabular-nums tracking-tight text-foreground">
                    {value.toLocaleString()}
                  </div>
                  <div className="mt-1 text-sm text-muted">{label}</div>
                </CardContent>
              </Card>
            ))}
      </div>
    </>
  )
}

function BookmarksTab({ caseId }: { caseId: string }) {
  const { data: bookmarks = [], isLoading } = useQuery({
    queryKey: ['bookmarks', caseId],
    queryFn: () => apiListBookmarks(caseId),
  })

  return (
    <>
      <PageHeader
        icon={Bookmark}
        title="Bookmarks"
        description={`${bookmarks.length} marcador(es)`}
      />
      {isLoading ? (
        <Loader2 className="h-5 w-5 animate-spin text-muted" />
      ) : bookmarks.length === 0 ? (
        <EmptyState icon={Bookmark} title="Nenhum bookmark ainda" />
      ) : (
        <div className="space-y-3">
          {bookmarks.map((b) => (
            <Card key={b.id}>
              <CardContent className="flex items-center gap-3 py-4">
                <span
                  className={cn(
                    'h-2.5 w-2.5 shrink-0 rounded-full',
                    BOOKMARK_DOT_COLORS[b.color] ?? 'bg-dim',
                  )}
                />
                <span className="text-sm font-medium text-foreground">{b.label}</span>
                <span className="ml-auto text-xs text-dim">
                  {new Date(b.created_at).toLocaleDateString('pt-BR')}
                </span>
              </CardContent>
              {b.note && (
                <CardContent className="border-t border-border pt-0">
                  <p className="text-sm text-muted">{b.note}</p>
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}
    </>
  )
}

function WatchlistsTab({ caseId }: { caseId: string }) {
  const { data: watchlists = [], isLoading } = useQuery({
    queryKey: ['watchlists', caseId],
    queryFn: () => apiListWatchlists(caseId),
  })

  return (
    <>
      <PageHeader
        icon={Eye}
        title="Watchlists"
        description={`${watchlists.length} lista(s)`}
      />
      {isLoading ? (
        <Loader2 className="h-5 w-5 animate-spin text-muted" />
      ) : watchlists.length === 0 ? (
        <EmptyState icon={Eye} title="Nenhuma watchlist ainda" />
      ) : (
        <div className="space-y-3">
          {watchlists.map((w) => (
            <Card key={w.id}>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-sm font-medium text-foreground">{w.name}</span>
                    <span className="ml-2 text-xs text-dim">({w.watch_type})</span>
                  </div>
                  <span
                    className={cn(
                      'h-2 w-2 rounded-full',
                      w.is_active ? 'bg-success' : 'bg-dim',
                    )}
                  />
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {w.patterns.slice(0, 3).map((p, i) => (
                    <Badge key={i}>{p}</Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  )
}

function PendenciasTab({ caseId }: { caseId: string }) {
  const { data: pendencias = [], isLoading } = useQuery({
    queryKey: ['pendencias', caseId],
    queryFn: () => apiListPendencias(caseId),
  })

  const priorityVariant: Record<string, 'danger' | 'warning' | 'default' | 'success'> = {
    critical: 'danger',
    high: 'warning',
    medium: 'default',
    low: 'success',
  }

  return (
    <>
      <PageHeader
        icon={AlertCircle}
        title="Pendências"
        description={`${pendencias.length} item(ns)`}
      />
      {isLoading ? (
        <Loader2 className="h-5 w-5 animate-spin text-muted" />
      ) : pendencias.length === 0 ? (
        <EmptyState icon={AlertCircle} title="Nenhuma pendência" />
      ) : (
        <div className="space-y-3">
          {pendencias.map((p) => (
            <Card key={p.id}>
              <CardContent className="flex items-center justify-between py-4">
                <div>
                  <span className="text-sm font-medium text-foreground">{p.title}</span>
                  <p
                    className={cn(
                      'mt-1 text-xs',
                      p.status === 'resolved' ? 'text-success' : 'text-dim',
                    )}
                  >
                    {p.status}
                  </p>
                </div>
                <Badge variant={priorityVariant[p.priority] ?? 'default'}>{p.priority}</Badge>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  )
}

function MediaTab({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient()
  const [selectedClass, setSelectedClass] = useState('')
  const [minConfidence, setMinConfidence] = useState(0.5)
  const [showOnlyDetections, setShowOnlyDetections] = useState(false)

  const { data: media = [], isLoading: mediaLoading } = useQuery({
    queryKey: ['media', caseId],
    queryFn: () => apiListMedia(caseId),
  })

  const { data: detectionStats = [] } = useQuery({
    queryKey: ['detectionStats', caseId, minConfidence],
    queryFn: () => apiDetectionStats(caseId, minConfidence),
  })

  const { data: mediaWithDetections = [], isLoading: detectionsLoading } = useQuery({
    queryKey: ['mediaWithDetections', caseId, selectedClass, minConfidence, showOnlyDetections],
    queryFn: () => apiMediaWithDetections(caseId, selectedClass || undefined, minConfidence),
    enabled: showOnlyDetections,
  })

  const pipelineMutation = useMutation({
    mutationFn: () => apiLaunchPipeline(caseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['media', caseId] })
      queryClient.invalidateQueries({ queryKey: ['plates', caseId] })
      queryClient.invalidateQueries({ queryKey: ['transcriptions', caseId] })
      queryClient.invalidateQueries({ queryKey: ['ocr', caseId] })
      queryClient.invalidateQueries({ queryKey: ['subjects', caseId] })
    },
  })

  const displayMedia = showOnlyDetections ? mediaWithDetections : media
  const isLoading = showOnlyDetections ? detectionsLoading : mediaLoading

  const getClassIcon = (className: string) => {
    const Icon = MEDIA_CLASS_ICONS[className] ?? Scan
    return <Icon className="h-3.5 w-3.5" />
  }

  const getClassLabel = (className: string) =>
    MEDIA_CLASSES.find((c) => c.class_name === className)?.label ?? className

  const getClassShort = (className: string) =>
    MEDIA_CLASS_SHORT[className] ?? getClassLabel(className)

  return (
    <>
      <PageHeader
        icon={Image}
        title="Mídia"
        description={`${media.length} arquivo(s)`}
        actions={
          <Button
            size="sm"
            variant="secondary"
            onClick={() => pipelineMutation.mutate()}
            disabled={pipelineMutation.isPending}
          >
            {pipelineMutation.isPending ? (
              <Loader2 className="mr-2 h-3 w-3 animate-spin" />
            ) : (
              <Scan className="mr-2 h-3 w-3" />
            )}
            Pipeline
          </Button>
        }
      />

      <Card className="mb-6">
        <CardContent>
          <div className="mb-4 flex items-center gap-2">
            <Scan className="h-4 w-4 text-muted" />
            <h3 className="text-sm font-medium text-foreground">Filtros de Detecção Visual</h3>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <label className="flex cursor-pointer items-center gap-2">
              <input
                type="checkbox"
                checked={showOnlyDetections}
                onChange={(e) => setShowOnlyDetections(e.target.checked)}
                className="h-4 w-4 rounded border-border accent-foreground"
              />
              <span className="text-sm text-muted">Apenas com detecções</span>
            </label>

            {showOnlyDetections && (
              <>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-dim">Classe:</span>
                  <select
                    value={selectedClass}
                    onChange={(e) => setSelectedClass(e.target.value)}
                    className={SELECT_CLASS}
                  >
                    <option value="">Todas</option>
                    {MEDIA_CLASSES.map((c) => (
                      <option key={c.class_name} value={c.class_name}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex min-w-[200px] flex-1 items-center gap-3">
                  <span className="whitespace-nowrap text-xs text-dim">
                    Certeza: {Math.round(minConfidence * 100)}%
                  </span>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={Math.round(minConfidence * 100)}
                    onChange={(e) => setMinConfidence(parseInt(e.target.value) / 100)}
                    className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-surface-elevated accent-foreground"
                  />
                </div>
              </>
            )}
          </div>

          {detectionStats.length > 0 && (
            <div className="mt-5 border-t border-border pt-5">
              <div className="flex flex-wrap gap-2">
                {detectionStats.map((stat) => (
                  <Button
                    key={stat.class_name}
                    variant={selectedClass === stat.class_name ? 'default' : 'secondary'}
                    size="sm"
                    title={getClassLabel(stat.class_name)}
                    onClick={() => {
                      setSelectedClass(stat.class_name === selectedClass ? '' : stat.class_name)
                      setShowOnlyDetections(true)
                    }}
                  >
                    {getClassIcon(stat.class_name)}
                    {getClassShort(stat.class_name)}
                    <span className="opacity-70">({stat.count})</span>
                  </Button>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-muted" />
        </div>
      ) : displayMedia.length === 0 ? (
        <EmptyState
          icon={Image}
          title={
            showOnlyDetections
              ? 'Nenhuma detecção encontrada'
              : 'Nenhuma mídia encontrada'
          }
        />
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-3">
          {displayMedia.map((m) => {
            const detections =
              'detections' in m && Array.isArray((m as { detections?: unknown[] }).detections)
                ? (m as { detections: Array<{ class_name: string; confidence: number }> })
                    .detections
                : []
            const detectionCount =
              'detection_count' in m ? (m as { detection_count: number }).detection_count : 0

            return (
              <Card key={m.hash} className="overflow-hidden hover:border-border-hover">
                <div className="relative flex aspect-square items-center justify-center overflow-hidden bg-surface-elevated">
                  <MediaThumbnail hash={m.hash} mimeType={m.mime_type} caseId={caseId} />

                  {detections.length > 0 && (
                    <div className="absolute right-2 top-2 flex flex-col items-end gap-1">
                      {detections.slice(0, 3).map((det, i) => (
                        <Badge
                          key={i}
                          variant={
                            ['gun', 'knife', 'grenade'].includes(det.class_name)
                              ? 'danger'
                              : det.class_name === 'explosive'
                                ? 'warning'
                                : 'accent'
                          }
                          className="gap-1"
                          title={getClassLabel(det.class_name)}
                        >
                          {getClassIcon(det.class_name)}
                          {Math.round(det.confidence * 100)}%
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
                <CardContent className="py-3">
                  <p className="truncate text-xs text-muted" title={m.mime_type ?? undefined}>
                    {m.mime_type}
                  </p>
                  <div className="mt-2 flex items-center justify-between text-xs text-dim">
                    <span>Usos: {m.usage_count}</span>
                    {m.size_bytes && <span>{(m.size_bytes / 1024).toFixed(0)} KB</span>}
                  </div>
                  {detectionCount > 0 && (
                    <p className="mt-2 flex items-center gap-1 text-xs text-muted">
                      <Scan className="h-3 w-3" />
                      {detectionCount} detecções
                    </p>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </>
  )
}

function MediaThumbnail({ hash, mimeType, caseId }: { hash: string; mimeType?: string | null; caseId: string }) {
  const [failed, setFailed] = useState(false)

  if (!mimeType?.startsWith('image/') || failed) {
    return <Camera className="h-8 w-8 text-dim" />
  }

  return (
    <img
      src={`/api/media/file/${hash}?case_id=${caseId}`}
      alt={mimeType}
      className="h-full w-full object-contain"
      loading="lazy"
      onError={() => setFailed(true)}
    />
  )
}

function GraphTab({ caseId }: { caseId: string }) {
  const { data: graph, isLoading } = useQuery({
    queryKey: ['graph', caseId],
    queryFn: () => apiGetGraph(caseId),
  })

  return (
    <>
      <PageHeader icon={GitBranch} title="Mapa de Relações" />
      {isLoading ? (
        <Loader2 className="h-5 w-5 animate-spin text-muted" />
      ) : (
        <Card>
          <CardContent className="py-12 text-center">
            <GitBranch className="mx-auto mb-3 h-8 w-8 text-dim" />
            <p className="text-sm text-muted">
              {graph?.nodes?.length || 0} nós, {graph?.edges?.length || 0} conexões
            </p>
            <p className="mt-1 text-xs text-dim">Visualização em grafo em breve</p>
          </CardContent>
        </Card>
      )}
    </>
  )
}

function PlaybooksTab({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient()
  const [executingId, setExecutingId] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<Record<string, unknown> | null>(null)

  const { data: playbooks = [], isLoading } = useQuery({
    queryKey: ['playbooks'],
    queryFn: () => apiListPlaybooks(),
  })

  const executeMutation = useMutation({
    mutationFn: (playbookId: string) => apiExecutePlaybook(playbookId, caseId),
    onMutate: (playbookId) => {
      setExecutingId(playbookId)
      setLastResult(null)
    },
    onSuccess: (data) => {
      setLastResult(data as Record<string, unknown>)
      setExecutingId(null)
      queryClient.invalidateQueries({ queryKey: ['playbooks'] })
    },
    onError: () => {
      setExecutingId(null)
    },
  })

  return (
    <>
      <PageHeader icon={Play} title="Playbooks" description={`${playbooks.length} disponível(is)`} />
      {isLoading ? (
        <Loader2 className="h-5 w-5 animate-spin text-muted" />
      ) : playbooks.length === 0 ? (
        <EmptyState icon={Play} title="Nenhum playbook disponível" />
      ) : (
        <div className="space-y-3">
          {playbooks.map((p) => (
            <Card key={p.id}>
              <CardContent className="py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-sm font-medium text-foreground">{p.name}</span>
                    <span className="ml-2 text-xs text-dim">({p.category})</span>
                    <p className="mt-1 text-xs text-dim">{p.steps.length} passos</p>
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => executeMutation.mutate(p.id)}
                    disabled={executingId === p.id}
                  >
                    {executingId === p.id ? (
                      <>
                        <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                        Executando...
                      </>
                    ) : (
                      'Executar'
                    )}
                  </Button>
                </div>

                {lastResult && lastResult.playbook_id === p.id && (
                  <div className="mt-4 rounded-lg border border-border bg-surface p-4">
                    <div className="mb-3 flex items-center gap-2 text-xs">
                      <CheckCircle className="h-3.5 w-3.5 text-success" />
                      <span className="font-medium text-foreground">
                        Executado em{' '}
                        {new Date(String(lastResult.completed_at)).toLocaleString('pt-BR')}
                      </span>
                    </div>

                    {lastResult.results && typeof lastResult.results === 'object' && (
                      <div className="space-y-2">
                        {Object.entries(lastResult.results as Record<string, Record<string, unknown>>).map(
                          ([stepId, result]) => (
                            <div
                              key={stepId}
                              className="flex items-start gap-3 rounded-md border border-border p-3"
                            >
                              {result.status === 'ok' ? (
                                <CheckCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
                              ) : (
                                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger" />
                              )}
                              <div className="flex-1">
                                <p className="text-xs font-medium text-foreground">
                                  Passo {stepId}
                                </p>
                                <p className="mt-0.5 text-xs text-dim">
                                  {result.output && typeof result.output === 'object'
                                    ? (result.output as Record<string, unknown>).count !== undefined
                                      ? `${String((result.output as Record<string, unknown>).count)} resultados`
                                      : String((result.output as Record<string, unknown>).message || 'OK')
                                    : 'OK'}
                                </p>
                              </div>
                            </div>
                          ),
                        )}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  )
}

function OpsTab() {
  const { data: ops, isLoading } = useQuery({
    queryKey: ['ops-health'],
    queryFn: () => apiOpsHealth(),
    refetchInterval: 30000,
  })

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin text-muted" />
      </div>
    )
  }

  return (
    <>
      <PageHeader icon={Cpu} title="Operação" description="Status dos serviços" />

      {ops?.alerts && ops.alerts.length > 0 && (
        <Card className="mb-6 border-warning/20 bg-warning/5">
          <CardContent className="py-4">
            {ops.alerts.map((a, i) => (
              <p key={i} className="text-sm text-warning">
                {a}
              </p>
            ))}
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {ops?.services?.map((s) => (
          <Card key={s.name}>
            <CardContent className="flex items-center justify-between py-4">
              <div className="flex items-center gap-3">
                {s.status === 'ok' ? (
                  <CheckCircle className="h-4 w-4 text-success" />
                ) : (
                  <AlertTriangle className="h-4 w-4 text-warning" />
                )}
                <span className="text-sm capitalize text-foreground">{s.name}</span>
              </div>
              <div className="flex items-center gap-3">
                {s.latency_ms && (
                  <span className="font-mono text-xs text-dim">{s.latency_ms}ms</span>
                )}
                <Badge variant={s.status === 'ok' ? 'success' : 'warning'}>{s.status}</Badge>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {ops?.disk_usage && (
        <Card className="mt-6">
          <CardContent>
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-medium text-foreground">Disco</span>
              <span className="font-mono text-xs text-dim">{ops.disk_usage.percent_used}%</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-elevated">
              <div
                className={cn(
                  'h-full rounded-full transition-all duration-300',
                  ops.disk_usage.percent_used > 90 ? 'bg-danger' : 'bg-foreground',
                )}
                style={{ width: `${ops.disk_usage.percent_used}%` }}
              />
            </div>
          </CardContent>
        </Card>
      )}
    </>
  )
}

function PlatesTab({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient()
  const [labelInput, setLabelInput] = useState('')

  const { data: plates = [], isLoading } = useQuery({
    queryKey: ['plates', caseId],
    queryFn: () => apiListPlates(caseId),
  })

  const labelMutation = useMutation({
    mutationFn: ({ id, label }: { id: string; label: string }) => apiLabelPlate(id, label),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plates', caseId] })
      setLabelInput('')
    },
  })

  return (
    <>
      <PageHeader icon={Car} title="Placas" description={`${plates.length} placa(s) detectada(s)`} />
      {isLoading ? (
        <Loader2 className="h-5 w-5 animate-spin text-muted" />
      ) : plates.length === 0 ? (
        <EmptyState icon={Car} title="Nenhuma placa detectada" description="Execute o pipeline de detecção para analisar imagens" />
      ) : (
        <div className="space-y-3">
          {plates.map((plate) => (
            <Card key={plate.id}>
              <CardContent className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded bg-surface flex items-center justify-center">
                    <Car className="h-5 w-5 text-dim" />
                  </div>
                  <div>
                    <span className="text-sm font-mono font-medium text-foreground">{plate.plate_text}</span>
                    {plate.label && <span className="ml-2 text-xs text-dim">({plate.label})</span>}
                    <p className="text-[10px] text-dim">
                      Confiança: {plate.confidence ? `${(plate.confidence * 100).toFixed(0)}%` : 'N/A'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={labelInput}
                    onChange={(e) => setLabelInput(e.target.value)}
                    placeholder="Label"
                    className="w-32 rounded-md border border-border bg-surface px-2 py-1 text-xs"
                    onKeyDown={(e) => e.key === 'Enter' && labelInput.trim() && labelMutation.mutate({ id: plate.id, label: labelInput.trim() })}
                  />
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => labelInput.trim() && labelMutation.mutate({ id: plate.id, label: labelInput.trim() })}
                    disabled={!labelInput.trim()}
                  >
                    Rotular
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  )
}

function TranscriptionsTab({ caseId }: { caseId: string }) {
  const [search, setSearch] = useState('')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const { data: transcriptions = [], isLoading } = useQuery({
    queryKey: ['transcriptions', caseId, search],
    queryFn: () => apiListTranscriptions(caseId, search || undefined),
  })

  return (
    <>
      <PageHeader icon={Mic} title="Transcrições de Voz" description={`${transcriptions.length} transcrição(ões)`} />
      <div className="mb-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar no texto transcrito..."
          className={cn('w-full', INPUT_CLASS)}
        />
      </div>
      {isLoading ? (
        <Loader2 className="h-5 w-5 animate-spin text-muted" />
      ) : transcriptions.length === 0 ? (
        <EmptyState icon={Mic} title="Nenhuma transcrição" description="Execute o pipeline de detecção para transcrever áudios" />
      ) : (
        <div className="space-y-3">
          {transcriptions.map((t) => {
            const isExpanded = expandedId === t.id
            return (
              <Card key={t.id} className="hover:border-border-hover">
                <CardContent className="py-3">
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 text-left"
                    onClick={() => setExpandedId(isExpanded ? null : t.id)}
                  >
                    <Mic className="h-4 w-4 shrink-0 text-dim" />
                    <span className="text-[10px] text-dim">
                      {t.language || 'unknown'} | {new Date(t.created_at).toLocaleString('pt-BR')}
                    </span>
                  </button>
                  <p className={cn(
                    'mt-2 text-sm text-foreground leading-relaxed',
                    !isExpanded && 'line-clamp-3',
                  )}>
                    {t.text}
                  </p>
                  {t.text.length > 200 && (
                    <button
                      type="button"
                      className="mt-1 text-xs text-accent hover:underline"
                      onClick={() => setExpandedId(isExpanded ? null : t.id)}
                    >
                      {isExpanded ? 'Recolher' : 'Expandir'}
                    </button>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </>
  )
}
