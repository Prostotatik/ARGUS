import { useEffect, useMemo, useState } from 'react'
import { Bug, Info } from 'lucide-react'
import type { FlyBrain, FlyFeedback, GateInfo } from '../types'
import type { NodeState } from '../data/graphState'

const VW = 340
const VH = 232
const IN_X = 14
const CX = 166
const CY = 116
const RX = 74
const RY = 104
const DEC = { x: 312, y: 116 }
const MAX_KC = 110

const INPUT_HUES = [212, 38, 152, 318, 252, 128, 222, 44, 184, 8, 276, 96, 340, 62]
const GROUPS = [
  { key: 'mismatch', label: 'mismatch', color: '#ff5d73' },
  { key: 'low_conf', label: 'low conf', color: '#f5b324' },
  { key: 'near_miss', label: 'near-miss', color: '#b38bff' },
  { key: '', label: 'doc', color: '#4de3d1' },
]
const groupOf = (name: string) => GROUPS.find((g) => g.key && name.startsWith(g.key + ':')) ?? GROUPS[3]

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

interface Props {
  fly: FlyBrain | null
  gate: GateInfo | null
  gateState: NodeState
  reduced: boolean
  feedback: FlyFeedback | null
}

export default function FlyPanel({ fly, gate, gateState, reduced, feedback }: Props) {
  const nIn = fly?.n_inputs ?? 14
  const names = fly?.input_names ?? fly?.input_labels
  const iy = (i: number) => 14 + (i * (VH - 28)) / Math.max(1, nIn - 1)
  const rIn = Math.min(3.3, Math.max(1.5, ((VH - 28) / Math.max(1, nIn - 1)) * 0.42))
  const inColor = (i: number) => (names?.[i] ? groupOf(names[i]).color : `hsl(${INPUT_HUES[i % INPUT_HUES.length]} 92% 64%)`)

  const layout = useMemo(() => {
    if (!fly) return null
    const n = fly.n_kc
    const active = new Set(gate?.kc_active ?? [])
    const ids: number[] = []
    if (n <= MAX_KC) for (let i = 0; i < n; i++) ids.push(i)
    else {
      const step = n / MAX_KC
      const s = new Set<number>()
      for (let k = 0; k < MAX_KC; k++) s.add(Math.floor(k * step))
      active.forEach((a) => s.add(a))
      ids.push(...s)
    }
    const pos = new Map<number, { x: number; y: number }>()
    ids.forEach((i) => pos.set(i, kcPos(i)))
    const w = fly.weights ?? []
    const lo = w.length ? Math.min(...w) : 0
    const hi = w.length ? Math.max(...w) : 1
    const wn = (i: number) => (w.length && hi > lo ? (w[i] - lo) / (hi - lo) : 0.5)
    // static projection edges, one path per input
    const perIn: string[] = Array.from({ length: nIn }, () => '')
    ids.forEach((i) => {
      const p = pos.get(i)!
      for (const inp of fly.projection[i] ?? []) {
        if (inp < nIn) perIn[inp] += `M${IN_X + 4} ${iy(inp).toFixed(1)}L${p.x.toFixed(1)} ${p.y.toFixed(1)}`
      }
    })
    let toDec = ''
    ids.forEach((i) => {
      const p = pos.get(i)!
      toDec += `M${p.x.toFixed(1)} ${p.y.toFixed(1)}L${DEC.x - 10} ${DEC.y}`
    })
    return { ids, pos, wn, perIn, toDec }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fly, nIn, gate?.kc_active])

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

  const activeSet = useMemo(() => new Set(gate?.kc_active ?? []), [gate?.kc_active])
  const vec = gate?.input_vector ?? []
  const escalate = !!gate?.escalate
  const lit = gate != null && gateState === 'done'
  const susp = gate?.suspicion ?? 0
  const thr = gate?.threshold ?? fly?.threshold ?? 0.5
  const note =
    gateState === 'skipped' ? 'Gate not used: this email is not a document comparison.'
      : gateState === 'pending' ? 'Waiting for the aggregator...'
        : !gate ? 'Idle. Select a comparison email to light the gate.'
          : ''
  const lastHist = fly?.history?.[fly.history.length - 1]

  return (
    <section className={`fly panel${lit ? ' lit' : ''}${escalate ? ' esc' : ''}`} aria-label="Fruit fly olfactory network confidence gate" data-phase={phase}>
      <header className="panel-h">
        <h2>Fruit Fly Olfactory Network</h2>
        <span className="info" title="Our own small network in the style of the fly olfactory circuit (sparse projection, Kenyon cells, winner-take-all, Hebbian update). Not real fly or connectome data." tabIndex={0} aria-label="About this network"><Info size={13} /></span>
      </header>

      <div className="fly-lbl-l">
        Inputs{names ? <> ({nIn}){GROUPS.map((g) => <span key={g.label} className="lg"><i style={{ background: g.color }} />{g.label}</span>)}</> : null}
      </div>
      <div className="fly-body">
        <div className="fly-gate" aria-live="polite">
          <span className="fg-t">Confidence Gate</span>
          {lit ? (
            <>
              <strong className={escalate ? 'warn' : 'ok'}>{susp.toFixed(2)}</strong>
              <span className="fg-s">suspicion &middot; threshold {thr.toFixed(2)}</span>
              <span className={`fg-v ${escalate ? 'warn' : 'ok'}`}>{escalate ? 'Escalate to human' : 'Confident'}</span>
            </>
          ) : (
            <span className="fg-s dim">{note}</span>
          )}
        </div>

        <svg className="fly-svg" viewBox={`0 0 ${VW} ${VH}`} role="img" aria-label={lit ? `Gate decision: suspicion ${susp.toFixed(2)} versus threshold ${thr.toFixed(2)}, ${escalate ? 'escalate' : 'confident'}` : 'Fly network idle'}>
          <defs>
            <radialGradient id="decg"><stop offset="0" stopColor="#fff" /><stop offset=".35" stopColor="var(--dec)" /><stop offset="1" stopColor="var(--dec)" stopOpacity="0" /></radialGradient>
            <filter id="flyglow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.2" /></filter>
          </defs>
          {layout && (
            <>
              <g className="f-proj">
                {layout.perIn.map((d, i) => d && <path key={i} d={d} stroke={inColor(i)} className={`f-pe${vec[i] > 0.5 && phase >= 1 ? ' hot' : ''}`} />)}
              </g>
              <path d={layout.toDec} className="f-dec-all" />
              {phase >= 2 && (
                <g className="f-active">
                  {layout.ids.filter((i) => activeSet.has(i)).map((i) => {
                    const p = layout.pos.get(i)!
                    const w = i === gate?.winner_kc
                    return (
                      <g key={i}>
                        {(fly?.projection[i] ?? []).filter((x) => x < nIn).map((x, k) => (
                          <line key={k} x1={IN_X + 4} y1={iy(x)} x2={p.x} y2={p.y} stroke={inColor(x)} className="f-ae" />
                        ))}
                        <line x1={p.x} y1={p.y} x2={DEC.x - 10} y2={DEC.y} className={`f-ad${w ? ' win' : ''}`} />
                      </g>
                    )
                  })}
                </g>
              )}
              <g className="f-kcs">
                {layout.ids.map((i) => {
                  const p = layout.pos.get(i)!
                  const on = phase >= 2 && activeSet.has(i)
                  const win = on && i === gate?.winner_kc
                  const r = 1.8 + layout.wn(i) * 1.6
                  return (
                    <g key={i}>
                      {on && <circle cx={p.x} cy={p.y} r={r + 4} className={`f-kc-halo${win ? ' win' : ''}`} filter="url(#flyglow)" />}
                      <circle cx={p.x} cy={p.y} r={win ? r + 1.6 : r} className={`f-kc${on ? ' on' : ''}${win ? ' win' : ''}${feedback && on ? ' upd' : ''}`}>
                        <title>{`Kenyon cell ${i}${on ? ' (active)' : ''}${fly?.weights ? `, weight ${fly.weights[i]?.toFixed(3)}` : ''}`}</title>
                      </circle>
                    </g>
                  )
                })}
              </g>
            </>
          )}
          <g className="f-in">
            {Array.from({ length: nIn }, (_, i) => {
              const v = vec[i] ?? 0
              const on = phase >= 1 && v > 0.05
              const label = names?.[i]
              return (
                <g key={i}>
                  {on && <circle cx={IN_X} cy={iy(i)} r={rIn * 2.1} fill={inColor(i)} opacity={0.25 * Math.min(1, v + 0.3)} filter="url(#flyglow)" />}
                  <circle cx={IN_X} cy={iy(i)} r={rIn} fill={inColor(i)} opacity={phase >= 1 ? 0.35 + 0.65 * Math.min(1, v) : 0.45} className="f-ind">
                    <title>{label ? `${label}: ${v.toFixed(2)}` : `Input ${i + 1}${gate ? `: ${v.toFixed(2)}` : ''}`}</title>
                  </circle>
                </g>
              )
            })}
          </g>
          <g className="f-decision" style={{ '--dec': escalate ? '#f5b324' : '#4d8dff' } as React.CSSProperties}>
            <circle cx={DEC.x} cy={DEC.y} r={20} fill="url(#decg)" className={`f-dec-glow${phase >= 3 ? ' on' : ''}`} />
            <circle cx={DEC.x} cy={DEC.y} r={7.5} className={`f-dec${phase >= 3 ? ' on' : ''}`} />
            {phase >= 3 && !reduced && <circle cx={DEC.x} cy={DEC.y} r={8} className="f-dec-ring" />}
          </g>
        </svg>
      </div>

      <div className="meter" aria-hidden="true">
        <div className="m-track">
          <div className={`m-fill ${escalate ? 'warn' : 'ok'}`} style={{ width: `${lit ? Math.min(100, susp * 100) : 0}%` }} />
          <div className="m-thr" style={{ left: `${thr * 100}%` }} title={`threshold ${thr.toFixed(2)}`} />
        </div>
        <div className="m-lbl"><span>0</span><span>escalation threshold {thr.toFixed(2)}</span><span>1</span></div>
      </div>

      {feedback ? (
        <div className="fly-fb" role="status">
          <b>Weights updated</b> after human verdict <em>{feedback.verdict.replace('_', ' ')}</em>: suspicion {feedback.before.toFixed(2)} &rarr; {feedback.after.toFixed(2)}
          {feedback.simulated && <span className="sim" title="REPLAY/mock mode has no backend: this update is simulated locally">simulated</span>}
        </div>
      ) : lastHist ? (
        <div className="fly-fb dim">Last human verdict ({lastHist.verdict.replace('_', ' ')}): {lastHist.before.toFixed(2)} &rarr; {lastHist.after.toFixed(2)}</div>
      ) : null}

      <footer className="fly-foot">
        <Bug size={15} strokeWidth={1.6} aria-hidden="true" />
        <p>Architecture inspired by the fruit fly's olfactory system.<br /><span>{fly?.schematic ? 'Schematic layout (no network file found).' : `${layout ? layout.ids.length : 0} of ${fly?.n_kc ?? '-'} Kenyon cells drawn`}</span></p>
        <svg viewBox="0 0 80 24" className="wave" aria-hidden="true"><path d="M0 12h14l4-9 5 18 5-14 4 8 4-3h44" /></svg>
      </footer>
    </section>
  )
}
