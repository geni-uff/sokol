/** Graph layout: Fruchterman–Reingold (1991) + iterative collision resolution. */

export type GraphNodeIn = {
  id: string
  label: string
  type: string
  size?: number
}

export type GraphEdgeIn = {
  source: string
  target: string
  weight?: number
}

export type LaidNode = GraphNodeIn & {
  x: number
  y: number
  r: number
  lx: number
  ly: number
}

const NODE_R = 7
const LABEL_H = 12
const CHAR_W = 5.6

function nodeRadius(n: GraphNodeIn): number {
  const s = n.size ?? 1
  return NODE_R + Math.min(5, Math.log2(1 + s))
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v))
}

function labelWidth(label: string): number {
  const text = label.length > 22 ? `${label.slice(0, 20)}…` : label
  return text.length * CHAR_W
}

function fruchtermanReingold(
  nodes: Array<LaidNode & { vx: number; vy: number }>,
  edges: GraphEdgeIn[],
  width: number,
  height: number,
  iterations: number,
): void {
  const n = nodes.length
  if (n === 0) return
  const index = new Map(nodes.map((node) => [node.id, node]))
  const k = 1.15 * Math.sqrt((width * height) / n)
  let temp = Math.max(width, height) / 8

  for (let iter = 0; iter < iterations; iter++) {
    for (const a of nodes) {
      a.vx = 0
      a.vy = 0
    }

    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const a = nodes[i]
        const b = nodes[j]
        let dx = a.x - b.x
        let dy = a.y - b.y
        const dist = Math.max(Math.hypot(dx, dy), 0.01)
        const force = (k * k) / dist
        dx = (dx / dist) * force
        dy = (dy / dist) * force
        a.vx += dx
        a.vy += dy
        b.vx -= dx
        b.vy -= dy
      }
    }

    for (const e of edges) {
      const a = index.get(e.source)
      const b = index.get(e.target)
      if (!a || !b) continue
      let dx = b.x - a.x
      let dy = b.y - a.y
      const dist = Math.max(Math.hypot(dx, dy), 0.01)
        const force = dist / k
      dx = (dx / dist) * force
      dy = (dy / dist) * force
      a.vx += dx
      a.vy += dy
      b.vx -= dx
      b.vy -= dy
    }

    for (const node of nodes) {
      const disp = Math.max(Math.hypot(node.vx, node.vy), 0.01)
      const limited = Math.min(disp, temp)
      node.x = clamp(node.x + (node.vx / disp) * limited, node.r + 8, width - node.r - 8)
      node.y = clamp(node.y + (node.vy / disp) * limited, node.r + 8, height - node.r - 8)
    }

    temp *= 1 - (iter + 1) / iterations
  }
}

function resolveCollisions(
  nodes: LaidNode[],
  width: number,
  height: number,
  gap: number,
  rounds = 120,
): void {
  const n = nodes.length
  for (let round = 0; round < rounds; round++) {
    let moved = false
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const a = nodes[i]
        const b = nodes[j]
        let dx = a.x - b.x
        let dy = a.y - b.y
        let dist = Math.hypot(dx, dy)
        const minDist = a.r + b.r + gap
        if (dist >= minDist) continue
        if (dist < 1e-6) {
          const angle = ((i * 17 + j * 31) % 360) * (Math.PI / 180)
          dx = Math.cos(angle)
          dy = Math.sin(angle)
          dist = 1
        }
        const push = (minDist - dist) / 2 + 0.15
        const ux = dx / dist
        const uy = dy / dist
        a.x += ux * push
        a.y += uy * push
        b.x -= ux * push
        b.y -= uy * push
        moved = true
      }
    }
    if (round % 3 === 2 || round === rounds - 1) {
      for (const node of nodes) {
        node.x = clamp(node.x, node.r + 8, width - node.r - 8)
        node.y = clamp(node.y, node.r + 8, height - node.r - 8)
      }
    }
    if (!moved) break
  }
  for (const node of nodes) {
    node.x = clamp(node.x, node.r + 8, width - node.r - 8)
    node.y = clamp(node.y, node.r + 8, height - node.r - 8)
  }
}

type Box = { x: number; y: number; w: number; h: number }

function overlaps(a: Box, b: Box, pad = 2): boolean {
  return !(
    a.x + a.w + pad < b.x ||
    b.x + b.w + pad < a.x ||
    a.y + a.h + pad < b.y ||
    b.y + b.h + pad < a.y
  )
}

