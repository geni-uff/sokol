import { useQuery } from '@tanstack/react-query'
import { apiGeoEvents, apiTimeline, type GeoEvent, type Event } from '@/lib/api'
import { useEffect, useRef, useState } from 'react'
import { MapPin, Globe, Clock, Loader2, Layers } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/cn'
import 'leaflet/dist/leaflet.css'


function LeafletMap({ geoEvents }: { geoEvents: GeoEvent[] }) {
  const mapRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<unknown>(null)

  useEffect(() => {
    if (!mapRef.current || geoEvents.length === 0) return

    let L: typeof import('leaflet')

    const initMap = async () => {
      L = await import('leaflet')

      // Bundlers break Leaflet's internal URL resolution for default marker icons
      delete (L.Icon.Default.prototype as Record<string, unknown>)._getIconUrl
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
        iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
      })

      if (mapInstanceRef.current) {
        ;(mapInstanceRef.current as { remove: () => void }).remove()
        mapInstanceRef.current = null
      }

      const map = L.map(mapRef.current!, {
        zoomControl: true,
        attributionControl: true,
      })

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap',
        maxZoom: 19,
      }).addTo(map)

      const markers: ReturnType<typeof L.marker>[] = []
      const coords: [number, number][] = []

      geoEvents.forEach((ev, idx) => {
        const marker = L.marker([ev.lat, ev.lon]).addTo(map)
        const dateStr = ev.ts ? new Date(ev.ts).toLocaleString('pt-BR') : 'Sem data'
        const meta = ev.meta as Record<string, unknown> | null
        const address = (meta?.address as string) || ev.summary
        marker.bindPopup(`
          <div style="font-family:system-ui;min-width:180px">
            <div style="font-weight:600;margin-bottom:4px;font-size:13px">${address}</div>
            <div style="font-size:11px;color:#666">
              <div>${dateStr}</div>
              <div style="margin-top:2px">Lat: ${ev.lat.toFixed(6)}</div>
              <div>Lon: ${ev.lon.toFixed(6)}</div>
              <div style="margin-top:4px;color:#999">Ponto ${idx + 1} de ${geoEvents.length}</div>
            </div>
          </div>
        `)
        markers.push(marker)
        coords.push([ev.lat, ev.lon])
      })

      if (coords.length > 1) {
        // Calculate distance and average speed
        let totalDistanceKm = 0
        for (let i = 0; i < coords.length - 1; i++) {
          const [lat1, lon1] = coords[i]
          const [lat2, lon2] = coords[i + 1]
          const R = 6371 // Earth radius in km
          const dLat = ((lat2 - lat1) * Math.PI) / 180
          const dLon = ((lon2 - lon1) * Math.PI) / 180
          const a =
            Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos((lat1 * Math.PI) / 180) *
              Math.cos((lat2 * Math.PI) / 180) *
              Math.sin(dLon / 2) *
              Math.sin(dLon / 2)
          const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
          totalDistanceKm += R * c
        }

        L.polyline(coords, {
          color: '#8b5cf6',
          weight: 3,
          opacity: 0.8,
          dashArray: '6 4',
        })
          .bindPopup(`<div style="font-size:11px"><b>Trajeto</b><br/>${coords.length} pontos<br/>${totalDistanceKm.toFixed(1)}km</div>`)
          .addTo(map)
      }

      if (coords.length > 0) {
        map.fitBounds(coords, { padding: [40, 40] })
      }

      mapInstanceRef.current = map
    }

    initMap()

    return () => {
      if (mapInstanceRef.current) {
        ;(mapInstanceRef.current as { remove: () => void }).remove()
        mapInstanceRef.current = null
      }
    }
  }, [geoEvents])

  return (
    <div
      ref={mapRef}
      className="h-[600px] w-full rounded-lg border border-border"
      style={{ background: '#111' }}
    />
  )
}

