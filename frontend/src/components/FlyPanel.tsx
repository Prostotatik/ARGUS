import { memo, useEffect, useMemo, useRef, useState } from 'react'
import { Bug, Info } from 'lucide-react'
import type { FlyBrain, FlyFeedback, GateInfo } from '../types'
import { FIELD_LABEL, type NodeState } from '../data/graphState'
import CountUp from './CountUp'

const VW = 340
const VH = 232
const IN_X = 14
const CX = 168
const CY = 118
const RX = 78
const RY = 104
const DEC = { x: 312, y: 118 }
const APL = { x: CX, y: 7 }

const INPUT_HUES = [212, 38, 152, 318, 252, 128, 222, 44, 184, 8, 276, 96, 340, 62]
const GROUPS = [
  { key: 'mismatch', label: 'mismatch', color: '#ff5d73' },
  { key: 'low_conf', label: 'low conf', color: '#f5b324' },
  { key: 'near_miss', label: 'near-miss', color: '#b38bff' },
  { key: '', label: 'doc', color: '#4de3d1' },
]
const groupOf = (name: string) => GROUPS.find((g) => g.key && name.startsWith(g.key + ':')) ?? GROUPS[3]

/** "mismatch:port_of_loading" -> "mismatch · Port of Loading"; "engine_fallback" -> "engine fallback" */
function prettyInput(name: string): string {
  const [g, f] = name.split(':')
  if (f) return `${g.replace(/_/g, ' ')} · ${(FIELD_LABEL as Record<string, string>)[f] ?? f}`
  return name.replace(/_/g, ' ')
}

function hash01(n: number): number {
  let x = (n + 1) * 2654435761
  x ^= x >>> 15
  x = Math.imul(x, 2246822519)
  x ^= x >>> 13
  x = Math.imul(x, 3266489917)
  x ^= x >>> 16
  return ((x >>> 0) % 100000) / 100000
}

function kcPos(i: number) {
  const a = hash01(i * 2 + 1) * Math.PI * 2
  const rr = Math.sqrt(hash01(i * 2 + 2))
  const lens = 1 - 0.55 * Math.pow(rr * Math.cos(a), 2)
  return { x: CX + RX * rr * Math.cos(a), y: CY + RY * rr * Math.sin(a) * lens }
}

/** smooth horizontal S-curve, like the reference's converging fibres */
const curve = (x0: number, y0: number, x1: number, y1: number) => {
  const dx = x1 - x0
  return `M${x0.toFixed(1)} ${y0.toFixed(1)}C${(x0 + dx * 0.55).toFixed(1)} ${y0.toFixed(1)} ${(x1 - dx * 0.45).toFixed(1)} ${y1.toFixed(1)} ${x1.toFixed(1)} ${y1.toFixed(1)}`
}

interface Layout {
  n: number
  nIn: number
  px: Float32Array
  py: Float32Array
  iy: (i: number) => number
  /** readers[input] = KC indices whose projection contains that input (real wiring, all n_kc) */
  readers: number[][]
}

function buildLayout(fly: FlyBrain, nIn: number): Layout {
  const n = fly.n_kc
  const px = new Float32Array(n)
  const py = new Float32Array(n)
  const readers: number[][] = Array.from({ length: nIn }, () => [])
  for (let i = 0; i < n; i++) {
    const p = kcPos(i)
    px[i] = p.x
    py[i] = p.y
    for (const inp of fly.projection[i] ?? []) if (inp < nIn) readers[inp].push(i)
  }
  const iy = (i: number) => 14 + (i * (VH - 28)) / Math.max(1, nIn - 1)
  return { n, nIn, px, py, iy, readers }
}