function placeLabels(nodes: LaidNode[], width: number, height: number): void {
  const used: Box[] = nodes.map((n) => ({
    x: n.x - n.r,
    y: n.y - n.r,
    w: n.r * 2,
    h: n.r * 2,
  }))

  for (const node of nodes) {
    const w = labelWidth(node.label)
    const candidates: Array<[number, number]> = [
      [node.x + node.r + 6, node.y + 4],
      [node.x - node.r - 6 - w, node.y + 4],
      [node.x - w / 2, node.y - node.r - 6],
      [node.x - w / 2, node.y + node.r + LABEL_H],
      [node.x + node.r + 6, node.y - 10],
      [node.x + node.r + 6, node.y + 14],
    ]
    let chosen: Box | null = null
    for (const [lx, ly] of candidates) {
      const box: Box = {
        x: clamp(lx, 4, width - w - 4),
        y: clamp(ly - LABEL_H + 2, 4, height - 4),
        w,
        h: LABEL_H,
      }
      if (!used.some((u) => overlaps(box, u))) {
        chosen = box
        break
      }
    }
    if (!chosen) {
      const lx = clamp(node.x + node.r + 6, 4, width - w - 4)
      const ly = clamp(node.y + 4, 4, height - 4)
      chosen = { x: lx, y: ly - LABEL_H + 2, w, h: LABEL_H }
    }
    node.lx = chosen.x
    node.ly = chosen.y + LABEL_H - 2
    used.push(chosen)
  }
}

export function minPairDistance(nodes: Array<{ x: number; y: number }>): number {
  let min = Infinity
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      min = Math.min(min, Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y))
    }
  }
  return min
}

export function layoutGraph(
  nodesIn: GraphNodeIn[],
  edgesIn: GraphEdgeIn[],
  width: number,
  height: number,
): LaidNode[] {
  const n = nodesIn.length
  if (n === 0) return []

  const ids = new Set(nodesIn.map((node) => node.id))
  const edges = edgesIn.filter((e) => ids.has(e.source) && ids.has(e.target))
  const degree = new Map<string, number>()
  for (const node of nodesIn) degree.set(node.id, 0)
  for (const e of edges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1)
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1)
  }

  const adj = new Map<string, string[]>()
  for (const node of nodesIn) adj.set(node.id, [])
  for (const e of edges) {
    adj.get(e.source)!.push(e.target)
    adj.get(e.target)!.push(e.source)
  }

  const hub = [...degree.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? nodesIn[0].id
  const layer = new Map<string, number>()
  const queue = [hub]
  layer.set(hub, 0)
  while (queue.length) {
    const cur = queue.shift()!
    const d = layer.get(cur) ?? 0
    for (const nxt of adj.get(cur) ?? []) {
      if (layer.has(nxt)) continue
      layer.set(nxt, d + 1)
      queue.push(nxt)
    }
  }
  for (const node of nodesIn) {
    if (!layer.has(node.id)) layer.set(node.id, 1)
  }

  const byLayer = new Map<number, GraphNodeIn[]>()
  for (const node of nodesIn) {
    const l = layer.get(node.id) ?? 1
    const list = byLayer.get(l) ?? []
    list.push(node)
    byLayer.set(l, list)
  }
  const maxLayer = Math.max(...byLayer.keys())
  const cx = width / 2
  const cy = height / 2
  const maxR = Math.min(width, height) / 2 - 36
  const ringGap = maxLayer > 0 ? maxR / (maxLayer + 0.35) : maxR

  const nodes: Array<LaidNode & { vx: number; vy: number }> = []
  for (const [l, group] of [...byLayer.entries()].sort((a, b) => a[0] - b[0])) {
    const radius = l === 0 ? 0 : ringGap * (l + 0.15)
    group.sort((a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0))
    group.forEach((node, i) => {
      const angle = (i / Math.max(group.length, 1)) * Math.PI * 2 - Math.PI / 2
      const jitter = l === 0 ? 0 : ((i % 3) - 1) * 6
      nodes.push({
        ...node,
        r: nodeRadius(node),
        x: cx + Math.cos(angle) * (radius + jitter),
        y: cy + Math.sin(angle) * (radius + jitter),
        vx: 0,
        vy: 0,
        lx: 0,
        ly: 0,
      })
    })
  }

  const gap = 16
  if (maxLayer >= 2) {
    fruchtermanReingold(nodes, [], width, height, 40)
  }
  resolveCollisions(nodes, width, height, gap)
  placeLabels(nodes, width, height)
  return nodes
}

export function canvasHeight(nodeCount: number): number {
  return Math.max(560, Math.min(1100, 420 + nodeCount * 5.5))
}
