import { useEffect, useMemo, useRef } from 'react'
import { EDGES, BYPASS_EDGE, W, H, edgeMode, agentSpeed, type Edge, type EdgeMode } from '../data/graphGeometry'
import type { NodeMap } from '../data/graphState'

/**
 * Colour-bead particle trails along the graph connectors, drawn by ONE rAF loop on ONE canvas
 * (no per-particle DOM, no React re-render per frame).
 *
 * Honest mapping (nothing decorative-random about the semantics):
 *  - hue      = the field agent the connector belongs to (same colour as its pill)
 *  - density  = connector state: ambient (sparse) / flowing (dense) / finished (medium) / dim (none)
 *  - speed    = flowing beads are faster for agents whose REAL duration_ms is shorter than the run median
 *  - flare    = a brief bright burst when a node completes (running -> done)
 */

const SAMPLES = 220

interface Bead { ph: number; sz: number; br: number }
interface Track {
  edge: Edge
  xs: Float32Array
  ys: Float32Array
  len: number
  off: number
  vis: number
  flare: number
  beads: Bead[]
}

const hash = (a: number, b: number) => {
  let x = Math.imul(a + 1, 374761393) ^ Math.imul(b + 7, 668265263)
  x = Math.imul(x ^ (x >>> 13), 1274126177)
  return ((x ^ (x >>> 16)) >>> 0) / 4294967296
}

function makeTrack(edge: Edge, idx: number): Track {
  const p = document.createElementNS('http://www.w3.org/2000/svg', 'path')
  p.setAttribute('d', edge.d)
  const len = p.getTotalLength()
  const xs = new Float32Array(SAMPLES)
  const ys = new Float32Array(SAMPLES)
  for (let i = 0; i < SAMPLES; i++) {
    const pt = p.getPointAtLength((i / (SAMPLES - 1)) * len)
    xs[i] = pt.x
    ys[i] = pt.y
  }
  const n = Math.max(8, Math.min(22, Math.round(len / 13)))
  const beads: Bead[] = Array.from({ length: n }, (_, k) => ({
    ph: (k + hash(idx, k) * 0.7) / n,
    sz: 1.15 + hash(idx * 31 + 5, k) * 1.3,
    br: 0.6 + hash(idx * 17 + 3, k) * 0.4,
  }))
  return { edge, xs, ys, len, off: hash(idx, 99), vis: 0, flare: -1e9, beads }
}

const spriteCache = new Map<string, HTMLCanvasElement>()
function sprite(color: string): HTMLCanvasElement {
  let s = spriteCache.get(color)
  if (s) return s
  s = document.createElement('canvas')
  s.width = s.height = 48
  const c = s.getContext('2d')!
  const g = c.createRadialGradient(24, 24, 0, 24, 24, 24)
  g.addColorStop(0, 'rgba(255,255,255,1)')
  g.addColorStop(0.16, color)
  g.addColorStop(0.42, color + '88')
  g.addColorStop(1, color + '00')
  c.fillStyle = g
  c.fillRect(0, 0, 48, 48)
  spriteCache.set(color, s)
  return s
}

const TARGET: Record<EdgeMode, { dens: number; speed: number }> = {
  ambient: { dens: 0.32, speed: 0.5 },
  flow: { dens: 1, speed: 1.75 },
  done: { dens: 0.6, speed: 0.85 },
  dim: { dens: 0, speed: 0.4 },
  error: { dens: 0.25, speed: 0.25 },
}
const BASE_PX_PER_S = 62

interface Props {
  nodes: NodeMap
  active: boolean
  bypass: boolean
  reduced: boolean
  scale: number
}

