import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { GitBranch, Loader2 } from 'lucide-react'
import { apiGetGraph } from '@/lib/api'
import { canvasHeight, layoutGraph } from '@/lib/graphLayout'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'

const TYPE_COLORS: Record<string, string> = {
  person: '#e5e5e5',
  phone: '#a3a3a3',
  chat: '#737373',
  app: '#d4d4d4',
  location: '#fafafa',
  media: '#9ca3af',
}

export function GraphTab({ caseId }: { caseId: string }) {
  const [maxNodes, setMaxNodes] = useState(100)
  const [typeFilter, setTypeFilter] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const [hovered, setHovered] = useState<string | null>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 800, h: 560 })

  const { data: graph, isLoading } = useQuery({
    queryKey: ['graph', caseId, maxNodes],
    queryFn: () => apiGetGraph(caseId, maxNodes),
  })

  const filtered = useMemo(() => {
    if (!graph) return null
    const nodes = typeFilter ? graph.nodes.filter((n) => n.type === typeFilter) : graph.nodes
    const ids = new Set(nodes.map((n) => n.id))
    const edges = graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target))
    return { ...graph, nodes, edges }
  }, [graph, typeFilter])

  const plotH = canvasHeight(filtered?.nodes.length ?? 0)

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const apply = () => setSize({ w: Math.max(el.clientWidth, 320), h: plotH })
    const ro = new ResizeObserver(apply)
    ro.observe(el)
    apply()
    return () => ro.disconnect()
  }, [filtered, plotH])

  const laid = useMemo(
    () =>
      filtered ? layoutGraph(filtered.nodes, filtered.edges, size.w, size.h) : [],
    [filtered, size.w, size.h],
  )
  const pos = useMemo(() => new Map(laid.map((n) => [n.id, n])), [laid])
  const selectedNode = laid.find((n) => n.id === selected)

  const types = Array.from(new Set(graph?.nodes.map((n) => n.type) ?? []))

  return (
    <>
      <PageHeader
        icon={GitBranch}
        title="Mapa de Relações"
        description={`${graph?.nodes?.length || 0} nós · ${graph?.edges?.length || 0} conexões. Clique ou passe o mouse para ver o rótulo.`}
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="text-xs text-dim">
          Máx. nós
          <select
            value={maxNodes}
            onChange={(e) => setMaxNodes(Number(e.target.value))}
            className="ml-2 h-9 rounded-lg border border-border bg-surface-elevated px-3 text-sm text-foreground"
          >
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={200}>200</option>
          </select>
        </label>
        <label className="text-xs text-dim">
          Tipo
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="ml-2 h-9 rounded-lg border border-border bg-surface-elevated px-3 text-sm text-foreground"
          >
            <option value="">Todos</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        {selectedNode && (
          <Badge>
            {selectedNode.label} · {selectedNode.type}
          </Badge>
        )}
        <span className="text-[11px] text-dim">
          Layout Fruchterman–Reingold com anéis BFS e colisão. Rótulos ao passar o mouse quando há muitos nós.
        </span>
      </div>

      {isLoading ? (
        <Loader2 className="h-5 w-5 animate-spin text-muted" />
      ) : !filtered || filtered.nodes.length === 0 ? (
        <EmptyState icon={GitBranch} title="Nenhuma relação para desenhar" />
      ) : (
        <Card>
          <CardContent className="p-0">
            <div ref={wrapRef} className="w-full overflow-hidden">
              <svg width={size.w} height={size.h} className="block">
                {filtered.edges.map((e, i) => {
                  const a = pos.get(e.source)
                  const b = pos.get(e.target)
                  if (!a || !b) return null
                  return (
                    <line
                      key={`${e.source}-${e.target}-${i}`}
                      x1={a.x}
                      y1={a.y}
                      x2={b.x}
                      y2={b.y}
                      stroke="#333"
                      strokeWidth={Math.min(3, 0.6 + (e.weight ?? 1) * 0.3)}
                    />
                  )
                })}
                {laid.map((n) => {
                  const showLabel =
                    laid.length <= 36 || selected === n.id || hovered === n.id
                  return (
                  <g
                    key={n.id}
                    onClick={() => setSelected(n.id)}
                    onMouseEnter={() => setHovered(n.id)}
                    onMouseLeave={() => setHovered((h) => (h === n.id ? null : h))}
                    style={{ cursor: 'pointer' }}
                  >
                    <circle
                      cx={n.x}
                      cy={n.y}
                      r={selected === n.id ? n.r + 2 : n.r}
                      fill={TYPE_COLORS[n.type] || '#737373'}
                      stroke={selected === n.id || hovered === n.id ? '#fff' : '#111'}
                      strokeWidth={1.5}
                    />
                    {showLabel && (
                      <text
                        x={n.lx}
                        y={n.ly}
                        fill="#a3a3a3"
                        fontSize="10"
                      >
                        {n.label.length > 22 ? `${n.label.slice(0, 20)}…` : n.label}
                      </text>
                    )}
                    <title>{`${n.label} (${n.type})`}</title>
                  </g>
                  )
                })}
              </svg>
            </div>
          </CardContent>
        </Card>
      )}
    </>
  )
}
