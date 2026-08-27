import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, BarChart3, Loader2, MapPin, Phone, MessageSquare, X } from 'lucide-react'
import {
  apiActivityHeatmap,
  apiLocationHeatmap,
  apiContactFrequency,
  apiAnalyzeAnomalies,
  apiListAnomalies,
  apiDismissAnomaly,
  type LocationCell,
} from '@/lib/api'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import 'leaflet/dist/leaflet.css'

const KIND_LABELS: Record<string, string> = {
  impossible_jump: 'Salto impossível',
  odd_hours: 'Horário atípico',
  burst_contact: 'Contato-relâmpago',
  silence_gap: 'Silêncio anômalo',
}

const SEVERITY_COLORS: Record<string, string> = {
  high: '#ef4444',
  medium: '#f97316',
  low: '#eab308',
}

const DOW_LABELS = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']

const SELECT_STYLE: React.CSSProperties = {
  height: '2.25rem',
  borderRadius: '0.5rem',
  border: '1px solid #262626',
  backgroundColor: '#141414',
  paddingLeft: '0.75rem',
  paddingRight: '0.75rem',
  fontSize: '0.8125rem',
  color: '#ededed',
}

function heatColor(value: number, max: number): string {
  if (value === 0 || max === 0) return '#141414'
  const t = Math.min(1, value / max)
  // dark → violet → hot
  const r = Math.round(30 + t * 200)
  const g = Math.round(20 + t * 60)
  const b = Math.round(60 + t * 140)
  return `rgb(${r},${g},${b})`
}