// ---------------------------------------------------------------- static network (one canvas, all Kenyon cells)
interface NetProps {
  layout: Layout
  fly: FlyBrain
  inColor: (i: number) => string
}
const StaticNet = memo(function StaticNet({ layout, fly, inColor }: NetProps) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const cv = ref.current
    if (!cv) return
    const dpr = Math.min(2, window.devicePixelRatio || 1)
    const k = Math.max(1, cv.clientWidth / VW) * dpr
    cv.width = Math.round(VW * k)
    cv.height = Math.round(VH * k)
    const c = cv.getContext('2d')!
    c.setTransform(k, 0, 0, k, 0, 0)
    c.clearRect(0, 0, VW, VH)
    c.globalCompositeOperation = 'lighter'
    const { n, nIn, px, py, iy } = layout
    // projection fibres: one stroke per input, additive so overlap reads as luminous density
    const alpha = n > 400 ? 0.05 : 0.3
    c.lineWidth = 0.5
    for (let inp = 0; inp < nIn; inp++) {
      c.beginPath()
      for (let j = 0; j < n; j++) {
        const pr = fly.projection[j]
        if (!pr || !pr.includes(inp)) continue
        const x0 = IN_X + 4, y0 = iy(inp), x1 = px[j], y1 = py[j]
        const dx = x1 - x0
        c.moveTo(x0, y0)
        c.bezierCurveTo(x0 + dx * 0.55, y0, x1 - dx * 0.45, y1, x1, y1)
      }
      c.strokeStyle = inColor(inp)
      c.globalAlpha = alpha
      c.stroke()
    }
    // KC -> decision fibres
    c.beginPath()
    for (let j = 0; j < n; j++) {
      const x1 = DEC.x - 10, y1 = DEC.y, x0 = px[j], y0 = py[j]
      const dx = x1 - x0
      c.moveTo(x0, y0)
      c.bezierCurveTo(x0 + dx * 0.55, y0, x1 - dx * 0.45, y1, x1, y1)
    }
    c.strokeStyle = '#6a92ff'
    c.globalAlpha = n > 400 ? 0.035 : 0.22
    c.lineWidth = 0.45
    c.stroke()
    // Kenyon cells: brightness follows the learned KC->decision weight (novel = bright, familiar/depressed = dim)
    const w = fly.weights
    const lo = w?.length ? Math.min(...w) : 0
    const hi = w?.length ? Math.max(...w) : 1
    const buckets: number[][] = [[], [], [], []]
    for (let j = 0; j < n; j++) {
      const t = w && hi > lo ? (w[j] - lo) / (hi - lo) : 0.6
      buckets[Math.min(3, Math.floor(t * 3.999))].push(j)
    }
    const rad = n > 400 ? 1.15 : 2.4
    const cols = ['#2c3f86', '#3a56c4', '#5478ea', '#86aaff']
    c.globalCompositeOperation = 'source-over'
    buckets.forEach((b, bi) => {
      c.globalAlpha = 0.1 + bi * 0.03
      c.fillStyle = cols[bi]
      c.beginPath()
      for (const j of b) { c.moveTo(px[j] + rad * 2.4, py[j]); c.arc(px[j], py[j], rad * 2.4, 0, 6.2832) }
      c.fill()
      c.globalAlpha = 0.5 + bi * 0.14
      c.beginPath()
      for (const j of b) { c.moveTo(px[j] + rad, py[j]); c.arc(px[j], py[j], rad, 0, 6.2832) }
      c.fill()
    })
    c.globalAlpha = 1
    c.globalCompositeOperation = 'source-over'
  }, [layout, fly, inColor])
  return <canvas ref={ref} className="fly-canvas" aria-hidden="true" />
})

interface Props {
  fly: FlyBrain | null
  gate: GateInfo | null
  gateState: NodeState
  reduced: boolean
  feedback: FlyFeedback | null
  /** REPLAY only: drop the locally taught weights */
  onResetTaught?: () => void
}

type Hover = { kind: 'kc'; i: number } | { kind: 'in'; i: number } | null

