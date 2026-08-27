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
  apiListPlaybooks,
  apiExecutePlaybook,
  apiListMedia,
  apiLaunchPipeline,
  apiPipelineStatus,
  apiListPlates,
  apiLabelPlate,
  apiListTranscriptions,
  apiDetectionStats,
  apiMediaWithDetections,
  apiGenerateReport,
  apiWatchlistHitsSummary,
  apiCreateBookmark,
  apiDeleteBookmark,
  apiCreateWatchlist,
  apiDeleteWatchlist,
  apiToggleWatchlist,
  apiBackfillChunks,
  apiEmbedStatus,
  apiLaunchEmbed,
  apiListAgenda,
  apiBackfillContacts,
  getMediaUrl,
  getThumbnailUrl,
  type SearchResult,
  type CaseStats,
  type PlateDetection,
  type Transcription,
} from '@/lib/api'
import { useEffect, useState } from 'react'
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
  Users,
  MessagesSquare,
  Crosshair,
  Sword,
  Bomb,
  Flame,
  User,
  Car,
  Smartphone,
  Mic,
  FileSearch,
  Plus,
  Trash2,
  Mail,
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
import { EntityResolutionTab } from '@/components/case/EntityResolutionTab'
import { ConversasTab } from '@/components/case/ConversasTab'
import { AnalyticsTab } from '@/components/case/AnalyticsTab'
import { CaseCommentsPanel } from '@/components/case/CaseCommentsPanel'
import { GraphTab } from '@/components/case/GraphTab'
import { IngestPanel } from '@/components/case/IngestPanel'
import { MediaLightbox, isExpandableMedia } from '@/components/case/MediaLightbox'

const NAV_ITEMS = [
  { icon: BarChart3, label: 'Timeline', id: 'timeline' },
  { icon: Search, label: 'Busca', id: 'search' },
  { icon: MessageSquare, label: 'Chat', id: 'chat' },
  { icon: MessagesSquare, label: 'Conversas', id: 'conversas' },
  { icon: Database, label: 'Dados', id: 'data' },
  { icon: Bookmark, label: 'Bookmarks', id: 'bookmarks' },
  { icon: Eye, label: 'Watchlists', id: 'watchlists' },
  { icon: AlertCircle, label: 'Pendências', id: 'pendencias' },
  { icon: Image, label: 'Mídia', id: 'media' },
  { icon: User, label: 'Rostos', id: 'faces' },
  { icon: Car, label: 'Placas', id: 'plates' },
  { icon: Mic, label: 'Voz', id: 'transcriptions' },
  { icon: FileSearch, label: 'OCR', id: 'ocr' },
  { icon: BarChart3, label: 'Analytics', id: 'analytics' },
  { icon: GitBranch, label: 'Grafo', id: 'graph' },
  { icon: Play, label: 'Playbooks', id: 'playbooks' },
  { icon: FileText, label: 'Relatórios', id: 'reports' },
  { icon: GitMerge, label: 'Análise Cruzada', id: 'cross-case' },
  { icon: Users, label: 'Identidades', id: 'entity-resolution' },
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
      {activeTab === 'conversas' && <ConversasTab caseId={caseId!} />}
      {activeTab === 'data' && (
        <DataTab caseId={caseId!} stats={stats} isLoading={statsLoading} />
      )}
      {activeTab === 'bookmarks' && <BookmarksTab caseId={caseId!} />}
      {activeTab === 'watchlists' && <WatchlistsTab caseId={caseId!} />}
      {activeTab === 'pendencias' && <PendenciasTab caseId={caseId!} />}
      {activeTab === 'media' && <MediaTab caseId={caseId!} />}
      {activeTab === 'faces' && <FacesTab caseId={caseId!} />}
      {activeTab === 'plates' && <PlatesTab caseId={caseId!} />}
      {activeTab === 'transcriptions' && <TranscriptionsTab caseId={caseId!} />}
      {activeTab === 'ocr' && <OCRTab caseId={caseId!} />}
      {activeTab === 'analytics' && <AnalyticsTab caseId={caseId!} />}
      {activeTab === 'graph' && <GraphTab caseId={caseId!} />}
      {activeTab === 'playbooks' && (
        <PlaybooksTab caseId={caseId!} onOpenReports={() => setActiveTab('reports')} />
      )}
      {activeTab === 'reports' && <ReportsTab caseId={caseId!} />}
      {activeTab === 'cross-case' && <CrossCaseTab caseId={caseId!} />}
      {activeTab === 'entity-resolution' && <EntityResolutionTab caseId={caseId!} />}
      {activeTab === 'ops' && <OpsTab caseId={caseId!} />}
    </AppShell>
  )
}