export function MapTab({ caseId }: { caseId: string }) {
  const [subTab, setSubTab] = useState<'mapa' | 'eventos'>('mapa')
  const [kindFilter, setKindFilter] = useState('')
  const [appFilter, setAppFilter] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [page, setPage] = useState(0)
  const limit = 50

  const { data: geoEvents = [], isLoading: geoLoading } = useQuery({
    queryKey: ['geo', caseId],
    queryFn: () => apiGeoEvents(caseId),
    enabled: !!caseId,
  })

  const { data: timelineData, isLoading: timelineLoading } = useQuery({
    queryKey: ['timeline', caseId, kindFilter, appFilter, startDate, endDate, page],
    queryFn: () => apiTimeline(
      caseId,
      limit,
      page * limit,
      kindFilter || undefined,
      appFilter || undefined,
      startDate || undefined,
      endDate || undefined,
    ),
    enabled: !!caseId,
  })

  const events = timelineData?.events ?? []
  const total = timelineData?.total ?? 0

  const KIND_ICONS: Record<string, string> = {
    message: '💬',
    call: '📞',
    location: '📍',
    web_visit: '🌐',
    media: '📷',
  }

  return (
    <>
      <PageHeader
        icon={MapPin}
        title="Timeline"
        description={`${geoEvents.length} pontos geolocalizados · ${total.toLocaleString()} eventos`}
      />

      <div className="mb-6 flex gap-1 rounded-lg border border-border bg-surface p-1">
        <button
          type="button"
          onClick={() => setSubTab('mapa')}
          className={cn(
            'flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors',
            subTab === 'mapa'
              ? 'bg-white/10 text-foreground'
              : 'text-muted hover:text-foreground',
          )}
        >
          <MapPin className="h-4 w-4" />
          Mapa
          {geoEvents.length > 0 && (
            <Badge className="ml-1 text-[10px]">{geoEvents.length}</Badge>
          )}
        </button>
        <button
          type="button"
          onClick={() => setSubTab('eventos')}
          className={cn(
            'flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors',
            subTab === 'eventos'
              ? 'bg-white/10 text-foreground'
              : 'text-muted hover:text-foreground',
          )}
        >
          <Clock className="h-4 w-4" />
          Eventos
          {total > 0 && (
            <Badge className="ml-1 text-[10px]">{total.toLocaleString()}</Badge>
          )}
        </button>
      </div>

      {subTab === 'mapa' && (
        <>
          {geoLoading ? (
            <div className="flex justify-center py-16">
              <Loader2 className="h-5 w-5 animate-spin text-muted" />
            </div>
          ) : geoEvents.length === 0 ? (
            <EmptyState
              icon={MapPin}
              title="Nenhum ponto geolocalizado"
              description="Execute a ingestão de dados para extrair coordenadas GPS."
            />
          ) : (
            <div className="space-y-4">
              <LeafletMap geoEvents={geoEvents} />
              <div className="flex flex-wrap items-center gap-3 text-xs text-dim">
                <div className="flex items-center gap-1.5">
                  <span className="inline-block h-2 w-2 rounded-full bg-muted" />
                  <span>{geoEvents.length} pontos</span>
                </div>
                {geoEvents.length > 1 && (
                  <div className="flex items-center gap-1.5">
                    <span className="inline-block h-0.5 w-4 border-t border-dashed border-muted" />
                    <span>Caminho do sujeito</span>
                  </div>
                )}
              </div>

              <div className="mt-4 space-y-2">
                {geoEvents.map((ev, idx) => {
                  const meta = ev.meta as Record<string, unknown> | null
                  return (
                    <Card key={ev.id} className="hover:border-border-hover">
                      <CardContent className="flex items-center gap-4 py-3">
                        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/5 text-xs font-medium text-muted">
                          {idx + 1}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm text-foreground truncate">
                            {ev.summary}
                          </p>
                          <div className="mt-1 flex items-center gap-3 text-xs text-dim">
                            <span>{ev.ts ? new Date(ev.ts).toLocaleString('pt-BR') : '?'}</span>
                            <span>
                              {ev.lat.toFixed(6)}, {ev.lon.toFixed(6)}
                            </span>
                            {meta?.address && <span className="truncate">{String(meta.address)}</span>}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  )
                })}
              </div>
            </div>
          )}
        </>
      )}

      {subTab === 'eventos' && (
        <>
          <div className="mb-4 space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <Layers className="h-4 w-4 text-dim" />
                <select
                  value={kindFilter}
                  onChange={(e) => {
                    setKindFilter(e.target.value)
                    setPage(0)
                  }}
                  style={{
                    height: '2.75rem',
                    borderRadius: '0.5rem',
                    border: '1px solid #262626',
                    backgroundColor: '#141414',
                    paddingLeft: '1rem',
                    paddingRight: '1rem',
                    fontSize: '0.875rem',
                    color: '#ededed',
                    paddingTop: 0,
                    paddingBottom: 0,
                  }}
                >
                  <option value="">Todos os eventos</option>
                  <option value="message">Mensagens</option>
                  <option value="call">Chamadas</option>
                  <option value="location">Localizações</option>
                  <option value="web_visit">Web</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs text-dim">App:</span>
                <select
                  value={appFilter}
                  onChange={(e) => {
                    setAppFilter(e.target.value)
                    setPage(0)
                  }}
                  style={{
                    height: '2.75rem',
                    borderRadius: '0.5rem',
                    border: '1px solid #262626',
                    backgroundColor: '#141414',
                    paddingLeft: '1rem',
                    paddingRight: '1rem',
                    fontSize: '0.875rem',
                    color: '#ededed',
                    paddingTop: 0,
                    paddingBottom: 0,
                    minWidth: '150px',
                  }}
                >
                  <option value="">Todos os apps</option>
                  <option value="whatsapp">WhatsApp</option>
                  <option value="telegram">Telegram</option>
                  <option value="messenger">Messenger</option>
                  <option value="signal">Signal</option>
                </select>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <span className="text-xs text-dim">Período:</span>
              <input
                type="date"
                value={startDate}
                onChange={(e) => {
                  setStartDate(e.target.value)
                  setPage(0)
                }}
                style={{
                  height: '2.75rem',
                  borderRadius: '0.5rem',
                  border: '1px solid #262626',
                  backgroundColor: '#141414',
                  paddingLeft: '1rem',
                  paddingRight: '1rem',
                  fontSize: '0.875rem',
                  color: '#ededed',
                }}
              />
              <span className="text-xs text-dim">até</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => {
                  setEndDate(e.target.value)
                  setPage(0)
                }}
                style={{
                  height: '2.75rem',
                  borderRadius: '0.5rem',
                  border: '1px solid #262626',
                  backgroundColor: '#141414',
                  paddingLeft: '1rem',
                  paddingRight: '1rem',
                  fontSize: '0.875rem',
                  color: '#ededed',
                }}
              />
            </div>
          </div>

          {timelineLoading ? (
            <div className="flex justify-center py-16">
              <Loader2 className="h-5 w-5 animate-spin text-muted" />
            </div>
          ) : events.length === 0 ? (
            <EmptyState icon={Clock} title="Nenhum evento encontrado" />
          ) : (
            <div className="space-y-3">
              {events.map((event: Event) => {
                const icon = KIND_ICONS[event.kind] || '•'
                return (
                  <Card key={event.id} className="group border-border hover:border-border-hover">
                    <CardContent className="flex items-start gap-4 py-4">
                      <span className="mt-0.5 shrink-0 text-base">{icon}</span>
                      <div className="min-w-0 flex-1">
                        <div className="mb-1.5 flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs text-muted">
                            {event.ts ? new Date(event.ts).toLocaleString('pt-BR') : '?'}
                          </span>
                          {event.tz_original && <Badge className="shrink-0 text-[10px]">{event.tz_original}</Badge>}
                          <Badge className="shrink-0 capitalize text-[10px]">{event.kind}</Badge>
                          {event.app && (
                            <Badge variant="accent" className="shrink-0 text-[10px]">
                              {event.app}
                            </Badge>
                          )}
                        </div>
                        <p className="break-words text-sm leading-relaxed text-foreground">
                          {event.summary}
                        </p>
                        {event.actor && event.counterpart && (
                          <p className="mt-1.5 break-words text-xs text-dim">
                            <span className="font-medium text-muted">{event.actor}</span>
                            {' → '}
                            <span className="font-medium text-muted">{event.counterpart}</span>
                          </p>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          )}

          {total > limit && (
            <div className="mt-6 flex items-center justify-center gap-3 pb-4">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage(Math.max(0, page - 1))}
                disabled={page === 0}
              >
                Anterior
              </Button>
              <span className="text-xs text-dim">
                Página {page + 1} de {Math.ceil(total / limit)}
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage(page + 1)}
                disabled={(page + 1) * limit >= total}
              >
                Próxima
              </Button>
            </div>
          )}
        </>
      )}
    </>
  )
}