export default function FlyPanel({ fly, gate, gateState, reduced, feedback, onResetTaught }: Props) {
  const nIn = fly?.n_inputs ?? 14
  const names = fly?.input_names ?? fly?.input_labels
  const inColor = useMemo(
    () => (i: number) => (names?.[i] ? groupOf(names[i]).color : `hsl(${INPUT_HUES[i % INPUT_HUES.length]} 92% 64%)`),
    [names],
  )
  const layout = useMemo(() => (fly ? buildLayout(fly, nIn) : null), [fly?.n_kc, fly?.projection, nIn]) // eslint-disable-line react-hooks/exhaustive-deps
  const iy = layout?.iy ?? ((i: number) => 14 + (i * (VH - 28)) / Math.max(1, nIn - 1))
  const rIn = Math.min(3.3, Math.max(1.5, ((VH - 28) / Math.max(1, nIn - 1)) * 0.42))

  // staged activation: inputs -> KCs -> decision
  const gateKey = gate ? `${gate.suspicion}|${(gate.kc_active ?? []).join(',')}|${gate.winner_kc}` : ''
  const [phase, setPhase] = useState(0)
  useEffect(() => {
    if (!gate || gateState === 'idle' || gateState === 'pending' || gateState === 'skipped') { setPhase(0); return }
    if (reduced) { setPhase(3); return }
    setPhase(0)
    const t1 = window.setTimeout(() => setPhase(1), 40)
    const t2 = window.setTimeout(() => setPhase(2), 420)
    const t3 = window.setTimeout(() => setPhase(3), 820)
    return () => { window.clearTimeout(t1); window.clearTimeout(t2); window.clearTimeout(t3) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gateKey, gateState, reduced])

  const activeList = gate?.kc_active
  const activeSet = useMemo(() => new Set(activeList ?? []), [activeList])
  const vec = gate?.input_vector ?? []
  const escalate = !!gate?.escalate
  const lit = gate != null && gateState === 'done'
  const thr = gate?.threshold ?? fly?.threshold ?? 0.5

  // suspicion shown: the recorded one, except in a locally-taught REPLAY session where we re-evaluate with the taught weights
  const taughtSusp = useMemo(() => {
    if (!fly?.taught || !fly.weights || !activeList?.length) return null
    const k = Math.round(fly.n_kc * (fly.kc_sparsity ?? 0.05))
    const tau = fly.tau ?? 0.15 * k
    return 1 - Math.exp(-activeList.reduce((a, i) => a + (fly.weights![i] ?? 0), 0) / tau)
  }, [fly, activeList])
  const susp = taughtSusp ?? gate?.suspicion ?? 0
  const shownSusp = feedback ? feedback.after : susp

  // hover: which inputs feed a Kenyon cell / which cells an input feeds (real wiring from flybrain.json)
  const [hover, setHover] = useState<Hover>(null)
  const [tip, setTip] = useState<{ x: number; y: number } | null>(null)
  const bodyRef = useRef<HTMLDivElement>(null)
  const raf = useRef(0)
  const onMove = (e: React.PointerEvent) => {
    if (!layout || !bodyRef.current) return
    const r = bodyRef.current.getBoundingClientRect()
    const cx = e.clientX, cy = e.clientY
    if (raf.current) return
    raf.current = requestAnimationFrame(() => {
      raf.current = 0
      const x = ((cx - r.left) / r.width) * VW
      const y = ((cy - r.top) / r.height) * VH
      let h: Hover = null
      if (x < IN_X + 14) {
        let best = -1, bd = (VH / nIn) * 0.75 + 1
        for (let i = 0; i < nIn; i++) { const d = Math.abs(layout.iy(i) - y); if (d < bd) { bd = d; best = i } }
        if (best >= 0) h = { kind: 'in', i: best }
      } else {
        let best = -1, bd = 6.5 * 6.5
        for (let i = 0; i < layout.n; i++) {
          const dx = layout.px[i] - x, dy = layout.py[i] - y
          let d = dx * dx + dy * dy
          if (activeSet.has(i)) d *= 0.4
          if (d < bd) { bd = d; best = i }
        }
        if (best >= 0) h = { kind: 'kc', i: best }
      }
      setHover((p) => (p?.kind === h?.kind && p?.i === h?.i ? p : h))
      setTip(h ? { x: cx - r.left, y: cy - r.top } : null)
    })
  }
  const onLeave = () => { setHover(null); setTip(null) }

  const hoverKcInputs = hover?.kind === 'kc' && fly ? (fly.projection[hover.i] ?? []).filter((x) => x < nIn) : []
  const hoverReaders = hover?.kind === 'in' && layout ? layout.readers[hover.i] : []
  const readersActive = hoverReaders.filter((k) => activeSet.has(k)).length

  const note =
    gateState === 'skipped' ? 'Gate not used: this email is not a document comparison.'
      : gateState === 'pending' ? 'Waiting for the aggregator...'
        : !gate ? 'Idle. Select a comparison email to light the gate.'
          : ''
  const lastHist = fly?.history?.[fly.history.length - 1]
  const kcd = feedback?.kc
  const drawn = layout ? layout.n : 0

  const tipBox = (() => {
    if (!tip || !hover || !fly) return null
    const w = bodyRef.current?.clientWidth ?? 320
    const left = Math.max(4, Math.min(w - 236, tip.x + 14))
    const top = Math.max(2, tip.y - 6)
    let inner: React.ReactNode = null
    if (hover.kind === 'kc') {
      const wgt = fly.weights?.[hover.i]
      const on = activeSet.has(hover.i)
      inner = (
        <>
          <b>Kenyon cell #{hover.i}{on ? <em className="on">firing</em> : null}{gate?.winner_kc === hover.i ? <em className="win">winner</em> : null}</b>
          <span>KC&rarr;decision weight <strong>{wgt != null ? wgt.toFixed(2) : 'n/a'}</strong>{wgt != null ? (wgt >= 0.5 ? ' (novel: pushes suspicion up)' : ' (familiar: depressed)') : ''}</span>
          <span className="sub">reads {hoverKcInputs.length} inputs</span>
          <ul>
            {hoverKcInputs.map((x) => (
              <li key={x}><i style={{ background: inColor(x) }} />{names?.[x] ? prettyInput(names[x]) : `input ${x + 1}`}{lit ? <strong>{(vec[x] ?? 0).toFixed(2)}</strong> : null}</li>
            ))}
          </ul>
        </>
      )
    } else {
      const v = vec[hover.i]
      const drv = gate?.drivers?.find((d) => d.index === hover.i)
      inner = (
        <>
          <b>{names?.[hover.i] ? prettyInput(names[hover.i]) : `Input ${hover.i + 1}`}</b>
          {lit && v != null ? <span>current value <strong>{v.toFixed(2)}</strong>{v > 0.25 ? ' (drives the gate)' : ' (below the 0.25 floor)'}</span> : <span className="sub">no email evaluated yet</span>}
          {lit && drv && <span>share of the drive <strong>{Math.round(drv.share * 100)}%</strong></span>}
          <span className="sub">wired to {hoverReaders.length} of {fly.n_kc} Kenyon cells{lit ? `, ${readersActive} firing now` : ''}</span>
        </>
      )
    }
    return <div className="fly-tip" style={{ left, top }} role="tooltip">{inner}</div>
  })()

  return (
    <section className={`fly panel${lit ? ' lit' : ''}${escalate ? ' esc' : ''}`} aria-label="Fruit fly olfactory network confidence gate" data-phase={phase}>
      <header className="panel-h">
        <h2>Fruit Fly Olfactory Network</h2>
        <span className="info" title="Our own small network in the style of the fly olfactory circuit (sparse projection, Kenyon cells, APL-style inhibition and winner-take-all, Hebbian update). Not real fly or connectome data. Hover an input or a Kenyon cell to see its real wiring." tabIndex={0} aria-label="About this network"><Info size={13} /></span>
      </header>

      <div className="fly-lbl-l">
        Inputs{names ? <> ({nIn}){GROUPS.map((g) => <span key={g.label} className="lg"><i style={{ background: g.color }} />{g.label}</span>)}</> : null}
      </div>
      <div className="fly-body" ref={bodyRef} onPointerMove={onMove} onPointerLeave={onLeave}>
        <div className="fly-gate" aria-live="polite">
          <span className="fg-t">Confidence Gate{lit && taughtSusp != null && !feedback && <em className="fg-sim" title="Re-evaluated with the weights you taught this session. REPLAY cannot change the backend; the documented update rule is applied locally.">simulated</em>}</span>
          {lit ? (
            <>
              <strong className={escalate ? 'warn' : 'ok'}><CountUp value={shownSusp} decimals={2} ms={feedback ? 1100 : 650} /></strong>
              <span className="fg-s">suspicion &middot; threshold {thr.toFixed(2)}</span>
              <span className={`fg-v ${escalate ? 'warn' : 'ok'}`}>{escalate ? 'Escalate to human' : 'Confident'}</span>
            </>
          ) : (
            <span className="fg-s dim">{note}</span>
          )}
        </div>

        {layout && fly && <StaticNet layout={layout} fly={fly} inColor={inColor} />}

        <svg className="fly-svg" viewBox={`0 0 ${VW} ${VH}`} role="img" aria-label={lit ? `Gate decision: suspicion ${shownSusp.toFixed(2)} versus threshold ${thr.toFixed(2)}, ${escalate ? 'escalate' : 'confident'}` : 'Fly network idle'}>
          <defs>
            <radialGradient id="decg"><stop offset="0" stopColor="#fff" /><stop offset=".35" stopColor="var(--dec)" /><stop offset="1" stopColor="var(--dec)" stopOpacity="0" /></radialGradient>
            <filter id="flyglow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2" /></filter>
          </defs>

          {/* APL: global feedback inhibition (only 5% of Kenyon cells stay active) */}
          <g className={`f-apl${phase >= 2 ? ' on' : ''}`}>
            <title>APL-style global inhibition: silences all but the strongest ~5% of Kenyon cells (winner-take-all)</title>
            <circle cx={APL.x} cy={APL.y} r={3.6} />
            <text x={APL.x + 8} y={APL.y + 4}>APL</text>
          </g>

          {layout && fly && lit && phase >= 1 && (
            <g className="f-active">
              {(activeList ?? []).map((i) => {
                const win = i === gate?.winner_kc
                return (
                  <g key={i}>
                    {phase >= 2 && (fly.projection[i] ?? []).filter((x) => x < nIn).map((x, k) => (
                      <path key={k} d={curve(IN_X + 4, iy(x), layout.px[i], layout.py[i])} fill="none" stroke={inColor(x)} className="f-ae" />
                    ))}
                    {phase >= 2 && <path d={curve(layout.px[i], layout.py[i], DEC.x - 10, DEC.y)} fill="none" className={`f-ad${win ? ' win' : ''}`} />}
                    {phase >= 2 && <path d={`M${layout.px[i].toFixed(1)} ${layout.py[i].toFixed(1)}L${APL.x} ${APL.y + 3}`} className="f-apl-l" />}
                  </g>
                )
              })}
            </g>
          )}

          {layout && fly && lit && phase >= 2 && (
            <g className="f-kcs">
              {(activeList ?? []).map((i) => {
                const win = i === gate?.winner_kc
                const d = kcd?.find((k) => k.i === i)
                const r = 2.6 + (fly.weights?.[i] ?? 0.5) * 1.2
                const style = d ? ({ '--from': d.before >= 0.5 ? '#9fc3ff' : '#4a5fae', '--to': d.after >= 0.5 ? '#9fc3ff' : '#4a5fae' } as React.CSSProperties) : undefined
                return (
                  <g key={i}>
                    <circle cx={layout.px[i]} cy={layout.py[i]} r={r + 4} className={`f-kc-halo${win ? ' win' : ''}`} filter="url(#flyglow)" />
                    <circle cx={layout.px[i]} cy={layout.py[i]} r={win ? r + 1.4 : r} className={`f-kc on${win ? ' win' : ''}${d ? ' upd' : ''}`} style={style} />
                    {d && <circle cx={layout.px[i]} cy={layout.py[i]} r={r + 1} className={`f-heb ${d.after < d.before ? 'ltd' : 'ltp'}`} style={{ animationDelay: `${(activeList ?? []).indexOf(i) * 55}ms` }} />}
                  </g>
                )
              })}
              {kcd && gate?.winner_kc != null && layout && (() => {
                const d = kcd.find((k) => k.i === gate.winner_kc)
                if (!d) return null
                const x = Math.min(VW - 76, Math.max(4, layout.px[gate.winner_kc] + 8))
                return <text x={x} y={Math.max(12, layout.py[gate.winner_kc] - 8)} className="f-heb-t" key={`t${feedback?.nonce}`}>w {d.before.toFixed(2)} &rarr; {d.after.toFixed(2)}</text>
              })()}
            </g>
          )}

          {/* hover highlight: the real wiring of the cell / input under the pointer */}
          {layout && fly && hover?.kind === 'kc' && (
            <g className="f-hov">
              {hoverKcInputs.map((x) => <path key={x} d={curve(IN_X + 4, iy(x), layout.px[hover.i], layout.py[hover.i])} fill="none" stroke={inColor(x)} className="f-hov-e" />)}
              <path d={curve(layout.px[hover.i], layout.py[hover.i], DEC.x - 10, DEC.y)} fill="none" className="f-hov-d" />
              <circle cx={layout.px[hover.i]} cy={layout.py[hover.i]} r={5.2} className="f-hov-ring" />
              {hoverKcInputs.map((x) => <circle key={`c${x}`} cx={IN_X} cy={iy(x)} r={rIn + 2.4} className="f-hov-ring" style={{ stroke: inColor(x) }} />)}
            </g>
          )}
          {layout && hover?.kind === 'in' && (
            <g className="f-hov">
              {hoverReaders.slice(0, 260).map((k) => <circle key={k} cx={layout.px[k]} cy={layout.py[k]} r={activeSet.has(k) ? 3.1 : 1.9} className={`f-hov-kc${activeSet.has(k) ? ' act' : ''}`} style={{ fill: inColor(hover.i) }} />)}
              <circle cx={IN_X} cy={iy(hover.i)} r={rIn + 3} className="f-hov-ring" style={{ stroke: inColor(hover.i) }} />
            </g>
          )}

          <g className="f-in">
            {Array.from({ length: nIn }, (_, i) => {
              const v = vec[i] ?? 0
              const on = phase >= 1 && v > 0.05
              const label = names?.[i]
              return (
                <g key={i}>
                  {on && <circle cx={IN_X} cy={iy(i)} r={rIn * 2.1} fill={inColor(i)} opacity={0.25 * Math.min(1, v + 0.3)} filter="url(#flyglow)" />}
                  <circle cx={IN_X} cy={iy(i)} r={rIn} fill={inColor(i)} opacity={phase >= 1 ? 0.35 + 0.65 * Math.min(1, v) : 0.5} className="f-ind">
                    <title>{label ? `${prettyInput(label)}: ${v.toFixed(2)}` : `Input ${i + 1}${gate ? `: ${v.toFixed(2)}` : ''}`}</title>
                  </circle>
                </g>
              )
            })}
          </g>
          <g className="f-decision" style={{ '--dec': escalate ? '#f5b324' : '#4d8dff' } as React.CSSProperties}>
            <circle cx={DEC.x} cy={DEC.y} r={17} className="f-dec-halo" />
            <circle cx={DEC.x} cy={DEC.y} r={26} fill="url(#decg)" className={`f-dec-glow${phase >= 3 ? ' on' : ''}`} />
            <circle cx={DEC.x} cy={DEC.y} r={7.5} className={`f-dec${phase >= 3 ? ' on' : ''}`} />
            {phase >= 3 && !reduced && <circle cx={DEC.x} cy={DEC.y} r={8} className="f-dec-ring" />}
          </g>
        </svg>
        {tipBox}
      </div>

      <div className="meter" aria-hidden="true">
        <div className="m-track">
          <div className={`m-fill ${escalate ? 'warn' : 'ok'}`} style={{ transform: `scaleX(${lit ? Math.min(1, shownSusp) : 0})` }} />
          <div className="m-thr" style={{ left: `${thr * 100}%` }} title={`threshold ${thr.toFixed(2)}`} />
        </div>
      </div>

      {feedback?.skippedReason ? (
        <div className="fly-fb dim" role="status" key={feedback.nonce}>
          <b>No fly-net weight update</b> &mdash; {feedback.skippedReason}
        </div>
      ) : feedback ? (
        <div className="fly-fb" role="status" key={feedback.nonce}>
          <b>Weights updated</b> after human verdict <em>{feedback.verdict.replace(/_/g, ' ')}</em>: suspicion {feedback.before.toFixed(2)} &rarr; {feedback.after.toFixed(2)}
          {kcd && kcd.length > 0 && <> &middot; {kcd.length} Kenyon cells, mean weight {(kcd.reduce((a, k) => a + k.before, 0) / kcd.length).toFixed(2)} &rarr; {(kcd.reduce((a, k) => a + k.after, 0) / kcd.length).toFixed(2)}</>}
          {feedback.simulated && <span className="sim" title="REPLAY/mock mode has no backend: the documented Hebbian rule is applied to the exported weights locally">simulated</span>}
          {feedback.simulated && onResetTaught && <button type="button" className="linkbtn" onClick={onResetTaught}>Reset</button>}
        </div>
      ) : fly?.taught && onResetTaught ? (
        <div className="fly-fb dim">Net taught in this session (simulated locally). <button type="button" className="linkbtn" onClick={onResetTaught}>Reset weights</button></div>
      ) : lastHist ? (
        <div className="fly-fb dim">Last human verdict ({lastHist.verdict.replace(/_/g, ' ')}): {lastHist.before.toFixed(2)} &rarr; {lastHist.after.toFixed(2)}</div>
      ) : null}

      <footer className="fly-foot">
        <Bug size={22} strokeWidth={1.3} aria-hidden="true" className="fly-glyph" />
        <p>Architecture inspired by the fruit fly's olfactory system.<br /><span>{fly?.schematic ? 'Schematic layout (no network file found).' : `${drawn} of ${fly?.n_kc ?? '-'} Kenyon cells drawn · hover to inspect`}</span></p>
        <svg viewBox="0 0 90 28" className="wave" aria-hidden="true"><path d="M0 14h22l3-5 3 11 4-19 4 25 4-20 3 9 3-5h43" /></svg>
      </footer>
    </section>
  )
}