function embedBusy(status?: string) {
  return status === 'pending' || status === 'running'
}

function EmbedIndexControls({ caseId, compact = false }: { caseId: string; compact?: boolean }) {
  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryKey: ['embedStatus', caseId],
    queryFn: () => apiEmbedStatus(caseId),
    refetchInterval: (q) => (embedBusy(q.state.data?.status) ? 3000 : false),
  })
  const mut = useMutation({
    mutationFn: () => apiLaunchEmbed(caseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['embedStatus', caseId] })
      queryClient.invalidateQueries({ queryKey: ['stats', caseId] })
    },
  })
  const chunksEmb = data?.chunks_embedded ?? 0
  const chunksTot = data?.chunks_total ?? 0
  const eventsEmb = data?.events_embedded ?? 0
  const eventsTot = data?.events_total ?? 0
  const vectorsReady = chunksTot > 0 && chunksEmb >= chunksTot && eventsEmb >= eventsTot
  const label = embedBusy(data?.status)
    ? `Indexando ${data?.stage ?? ''} ${data?.done ?? 0}/${data?.total ?? 0}`
    : vectorsReady
      ? 'Vetores prontos'
      : 'Indexar vetores'

  return (
    <div className={cn('flex flex-wrap items-center gap-3', compact && 'text-xs')}>
      <Button
        variant="secondary"
        size="sm"
        disabled={mut.isPending || embedBusy(data?.status) || vectorsReady}
        onClick={() => mut.mutate()}
      >
        {mut.isPending || embedBusy(data?.status) ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : null}
        {label}
      </Button>
      <span className="text-xs text-dim">
        chunks {chunksEmb.toLocaleString()}/{chunksTot.toLocaleString()} · eventos{' '}
        {eventsEmb.toLocaleString()}/{eventsTot.toLocaleString()}
      </span>
      {data?.error ? <span className="text-xs text-danger">{data.error}</span> : null}
      {mut.isError ? (
        <span className="text-xs text-danger">
          {mut.error instanceof Error ? mut.error.message : 'Falha ao enfileirar'}
        </span>
      ) : null}
    </div>
  )
}