function ActivityGrid({ caseId }: { caseId: string }) {
  const [kind, setKind] = useState('')
  const { data, isLoading } = useQuery({
    queryKey: ['activity-heatmap', caseId, kind],
    queryFn: () => apiActivityHeatmap(caseId, kind || undefined),
  })

  const cells = data?.cells ?? []
  const matrix = new Map<string, number>()
  let max = 0
  for (const c of cells) {
    matrix.set(`${c.dow}:${c.hour}`, c.count)
    if (c.count > max) max = c.count
  }

  return (
    <Card>
      <CardContent className="py-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-medium text-foreground">Atividade por hora × dia da semana</h3>
            <p className="mt-0.5 text-xs text-dim">
              {data?.total_events?.toLocaleString() ?? 0} eventos · fuso {data?.timezone || '—'}
            </p>
          </div>
          <select value={kind} onChange={(e) => setKind(e.target.value)} style={SELECT_STYLE}>
            <option value="">Todos os tipos</option>
            <option value="message">Mensagens</option>
            <option value="call">Chamadas</option>
            <option value="location">Localizações</option>
            <option value="web_visit">Web</option>
          </select>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="h-5 w-5 animate-spin text-muted" />
          </div>
        ) : cells.length === 0 ? (
          <p className="py-8 text-center text-xs text-dim">Sem eventos datados neste caso.</p>
        ) : (
          <div className="overflow-x-auto">
            <div style={{ display: 'grid', gridTemplateColumns: '2.5rem repeat(24, minmax(14px, 1fr))', gap: '2px', minWidth: '520px' }}>
              <div />
              {Array.from({ length: 24 }, (_, h) => (
                <div key={h} className="text-center text-[9px] text-dim">
                  {h % 3 === 0 ? h : ''}
                </div>
              ))}
              {Array.from({ length: 7 }, (_, dow) => (
                <div key={dow} style={{ display: 'contents' }}>
                  <div className="pr-1 text-right text-[10px] leading-[16px] text-dim">{DOW_LABELS[dow]}</div>
                  {Array.from({ length: 24 }, (_, h) => {
                    const v = matrix.get(`${dow}:${h}`) ?? 0
                    return (
                      <div
                        key={h}
                        title={`${DOW_LABELS[dow]} ${h}h — ${v} evento(s)`}
                        style={{
                          height: '16px',
                          borderRadius: '3px',
                          backgroundColor: heatColor(v, max),
                        }}
                      />
                    )
                  })}
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function LocationHeatMap({ points }: { points: LocationCell[] }) {
  const mapRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<unknown>(null)

  useEffect(() => {
    if (!mapRef.current || points.length === 0) return

    const init = async () => {
      const L = await import('leaflet')

      if (mapInstanceRef.current) {
        ;(mapInstanceRef.current as { remove: () => void }).remove()
        mapInstanceRef.current = null
      }

      const map = L.map(mapRef.current!, { zoomControl: true })
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap',
        maxZoom: 19,
      }).addTo(map)

      const max = Math.max(...points.map((p) => p.count))
      points.forEach((p) => {
        const t = p.count / max
        L.circleMarker([p.lat, p.lon], {
          radius: 4 + t * 14,
          color: 'transparent',
          fillColor: t > 0.66 ? '#ef4444' : t > 0.33 ? '#f97316' : '#8b5cf6',
          fillOpacity: 0.35 + t * 0.45,
        })
          .bindPopup(`<b>${p.count}</b> evento(s)<br/>${p.lat.toFixed(3)}, ${p.lon.toFixed(3)}`)
          .addTo(map)
      })

      map.fitBounds(points.map((p) => [p.lat, p.lon] as [number, number]), { padding: [30, 30] })
      mapInstanceRef.current = map
    }

    init()
    return () => {
      if (mapInstanceRef.current) {
        ;(mapInstanceRef.current as { remove: () => void }).remove()
        mapInstanceRef.current = null
      }
    }
  }, [points])

  return <div ref={mapRef} className="h-[420px] w-full rounded-lg border border-border" style={{ background: '#111' }} />
}

function LocationPanel({ caseId }: { caseId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['location-heatmap', caseId],
    queryFn: () => apiLocationHeatmap(caseId),
  })

  const points = data?.points ?? []

  return (
    <Card>
      <CardContent className="py-5">
        <div className="mb-4 flex items-center gap-2">
          <MapPin className="h-4 w-4 text-muted" />
          <h3 className="text-sm font-medium text-foreground">Densidade de localização</h3>
          <span className="text-xs text-dim">
            {points.length} células (~110 m) · {data?.total?.toLocaleString() ?? 0} eventos
          </span>
        </div>
        {isLoading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="h-5 w-5 animate-spin text-muted" />
          </div>
        ) : points.length === 0 ? (
          <p className="py-8 text-center text-xs text-dim">Nenhum evento geolocalizado.</p>
        ) : (
          <LocationHeatMap points={points} />
        )}
      </CardContent>
    </Card>
  )
}

function ContactBars({ caseId }: { caseId: string }) {
  const { data: contacts = [], isLoading } = useQuery({
    queryKey: ['contact-frequency', caseId],
    queryFn: () => apiContactFrequency(caseId),
  })

  const max = contacts.length ? contacts[0].total : 0

  return (
    <Card>
      <CardContent className="py-5">
        <div className="mb-4 flex items-center gap-2">
          <Phone className="h-4 w-4 text-muted" />
          <h3 className="text-sm font-medium text-foreground">Frequência de contato</h3>
          <span className="text-xs text-dim">top {contacts.length} contrapartes</span>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="h-5 w-5 animate-spin text-muted" />
          </div>
        ) : contacts.length === 0 ? (
          <p className="py-8 text-center text-xs text-dim">Sem mensagens ou chamadas com contraparte identificada.</p>
        ) : (
          <div className="space-y-2">
            {contacts.map((c) => (
              <div key={c.counterpart} className="flex items-center gap-3">
                <span className="w-52 shrink-0 truncate text-xs text-muted" title={c.counterpart}>
                  {c.counterpart}
                </span>
                <div className="h-4 flex-1 overflow-hidden rounded bg-white/5">
                  <div
                    style={{
                      width: `${max ? (c.total / max) * 100 : 0}%`,
                      height: '100%',
                      background: 'linear-gradient(90deg, #7c3aed, #a78bfa)',
                    }}
                  />
                </div>
                <span className="w-14 shrink-0 text-right font-mono text-xs text-foreground">
                  {c.total.toLocaleString()}
                </span>
                <span className="flex w-20 shrink-0 items-center gap-1 text-[10px] text-dim">
                  {c.kinds.message ? (
                    <span className="flex items-center gap-0.5">
                      <MessageSquare className="h-3 w-3" />
                      {c.kinds.message}
                    </span>
                  ) : null}
                  {c.kinds.call ? (
                    <span className="flex items-center gap-0.5">
                      <Phone className="h-3 w-3" />
                      {c.kinds.call}
                    </span>
                  ) : null}
                </span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function AnomaliesPanel({ caseId }: { caseId: string }) {
  const qc = useQueryClient()

  const { data: anomalies = [], isLoading } = useQuery({
    queryKey: ['anomalies', caseId],
    queryFn: () => apiListAnomalies(caseId),
  })

  const analyzeMut = useMutation({
    mutationFn: () => apiAnalyzeAnomalies(caseId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['anomalies', caseId] }),
  })

  const dismissMut = useMutation({
    mutationFn: (id: string) => apiDismissAnomaly(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['anomalies', caseId] }),
  })

  return (
    <Card>
      <CardContent className="py-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-muted" />
            <h3 className="text-sm font-medium text-foreground">Anomalias na timeline</h3>
            {anomalies.length > 0 && <Badge variant="danger">{anomalies.length}</Badge>}
          </div>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => analyzeMut.mutate()}
            disabled={analyzeMut.isPending}
          >
            {analyzeMut.isPending ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : null}
            Analisar
          </Button>
        </div>

        <p className="mb-4 rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-3 py-2 text-xs text-yellow-300/80">
          Anomalias são indícios automáticos (Indicators) com score e explicação — nunca fatos
          confirmados.
        </p>

        {analyzeMut.data && (
          <p className="mb-3 text-xs text-dim">
            Última análise: {analyzeMut.data.created} nova(s) anomalia(s).
          </p>
        )}

        {isLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted" />
          </div>
        ) : anomalies.length === 0 ? (
          <p className="py-6 text-center text-xs text-dim">
            Nenhuma anomalia aberta. Clique em Analisar para rodar as regras.
          </p>
        ) : (
          <div className="space-y-2">
            {anomalies.map((a) => (
              <div
                key={a.id}
                className="flex items-start gap-3 rounded-lg border border-border bg-surface px-4 py-3"
              >
                <span
                  className="mt-1 inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: SEVERITY_COLORS[a.severity] ?? '#666' }}
                  title={`Severidade: ${a.severity}`}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-medium text-foreground">
                      {KIND_LABELS[a.kind] ?? a.kind}
                    </span>
                    <Badge className="text-[10px]">score {a.score.toFixed(2)}</Badge>
                    <span className="text-[10px] text-dim">
                      {a.ref_event_ids.length} evento(s) de origem
                    </span>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-muted">{a.explanation}</p>
                </div>
                <button
                  type="button"
                  onClick={() => dismissMut.mutate(a.id)}
                  disabled={dismissMut.isPending}
                  title="Descartar"
                  className="shrink-0 rounded p-1 text-dim hover:bg-white/5 hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function AnalyticsTab({ caseId }: { caseId: string }) {
  const { data: activity } = useQuery({
    queryKey: ['activity-heatmap', caseId, ''],
    queryFn: () => apiActivityHeatmap(caseId),
  })

  const empty = (activity?.total_events ?? 0) === 0

  return (
    <>
      <PageHeader
        icon={BarChart3}
        title="Analytics"
        description="Padrões de atividade, densidade geográfica e frequência de contato"
      />

      {empty && activity ? (
        <EmptyState
          icon={BarChart3}
          title="Sem dados para análise"
          description="Ingira evidências para gerar os heatmaps."
        />
      ) : (
        <div className="space-y-6">
          <ActivityGrid caseId={caseId} />
          <LocationPanel caseId={caseId} />
          <ContactBars caseId={caseId} />
          <AnomaliesPanel caseId={caseId} />
        </div>
      )}
    </>
  )
}