export default function BeadCanvas({ nodes, active, bypass, reduced, scale }: Props) {
  const ref = useRef<HTMLCanvasElement>(null)
  const tracks = useRef<Track[]>([])
  const live = useRef({ nodes, active, bypass, reduced })
  live.current = { nodes, active, bypass, reduced }
  const speeds = useMemo(() => agentSpeed(nodes), [nodes])
  const speedsRef = useRef(speeds)
  speedsRef.current = speeds
  const prev = useRef<Record<string, string>>({})
  const kick = useRef<() => void>(() => undefined)

  // build tracks once (needs DOM for path sampling)
  useEffect(() => {
    tracks.current = [...EDGES, BYPASS_EDGE].map((e, i) => makeTrack(e, i))
  }, [])

  // flare an edge when its source or destination node completes
  useEffect(() => {
    const now = performance.now()
    const cur: Record<string, string> = {}
    for (const [id, n] of Object.entries(nodes)) cur[id] = n.state
    if (active) {
      for (const t of tracks.current) {
        const a = t.edge.from, b = t.edge.to
        const doneNow = (id: string) => cur[id] === 'done' && prev.current[id] !== 'done'
        if (doneNow(a) || doneNow(b)) t.flare = now
      }
    }
    prev.current = cur
    kick.current()
  }, [nodes, active])

  // canvas sizing + the single animation loop
  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    // capped at 1.5 (not 2): full device pixel ratio here buys little visible sharpness for a soft
    // glow trail but roughly doubles fill-rate cost, which is what caused visible lag on weaker GPUs
    // during a fast multi-agent run.
    const dpr = Math.min(1.5, window.devicePixelRatio || 1)
    const sc = Math.max(0.3, scale)
    cv.width = Math.round(W * sc * dpr)
    cv.height = Math.round(H * sc * dpr)
    const ctx = cv.getContext('2d')!
    let raf = 0
    let last = performance.now()

    const draw = (now: number, dt: number, snap: boolean) => {
      const L = live.current
      ctx.setTransform(sc * dpr, 0, 0, sc * dpr, 0, 0)
      ctx.clearRect(0, 0, W, H)
      ctx.globalCompositeOperation = 'lighter'
      for (const t of tracks.current) {
        const isBypass = t.edge.id === 'bypass'
        let mode: EdgeMode = isBypass ? (L.active && L.bypass ? 'flow' : 'dim') : edgeMode(L.nodes[t.edge.from], L.nodes[t.edge.to], L.active)
        if (isBypass && !(L.active && L.bypass)) mode = 'dim'
        const tg = TARGET[mode]
        const flareAge = now - t.flare
        const flaring = flareAge < 1000 && mode !== 'dim'
        const fl = flaring ? 1 - flareAge / 1000 : 0
        const max = t.beads.length
        const targetVis = flaring ? max : tg.dens * max
        t.vis = snap ? targetVis : t.vis + (targetVis - t.vis) * Math.min(1, dt * 5)
        if (t.vis < 0.02) continue
        const ag = t.edge.agent ? speedsRef.current[t.edge.agent] ?? 1 : 1
        const speed = (mode === 'flow' ? tg.speed * ag : tg.speed) * (1 + fl * 1.4)
        if (!snap) t.off = (t.off + (dt * BASE_PX_PER_S * speed) / t.len) % 1
        const color = mode === 'error' ? '#ff5d73' : t.edge.color
        const sp = sprite(color)
        const boost = 1 + fl * 0.7
        for (let k = 0; k < t.beads.length; k++) {
          const a = Math.max(0, Math.min(1, t.vis - k))
          if (a <= 0) continue
          const b = t.beads[k]
          const u = (b.ph + t.off) % 1
          const edgeFade = Math.min(1, u / 0.05, (1 - u) / 0.05)
          const alpha = a * b.br * edgeFade
          if (alpha < 0.02) continue
          const r = b.sz * 3.6 * (1 + fl * 0.25)
          const segments = mode === 'flow' ? 2 : 3 // fewer trail segments while several agents run at once
          for (let g = 0; g < segments; g++) {
            const uu = u - g * 0.0075
            if (uu < 0) break
            const fi = uu * (SAMPLES - 1)
            const i0 = Math.floor(fi)
            const f = fi - i0
            const i1 = Math.min(SAMPLES - 1, i0 + 1)
            const x = t.xs[i0] + (t.xs[i1] - t.xs[i0]) * f
            const y = t.ys[i0] + (t.ys[i1] - t.ys[i0]) * f
            const rg = r * (1 - g * 0.22)
            ctx.globalAlpha = Math.min(1, alpha * boost * (g === 0 ? 1 : g === 1 ? 0.42 : 0.2))
            ctx.drawImage(sp, x - rg, y - rg, rg * 2, rg * 2)
          }
        }
      }
      ctx.globalAlpha = 1
      ctx.globalCompositeOperation = 'source-over'
    }

    let lastIdleDraw = 0
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop)
      // when nothing is processing, cap the ambient shimmer to ~15fps instead of 60fps: it still
      // reads as "alive" but doesn't burn a full frame budget on an idle screen.
      if (!live.current.active) {
        if (now - lastIdleDraw < 66) { last = now; return }
        lastIdleDraw = now
      }
      const dt = Math.min(0.06, (now - last) / 1000)
      last = now
      draw(now, dt, false)
    }
    if (reduced) {
      // one static frame per state change, no animation loop
      kick.current = () => { window.setTimeout(() => draw(performance.now() + 5000, 0, true), 30) }
      kick.current()
    } else {
      kick.current = () => undefined
      raf = requestAnimationFrame(loop)
    }
    return () => { cancelAnimationFrame(raf); kick.current = () => undefined }
  }, [scale, reduced])

  return <canvas ref={ref} className="beads" width={W} height={H} style={{ width: W, height: H }} aria-hidden="true" />
}