function SearchTab({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient()
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState('lexical')
  const [results, setResults] = useState<SearchResult[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState('')
  const [indexMsg, setIndexMsg] = useState('')

  const handleSearch = async () => {
    if (!query) return
    setSearching(true)
    setError('')
    try {
      const res = await apiSearch(caseId, query, mode)
      setResults(res.results)
    } catch (err: unknown) {
      setResults(null)
      setError(err instanceof Error ? err.message : 'Falha na busca')
    } finally {
      setSearching(false)
    }
  }

  const handleIndex = async () => {
    setIndexMsg('')
    setError('')
    try {
      const res = await apiBackfillChunks(caseId)
      setIndexMsg(`${res.chunks_created} chunks no índice textual`)
      queryClient.invalidateQueries({ queryKey: ['stats', caseId] })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Falha ao indexar')
    }
  }

  return (
    <>
      <PageHeader
        icon={Search}
        title="Busca Avançada"
        description="Busque informações nos dados do caso"
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <EmbedIndexControls caseId={caseId} />
            <Button variant="secondary" size="sm" onClick={handleIndex}>
              Indexar texto
            </Button>
          </div>
        }
      />

      <div className="mb-8 flex flex-wrap gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="Buscar nos dados do caso..."
          className={cn('min-w-0 flex-1', INPUT_CLASS)}
        />
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          className={cn('h-11 shrink-0 rounded-lg border border-border bg-surface-elevated px-3 text-sm')}
        >
          <option value="lexical">lexical</option>
          <option value="exact">exata</option>
          <option value="hybrid">híbrida</option>
        </select>
        <Button className="h-11 shrink-0" onClick={handleSearch} disabled={!query || searching}>
          {searching ? 'Buscando...' : 'Buscar'}
        </Button>
      </div>

      {error && (
        <Card className="mb-6 border-danger/20">
          <CardContent className="py-3 text-sm text-danger">{error}</CardContent>
        </Card>
      )}
      {indexMsg && <p className="mb-4 text-xs text-dim">{indexMsg}</p>}

      {searching ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-muted" />
        </div>
      ) : error ? null : results === null ? (
        <EmptyState
          icon={Search}
          title="Digite uma busca para começar"
        />
      ) : results.length === 0 ? (
        <EmptyState
          icon={Search}
          title="Nenhum resultado encontrado"
          description="Tente outros termos ou indexe o texto do caso."
        />
      ) : (
        <div className="space-y-3">
          {results.map((r) => (
            <Card key={r.chunk_id} className="hover:border-border-hover">
              <CardContent>
                <div className="mb-3 flex items-center gap-3">
                  <Badge>{r.source_type || 'N/A'}</Badge>
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
          ))}
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
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Erro ao processar pergunta.'
      setHistory((prev) => [...prev, { role: 'assistant', content: msg }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="space-y-5 px-10 py-10 lg:px-14">
          {history.length === 0 && (
            <div className="space-y-6">
              <EmbedIndexControls caseId={caseId} />
              <EmptyState
                icon={MessageSquare}
                title="Nenhuma pergunta ainda"
                description="O Agent busca no caso via SQL e vetores. Sem vetores, só encontra o que as ferramentas SQL devolverem (até 50 linhas)."
                size="compact"
              />
            </div>
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

function DataTab({
  caseId,
  stats,
  isLoading,
}: {
  caseId: string
  stats: CaseStats | undefined
  isLoading: boolean
}) {
  const queryClient = useQueryClient()
  const items = [
    { label: 'Eventos', value: stats?.events ?? 0, icon: BarChart3 },
    { label: 'Mensagens', value: stats?.messages ?? 0, icon: MessageSquare },
    { label: 'Chunks', value: stats?.chunks ?? 0, icon: Database },
    { label: 'Entidades', value: stats?.entities ?? 0, icon: User },
    { label: 'Mídia', value: stats?.media ?? 0, icon: Camera },
  ]

  const { data: agenda, isLoading: agendaLoading } = useQuery({
    queryKey: ['agenda', caseId],
    queryFn: () => apiListAgenda(caseId),
  })
  const contacts = agenda?.contacts ?? []

  const backfillMut = useMutation({
    mutationFn: () => apiBackfillContacts(caseId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agenda', caseId] })
      queryClient.invalidateQueries({ queryKey: ['stats', caseId] })
    },
  })

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

      <Card className="mt-8">
        <CardContent className="py-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-medium text-foreground">Contatos de agenda</h3>
              <p className="mt-1 text-xs text-dim">
                {agendaLoading
                  ? 'Carregando…'
                  : `${contacts.length.toLocaleString()} pessoa(s) com telefone ou e-mail (WhatsApp/iCloud)`}
              </p>
            </div>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => backfillMut.mutate()}
              disabled={backfillMut.isPending}
            >
              {backfillMut.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Users className="h-3.5 w-3.5" />
              )}
              Materializar
            </Button>
          </div>
          {agendaLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : contacts.length === 0 ? (
            <EmptyState
              icon={User}
              title="Nenhum contato de agenda"
              description="Telefones e e-mails do WhatsApp/iCloud viram pessoas após materializar."
            />
          ) : (
            <div className="max-h-[28rem] space-y-2 overflow-y-auto pr-1">
              {contacts.map((c) => (
                <div
                  key={c.id}
                  className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-border px-4 py-3"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{c.name}</p>
                    <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                      {c.phones.map((p) => (
                        <span key={p} className="inline-flex items-center gap-1">
                          <Phone className="h-3 w-3 text-dim" />
                          {p}
                        </span>
                      ))}
                      {c.emails.map((e) => (
                        <span key={e} className="inline-flex items-center gap-1">
                          <Mail className="h-3 w-3 text-dim" />
                          {e}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="mt-8">
        <CardContent className="py-5">
          <CaseCommentsPanel
            caseId={caseId}
            targetKind="case"
            title="Notas do caso"
          />
          <p className="mt-3 text-xs text-dim">
            Notas internas de trabalho — não entram em laudo. Use Bookmark se o conteúdo for
            para o relatório.
          </p>
        </CardContent>
      </Card>
    </>
  )
}

function BookmarksTab({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient()
  const [label, setLabel] = useState('')
  const [formError, setFormError] = useState('')

  const { data: bookmarks = [], isLoading } = useQuery({
    queryKey: ['bookmarks', caseId],
    queryFn: () => apiListBookmarks(caseId),
  })

  const createMut = useMutation({
    mutationFn: () => apiCreateBookmark(caseId, label.trim()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bookmarks', caseId] })
      setLabel('')
      setFormError('')
    },
    onError: (e: Error) => setFormError(e.message),
  })

  const deleteMut = useMutation({
    mutationFn: apiDeleteBookmark,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['bookmarks', caseId] }),
    onError: (e: Error) => setFormError(e.message),
  })

  return (
    <>
      <PageHeader
        icon={Bookmark}
        title="Bookmarks"
        description={`${bookmarks.length} marcador(es)`}
      />
      <div className="mb-6 flex gap-3">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Novo bookmark..."
          className={cn('flex-1', INPUT_CLASS)}
          onKeyDown={(e) => e.key === 'Enter' && label.trim() && createMut.mutate()}
        />
        <Button
          onClick={() => createMut.mutate()}
          disabled={!label.trim() || createMut.isPending}
        >
          <Plus className="h-4 w-4" />
          Adicionar
        </Button>
      </div>
      {formError && <p className="mb-4 text-sm text-danger">{formError}</p>}
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
                {b.event_id && (
                  <span className="max-w-md truncate text-xs text-muted">
                    {b.event_kind ? `${b.event_kind}: ` : ''}
                    {b.event_summary || 'ligado a um evento'}
                  </span>
                )}
                <span className="ml-auto text-xs text-dim">
                  {new Date(b.created_at).toLocaleDateString('pt-BR')}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => deleteMut.mutate(b.id)}
                  title="Remover"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
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
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [patterns, setPatterns] = useState('')
  const [formError, setFormError] = useState('')

  const { data: watchlists = [], isLoading } = useQuery({
    queryKey: ['watchlists', caseId],
    queryFn: () => apiListWatchlists(caseId),
  })

  const { data: hitsSummary } = useQuery({
    queryKey: ['watchlist-hits-summary', caseId],
    queryFn: () => apiWatchlistHitsSummary(caseId),
    refetchInterval: 30_000,
  })

  const createMut = useMutation({
    mutationFn: () =>
      apiCreateWatchlist(
        caseId,
        name.trim(),
        'keyword',
        patterns.split(',').map((p) => p.trim()).filter(Boolean),
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlists', caseId] })
      setName('')
      setPatterns('')
      setFormError('')
    },
    onError: (e: Error) => setFormError(e.message),
  })

  const deleteMut = useMutation({
    mutationFn: apiDeleteWatchlist,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlists', caseId] }),
    onError: (e: Error) => setFormError(e.message),
  })

  const toggleMut = useMutation({
    mutationFn: apiToggleWatchlist,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlists', caseId] }),
  })

  return (
    <>
      <PageHeader
        icon={Eye}
        title="Watchlists"
        description={`${watchlists.length} lista(s) · ${hitsSummary?.total_hits ?? 0} hit(s)`}
        actions={
          hitsSummary && hitsSummary.unacknowledged > 0 ? (
            <Badge variant="danger">{hitsSummary.unacknowledged} não reconhecido(s)</Badge>
          ) : undefined
        }
      />
      <div className="mb-6 flex flex-wrap gap-3">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Nome da lista"
          className={cn('min-w-[12rem] flex-1', INPUT_CLASS)}
        />
        <input
          value={patterns}
          onChange={(e) => setPatterns(e.target.value)}
          placeholder="Padrões, separados por vírgula"
          className={cn('min-w-[16rem] flex-[2]', INPUT_CLASS)}
        />
        <Button
          onClick={() => createMut.mutate()}
          disabled={!name.trim() || !patterns.trim() || createMut.isPending}
        >
          <Plus className="h-4 w-4" />
          Adicionar
        </Button>
      </div>
      {formError && <p className="mb-4 text-sm text-danger">{formError}</p>}
      {isLoading ? (
        <Loader2 className="h-5 w-5 animate-spin text-muted" />
      ) : watchlists.length === 0 ? (
        <EmptyState icon={Eye} title="Nenhuma watchlist ainda" />
      ) : (
        <div className="space-y-3">
          {watchlists.map((w) => (
            <Card key={w.id}>
              <CardContent>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <span className="text-sm font-medium text-foreground">{w.name}</span>
                    <span className="ml-2 text-xs text-dim">({w.watch_type})</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      title={w.is_active ? 'Desativar' : 'Ativar'}
                      onClick={() => toggleMut.mutate(w.id)}
                      className={cn(
                        'h-2 w-2 rounded-full',
                        w.is_active ? 'bg-success' : 'bg-dim',
                      )}
                    />
                    <Button variant="ghost" size="sm" onClick={() => deleteMut.mutate(w.id)}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {w.patterns.slice(0, 8).map((p, i) => (
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
  const [mediaPage, setMediaPage] = useState(0)
  const MEDIA_PAGE_SIZE = 60

  const { data: mediaData, isLoading: mediaLoading } = useQuery({
    queryKey: ['media', caseId, mediaPage],
    queryFn: () => apiListMedia(caseId, { limit: MEDIA_PAGE_SIZE, offset: mediaPage * MEDIA_PAGE_SIZE }),
  })
  const media = mediaData?.items ?? []
  const mediaTotal = mediaData?.total ?? 0
  const cacheFiles = mediaData?.cache_files ?? 0

  const { data: detectionStats = [] } = useQuery({
    queryKey: ['detectionStats', caseId, minConfidence],
    queryFn: () => apiDetectionStats(caseId, minConfidence),
  })

  const { data: mediaWithDetections = [], isLoading: detectionsLoading } = useQuery({
    queryKey: ['mediaWithDetections', caseId, selectedClass, minConfidence, showOnlyDetections],
    queryFn: () => apiMediaWithDetections(caseId, selectedClass || undefined, minConfidence),
    enabled: showOnlyDetections,
  })

  const [pipelineNote, setPipelineNote] = useState('')
  const [preview, setPreview] = useState<{ hash: string; mimeType: string | null } | null>(null)

  const { data: pipelineJobs = [] } = useQuery({
    queryKey: ['pipelineStatus', caseId],
    queryFn: () => apiPipelineStatus(caseId),
    refetchInterval: (query) => {
      const jobs = query.state.data ?? []
      const busy = jobs.some((j) => j.status === 'running' || j.status === 'pending')
      return busy ? 2000 : false
    },
  })

  const jobsBusy = pipelineJobs.some((j) => j.status === 'running' || j.status === 'pending')

  useEffect(() => {
    if (pipelineJobs.length === 0) return
    if (jobsBusy) return
    queryClient.invalidateQueries({ queryKey: ['plates', caseId] })
    queryClient.invalidateQueries({ queryKey: ['transcriptions', caseId] })
    queryClient.invalidateQueries({ queryKey: ['ocr', caseId] })
    queryClient.invalidateQueries({ queryKey: ['subjects', caseId] })
    queryClient.invalidateQueries({ queryKey: ['faces', caseId] })
    queryClient.invalidateQueries({ queryKey: ['pendencias', caseId] })
  }, [jobsBusy, pipelineJobs.length, caseId, queryClient])

  const pipelineMutation = useMutation({
    mutationFn: (mode: 'sample' | 'all') => apiLaunchPipeline(caseId, { mode }),
    onSuccess: (data) => {
      const skipped = Object.values(data.skipped ?? {})
      const warnings = data.warnings ?? []
      setPipelineNote(
        [
          data.mode === 'all'
            ? `${data.jobs_launched} job(s) · caso inteiro · ${data.image_count ?? 0} img · ${data.audio_count ?? 0} áudio`
            : `${data.jobs_launched} job(s) · amostra · ${data.image_count ?? 0} img · ${data.audio_count ?? 0} áudio`,
          data.missing_files ? `${data.missing_files} sem arquivo no UFDR` : '',
          ...skipped,
          ...warnings.filter((w) => !w.startsWith('Modo amostra')),
          data.mode === 'sample'
            ? 'Para processar o caso inteiro, use o botão Caso inteiro.'
            : '',
        ]
          .filter(Boolean)
          .join(' · '),
      )
      queryClient.invalidateQueries({ queryKey: ['media', caseId] })
      queryClient.invalidateQueries({ queryKey: ['pipelineStatus', caseId] })
    },
    onError: (e: Error) => setPipelineNote(e.message),
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
        description={`${mediaTotal.toLocaleString()} na galeria · ${cacheFiles.toLocaleString()} no disco · página ${mediaPage + 1} de ${Math.max(1, Math.ceil(mediaTotal / MEDIA_PAGE_SIZE))}`}
      />

      <Card className="mb-4">
        <CardContent className="py-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-foreground">Pipeline de detecção</p>
              <p className="mt-1 max-w-xl text-xs text-dim">
                Amostra processa 80 imagens e 40 áudios. Caso inteiro percorre toda a mídia extraível e pode demorar.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => pipelineMutation.mutate('sample')}
                disabled={pipelineMutation.isPending || jobsBusy}
              >
                {pipelineMutation.isPending ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Scan className="h-3 w-3" />
                )}
                Amostra
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  const ok = window.confirm(
                    `Vai processar toda a mídia extraível deste caso (${mediaTotal.toLocaleString()} hashes na galeria). Pode demorar. Continuar?`,
                  )
                  if (ok) pipelineMutation.mutate('all')
                }}
                disabled={pipelineMutation.isPending || jobsBusy}
              >
                Caso inteiro
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {pipelineNote && (
        <Card className="mb-4 border-warning/20">
          <CardContent className="py-3 text-sm text-muted">{pipelineNote}</CardContent>
        </Card>
      )}

      {pipelineJobs.length > 0 && (
        <Card className="mb-4">
          <CardContent className="space-y-2 py-4">
            {pipelineJobs.map((j) => (
              <div key={j.job_id} className="flex items-center gap-3">
                <span className="w-16 shrink-0 text-xs font-medium uppercase text-muted">{j.kind}</span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-white/40"
                    style={{ width: `${Math.round((j.progress ?? 0) * 100)}%` }}
                  />
                </div>
                <span className="w-10 shrink-0 text-right text-xs tabular-nums text-dim">
                  {Math.round((j.progress ?? 0) * 100)}%
                </span>
                <span className="max-w-[14rem] truncate text-xs text-dim">{j.message}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

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

            const expandable = isExpandableMedia(m.mime_type)
            return (
              <Card key={m.hash} className="overflow-hidden hover:border-border-hover">
                <div
                  className={`relative flex aspect-square items-center justify-center overflow-hidden bg-surface-elevated ${
                    expandable ? 'cursor-zoom-in' : ''
                  }`}
                  role={expandable ? 'button' : undefined}
                  tabIndex={expandable ? 0 : undefined}
                  onClick={() => {
                    if (expandable) setPreview({ hash: m.hash, mimeType: m.mime_type })
                  }}
                  onKeyDown={(e) => {
                    if (!expandable) return
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      setPreview({ hash: m.hash, mimeType: m.mime_type })
                    }
                  }}
                >
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

      {!showOnlyDetections && mediaTotal > MEDIA_PAGE_SIZE && (
        <div className="mt-6 flex items-center justify-center gap-3 pb-4">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setMediaPage(Math.max(0, mediaPage - 1))}
            disabled={mediaPage === 0}
          >
            Anterior
          </Button>
          <span className="text-xs text-dim">
            Página {mediaPage + 1} de {Math.ceil(mediaTotal / MEDIA_PAGE_SIZE)}
          </span>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setMediaPage(mediaPage + 1)}
            disabled={(mediaPage + 1) * MEDIA_PAGE_SIZE >= mediaTotal}
          >
            Próxima
          </Button>
        </div>
      )}

      <MediaLightbox
        open={preview !== null}
        onClose={() => setPreview(null)}
        caseId={caseId}
        hash={preview?.hash ?? null}
        mimeType={preview?.mimeType}
      />
    </>
  )
}

function MediaThumbnail({ hash, mimeType, caseId }: { hash: string; mimeType?: string | null; caseId: string }) {
  const [stage, setStage] = useState<'thumb' | 'full' | 'fail'>('thumb')
  const thumbUrl = getThumbnailUrl(hash, caseId)
  const fileUrl = getMediaUrl(hash, caseId)
  const looksLikeImage =
    !mimeType ||
    mimeType.startsWith('image/') ||
    mimeType === 'application/octet-stream'

  if (stage === 'fail') {
    return <Camera className="h-8 w-8 text-dim" />
  }

  if (looksLikeImage) {
    const src = stage === 'thumb' ? thumbUrl : fileUrl
    return (
      <img
        src={src}
        alt={mimeType || 'imagem'}
        className="h-full w-full object-contain"
        loading="lazy"
        onError={() => setStage((s) => (s === 'thumb' ? 'full' : 'fail'))}
      />
    )
  }

  if (mimeType?.startsWith('video/')) {
    return (
      <video
        src={fileUrl}
        className="h-full w-full object-contain"
        preload="metadata"
        onError={() => setStage('fail')}
      />
    )
  }

  if (mimeType?.startsWith('audio/')) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <audio src={fileUrl} controls className="w-full px-2" onError={() => setStage('fail')} />
      </div>
    )
  }

  if (mimeType === 'application/pdf') {
    return (
      <iframe
        src={fileUrl}
        title="PDF"
        className="h-full w-full"
        style={{ border: 'none', backgroundColor: '#fff' }}
        onError={() => setStage('fail')}
      />
    )
  }

  const isTextLike =
    !!mimeType &&
    (mimeType.startsWith('text/') ||
      mimeType === 'application/json' ||
      mimeType === 'application/xml' ||
      mimeType === 'application/javascript' ||
      mimeType.endsWith('+json') ||
      mimeType.endsWith('+xml'))

  if (isTextLike) {
    return <TextFilePreview url={fileUrl} onFail={() => setStage('fail')} />
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <FileText className="h-8 w-8 text-dim" />
      <span className="px-2 text-center text-[10px] text-dim">{mimeType}</span>
    </div>
  )
}

function TextFilePreview({ url, onFail }: { url: string; onFail: () => void }) {
  const { data: content, isError } = useQuery({
    queryKey: ['text-preview', url],
    queryFn: async () => {
      const res = await fetch(url)
      if (!res.ok) throw new Error(`${res.status}`)
      const text = await res.text()
      return text.slice(0, 800)
    },
    staleTime: Infinity,
    retry: false,
  })

  if (isError) {
    onFail()
    return null
  }

  // Rendered as plain text via React — HTML/JS content is never executed
  return (
    <pre
      className="h-full w-full overflow-hidden p-2 text-left"
      style={{
        fontSize: '9px',
        lineHeight: '1.35',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        color: '#a3a3a3',
        margin: 0,
      }}
    >
      {content ?? '…'}
    </pre>
  )
}

function PlaybooksTab({
  caseId,
  onOpenReports,
}: {
  caseId: string
  onOpenReports: () => void
}) {
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
      queryClient.invalidateQueries({ queryKey: ['reports', caseId] })
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

                    {lastResult.results && typeof lastResult.results === 'object' ? (
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
                    ) : null}
                    {Object.values(
                      (lastResult.results ?? {}) as Record<string, { output?: { report_id?: string } }>,
                    ).some((r) => r.output?.report_id) && (
                      <Button
                        size="sm"
                        variant="secondary"
                        className="mt-3"
                        onClick={onOpenReports}
                      >
                        <FileText className="h-3.5 w-3.5" />
                        Abrir Relatórios
                      </Button>
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

function OpsTab({ caseId }: { caseId: string }) {
  const { data: ops, isLoading } = useQuery({
    queryKey: ['ops-health'],
    queryFn: () => apiOpsHealth(),
    refetchInterval: 30000,
  })

  return (
    <>
      <IngestPanel caseId={caseId} />

      <PageHeader icon={Cpu} title="Operação" description="Status dos serviços" />

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-muted" />
        </div>
      ) : (
        <>
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

      {ops?.queues && ops.queues.length > 0 && (
        <div className="mt-8">
          <h3 className="mb-3 text-sm font-medium text-foreground">Filas</h3>
          <div className="space-y-2">
            {ops.queues.map((q) => (
              <Card key={q.stage}>
                <CardContent className="flex items-center justify-between py-3 text-sm">
                  <span className="text-foreground">{q.stage}</span>
                  <span className="font-mono text-xs text-dim">
                    pendentes {q.pending} · em curso {q.processing} · falhas {q.failed}
                  </span>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

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

function formatAudioBytes(n: number | null | undefined): string | null {
  if (n == null || n <= 0) return null
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

function TranscriptionsTab({ caseId }: { caseId: string }) {
  const [search, setSearch] = useState('')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const { data: transcriptions = [], isLoading, isError, error: listError } = useQuery({
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
      ) : isError ? (
        <EmptyState
          icon={Mic}
          title="Falha ao carregar transcrições"
          description={listError instanceof Error ? listError.message : 'Erro na API'}
        />
      ) : transcriptions.length === 0 ? (
        <EmptyState icon={Mic} title="Nenhuma transcrição" description="Execute o pipeline de detecção para transcrever áudios" />
      ) : (
        <div className="space-y-3">
          {transcriptions.map((t) => {
            const isExpanded = expandedId === t.id
            const sizeLabel = formatAudioBytes(t.size_bytes)
            return (
              <Card key={t.id} className="hover:border-border-hover">
                <CardContent className="py-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Mic className="h-4 w-4 shrink-0 text-dim" />
                    <span className="truncate font-mono text-sm text-foreground">
                      {t.file_name || t.media_hash.slice(0, 16)}
                    </span>
                    {t.language && <Badge className="text-[10px]">{t.language}</Badge>}
                    {sizeLabel && <span className="text-xs text-dim">{sizeLabel}</span>}
                    <span className="text-[10px] text-dim">
                      {new Date(t.created_at).toLocaleString('pt-BR')}
                    </span>
                  </div>

                  {(t.app || t.whatsapp_id || t.sender) && (
                    <p className="mt-2 text-xs text-muted">
                      {[t.app, t.whatsapp_id, t.sender || t.counterpart]
                        .filter(Boolean)
                        .join(' · ')}
                    </p>
                  )}

                  {(t.original_path || t.source_member) && (
                    <p
                      className="mt-1 truncate font-mono text-[11px] text-dim"
                      title={t.original_path || t.source_member || undefined}
                    >
                      Origem: {t.original_path || t.source_member}
                    </p>
                  )}
                  {t.original_path && t.source_member && t.source_member !== t.original_path && (
                    <p
                      className="mt-0.5 truncate font-mono text-[11px] text-dim"
                      title={t.source_member}
                    >
                      Artifact: {t.source_member}
                    </p>
                  )}
                  {t.document_title && (
                    <p className="mt-0.5 truncate text-[11px] text-dim" title={t.document_title}>
                      Document: {t.document_title}
                    </p>
                  )}
                  <p className="mt-1 font-mono text-[10px] text-dim" title={t.media_hash}>
                    SHA-256 {t.media_hash.slice(0, 16)}…
                  </p>

                  <audio
                    controls
                    preload="metadata"
                    className="mt-3 w-full"
                    src={getMediaUrl(t.media_hash, caseId)}
                    onClick={(e) => e.stopPropagation()}
                  >
                    O navegador não reproduz este áudio.
                  </audio>

                  <button
                    type="button"
                    className="mt-3 w-full text-left"
                    onClick={() => setExpandedId(isExpanded ? null : t.id)}
                  >
                    <p
                      className={cn(
                        'text-sm leading-relaxed text-foreground',
                        !isExpanded && 'line-clamp-3',
                      )}
                    >
                      {t.text}
                    </p>
                    {t.text.length > 200 && (
                      <span className="mt-1 inline-block text-xs text-muted">
                        {isExpanded ? 'Recolher' : 'Expandir texto'}
                      </span>
                    )}
                  </button>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </>
  )
}
