import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import type { FieldResult, Mode, Result } from '../types'
import { FIELD_KEYS, type FieldKey } from '../types'
import {
  FIELD_COLOR, FIELD_LABEL, fmtMs, type NodeInfo, type NodeMap,
} from '../data/graphState'
import {
  BYPASS_EDGE, EDGES, H, PILL_H, PILL_W, PILL_X, POS, W, edgeMode, pillY,
} from '../data/graphGeometry'
import { FIELD_ICON, NODE_ICON } from './icons'
import NodePopover from './NodePopover'
import BeadCanvas from './BeadCanvas'

/** engine that produced most LLM-capable nodes (classifier + 7 field agents) of this run */
function runDefaultEngine(nodes: NodeMap): string | null {
  const count: Record<string, number> = {}
  for (const id of ['classifier', ...FIELD_KEYS.map((k) => `field:${k}`)]) {
    const n = nodes[id]
    if (n?.engine && (n.state === 'done' || n.state === 'error' || n.state === 'running')) count[n.engine] = (count[n.engine] ?? 0) + 1
  }
  const top = Object.entries(count).sort((a, b) => b[1] - a[1])[0]
  return top ? top[0] : null
}

/** true once, for ~1s, when a node goes running -> done (drives the completion ripple) */
function useCompletion(state: string): number {
  const prev = useRef(state)
  const [k, setK] = useState(0)
  useEffect(() => {
    if (prev.current === 'running' && state === 'done') setK((x) => x + 1)
    prev.current = state
  }, [state])
  return k
}

const Ripples = ({ k }: { k: number }) => (k > 0 ? <><span key={`a${k}`} className="ripple" aria-hidden="true" /><span key={`b${k}`} className="ripple r2" aria-hidden="true" /></> : null)

interface Props {
  nodes: NodeMap
  active: boolean
  running: boolean
  reduced: boolean
  mode: Mode
  totalEmails: number
  emailLabel: string | null
  result: Result | null
  onRetry: () => void
  onOpenReport: () => void
}

export default function GraphPanel({ nodes, active, running, reduced, mode, totalEmails, emailLabel, result, onRetry, onOpenReport }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)
  const [box, setBox] = useState({ w: W, h: H })
  const [hover, setHover] = useState<{ id: string; rect: DOMRect } | null>(null)
  const [pinned, setPinned] = useState<{ id: string; rect: DOMRect } | null>(null)
  const leaveTimer = useRef<number | null>(null)

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect()
      setBox({ w: r.width, h: r.height })
      setScale(Math.max(r.width < 700 ? 0.62 : 0.35, Math.min(r.width / W, r.height / H)))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { setPinned(null); setHover(null) } }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const rectOf = (el: HTMLElement) => {
    const p = panelRef.current!.getBoundingClientRect()
    const r = el.getBoundingClientRect()
    return new DOMRect(r.left - p.left, r.top - p.top, r.width, r.height)
  }
  const onEnter = useCallback((id: string, el: HTMLElement) => {
    if (leaveTimer.current) window.clearTimeout(leaveTimer.current)
    setHover({ id, rect: rectOf(el) })
  }, [])
  const onLeave = useCallback(() => {
    leaveTimer.current = window.setTimeout(() => setHover(null), 120)
  }, [])
  const onClick = useCallback((id: string, el: HTMLElement) => {
    setPinned((p) => (p?.id === id ? null : { id, rect: rectOf(el) }))
  }, [])

  const compareFields = useMemo<FieldResult[]>(() => {
    const p = nodes.compare?.payload?.fields as FieldResult[] | undefined
    return result?.fields ?? p ?? []
  }, [nodes.compare, result])
  const matchOf = (k: FieldKey) => compareFields.find((f) => f.field === k)?.match

  const pop = pinned ?? hover
  const hoverId = hover?.id ?? pinned?.id ?? null
  const bypass = active && nodes.aggregator?.state === 'skipped' && nodes.report?.state === 'done'
  const runEngine = useMemo(() => runDefaultEngine(nodes), [nodes])
  /** badge only when the node's engine differs from the run's default (e.g. gemini -> rules fallback) */
  const oddEngine = (id: string) => { const e = nodes[id]?.engine; return e && runEngine && e !== runEngine ? e : null }
  const doneFields = FIELD_KEYS.filter((k) => nodes[`field:${k}`]?.state === 'done').length
  const cat = (nodes.classifier?.payload?.category as string | undefined) ?? null

  const circleSub = {
    inbox: emailLabel ?? `${totalEmails} emails`,
    classifier: nodes.classifier?.state === 'running' ? 'classifying...' : cat ? cat.replace('_', ' ').toLowerCase() : 'standby',
    aggregator: active && nodes.aggregator?.state !== 'skipped' ? `${doneFields}/7 fields` : nodes.aggregator?.state === 'skipped' ? 'skipped' : 'merge + compare',
    report: result ? (result.status ? result.status.replace('_', ' ').toLowerCase() : 'classified') : 'report',
  }

  const nodeState = (id: string) => (active ? nodes[id]?.state ?? 'pending' : 'idle')

  return (
    <div className="graph-panel" ref={panelRef} onClick={(e) => { if ((e.target as HTMLElement).closest('.node, .popover')) return; setPinned(null) }}>
      <div className={`graph-viewport${W * scale > box.w + 1 ? ' scroll' : ''}`} ref={wrapRef}>
        <div
          className={`stage${reduced ? ' reduced' : ''}`}
          style={{ width: W, height: H, transform: `scale(${scale})`, left: Math.max(0, (box.w - W * scale) / 2), top: Math.max(0, (box.h - H * scale) / 2) }}
        >
          <svg className={`edges${hoverId ? ' has-hl' : ''}`} width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
            <defs>
              <filter id="blur4" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="4.5" /></filter>
            </defs>
            {EDGES.map((e) => {
              const m = edgeMode(nodes[e.from], nodes[e.to], active)
              const hl = !!hoverId && (e.from === hoverId || e.to === hoverId)
              return (
                <g key={e.id} className={`edge ${m}${hl ? ' hl' : ''}`} style={{ '--c': e.color } as CSSProperties}>
                  <path d={e.d} className="e-glow" filter="url(#blur4)" />
                  <path d={e.d} className="e-line" />
                </g>
              )
            })}
            {bypass && (
              <g className="edge flow" style={{ '--c': '#6ea8ff' } as CSSProperties}>
                <path d={BYPASS_EDGE.d} className="e-glow" filter="url(#blur4)" />
                <path d={BYPASS_EDGE.d} className="e-line dashed" />
              </g>
            )}
          </svg>
          <BeadCanvas nodes={nodes} active={active} bypass={bypass} reduced={reduced} scale={scale} />

          <CircleNode id="inbox" label="Inbox" sub={circleSub.inbox} pos={POS.inbox} color="#3b82f6" Icon={NODE_ICON.inbox}
            info={nodes.inbox} state={nodeState('inbox')} onEnter={onEnter} onLeave={onLeave} onClick={onClick} />
          <CircleNode id="classifier" label="Classifier" sub={circleSub.classifier} pos={POS.classifier} color="#6272ff" Icon={NODE_ICON.classifier}
            info={nodes.classifier} state={nodeState('classifier')} odd={oddEngine('classifier')} defaultEngine={runEngine} onEnter={onEnter} onLeave={onLeave} onClick={onClick} />

          {FIELD_KEYS.map((k, i) => {
            const id = `field:${k}`
            const info = nodes[id]
            const st = nodeState(id)
            const Icon = FIELD_ICON[k]
            const m = matchOf(k)
            let sub = 'SI vs BL'
            if (st === 'running') sub = 'reading...'
            else if (st === 'pending') sub = 'waiting'
            else if (st === 'skipped') sub = 'skipped'
            else if (st === 'error') sub = 'error - retry'
            else if (st === 'done') sub = m === undefined ? `${info?.engine ?? ''} ${fmtMs(info?.duration_ms)}`.trim() : m ? 'match' : 'MISMATCH'
            return (
              <FieldPill key={k} id={id} k={k} i={i} st={st} sub={sub} Icon={Icon} mismatch={m === false && st === 'done'}
                odd={oddEngine(id)} defaultEngine={runEngine} onEnter={onEnter} onLeave={onLeave} onClick={onClick} />
            )
          })}

          <CircleNode id="aggregator" label="Aggregator" sub={circleSub.aggregator} pos={POS.aggregator} color="#8a7bff" Icon={NODE_ICON.aggregator}
            info={nodes.aggregator} state={nodeState('aggregator')} intrinsic="pure" onEnter={onEnter} onLeave={onLeave} onClick={onClick} />

          <GateChip state={nodeState('gate')} escalate={!!result?.gate?.escalate} onEnter={onEnter} onLeave={onLeave} onClick={onClick} />

          <CircleNode id="report" label="Report" sub={circleSub.report} pos={POS.report} color="#4aa3ff" Icon={NODE_ICON.report}
            info={nodes.report} state={nodeState('report')} onEnter={onEnter} onLeave={onLeave} onClick={(id, el) => { onClick(id, el); }} />
        </div>
      </div>

      <div className="bead-key" aria-hidden="true"><i /><i /><i />bead colour = field agent &middot; bead speed = its real runtime</div>

      {pop && (
        <NodePopover
          key={pop.id}
          nodeId={pop.id}
          anchor={pop.rect}
          panelW={panelRef.current?.clientWidth ?? 800}
          panelH={panelRef.current?.clientHeight ?? 600}
          pinned={pinned?.id === pop.id}
          nodes={nodes}
          result={result}
          mode={mode}
          running={running}
          onClose={() => { setPinned(null); setHover(null) }}
          onRetry={onRetry}
          onOpenReport={onOpenReport}
          onEnter={() => { if (leaveTimer.current) window.clearTimeout(leaveTimer.current) }}
          onLeave={onLeave}
        />
      )}
    </div>
  )
}

type NodeHandlers = {
  onEnter: (id: string, el: HTMLElement) => void
  onLeave: () => void
  onClick: (id: string, el: HTMLElement) => void
}

const hookProps = (id: string, h: NodeHandlers) => ({
  onMouseEnter: (e: React.MouseEvent<HTMLElement>) => h.onEnter(id, e.currentTarget),
  onMouseLeave: h.onLeave,
  onFocus: (e: React.FocusEvent<HTMLElement>) => h.onEnter(id, e.currentTarget),
  onBlur: h.onLeave,
  onClick: (e: React.MouseEvent<HTMLElement>) => h.onClick(id, e.currentTarget),
})

/** Compact, honest engine tag: shown only for a node whose engine differs from the run's default (fallback) */
const OddTag = ({ engine, defaultEngine }: { engine: string; defaultEngine: string | null }) => (
  <span className={`eng eng-${engine}`} title={`This node ran on "${engine}" while the rest of the run used "${defaultEngine}" (fallback)`}>{engine}</span>
)

interface PillProps extends NodeHandlers {
  id: string; k: FieldKey; i: number; st: string; sub: string
  Icon: (typeof FIELD_ICON)[FieldKey]
  mismatch: boolean
  odd: string | null
  defaultEngine: string | null
}
function FieldPill({ id, k, i, st, sub, Icon, mismatch, odd, defaultEngine, ...h }: PillProps) {
  const done = useCompletion(st)
  return (
    <button
      type="button"
      className={`node pill${mismatch ? ' mismatch' : ''}`}
      data-state={st}
      data-node={id}
      aria-label={`${FIELD_LABEL[k]} field agent, ${st}${mismatch ? ', mismatch' : ''}`}
      style={{ left: PILL_X, top: pillY(i), width: PILL_W, height: PILL_H, '--c': FIELD_COLOR[k] } as CSSProperties}
      {...hookProps(id, h)}
    >
      <Ripples k={done} />
      <span className="pill-ico"><Icon size={20} strokeWidth={1.8} /></span>
      <span className="pill-txt"><b>{FIELD_LABEL[k]}</b><i>{sub}</i></span>
      {odd && st !== 'idle' && st !== 'pending' && <OddTag engine={odd} defaultEngine={defaultEngine} />}
    </button>
  )
}

function GateChip({ state, escalate, ...h }: NodeHandlers & { state: string; escalate: boolean }) {
  const done = useCompletion(state)
  return (
    <button
      type="button"
      className={`node gate-chip${escalate ? ' escalate' : ''}`}
      data-state={state}
      data-node="gate"
      aria-label="Fly-brain confidence gate"
      style={{ left: POS.gate.x, top: POS.gate.y, width: POS.gate.r * 2, height: POS.gate.r * 2 }}
      {...hookProps('gate', h)}
    >
      <Ripples k={done} />
      <NODE_ICON.gate size={17} strokeWidth={1.9} />
      <span className="gate-lbl">fly gate</span>
    </button>
  )
}

interface CNProps extends NodeHandlers {
  id: string; label: string; sub: string; color: string
  pos: { x: number; y: number; r: number }
  Icon: typeof NODE_ICON.inbox
  info?: NodeInfo
  state: string
  odd?: string | null
  defaultEngine?: string | null
  /** intrinsic non-LLM node (e.g. the pure compare function): always carries a compact tag */
  intrinsic?: string
}
function CircleNode({ id, label, sub, color, pos, Icon, state, odd, defaultEngine = null, intrinsic, ...h }: CNProps) {
  const done = useCompletion(state)
  const showIntrinsic = intrinsic && (state === 'done' || state === 'running' || state === 'error')
  return (
    <button
      type="button"
      className="node cnode"
      data-state={state}
      data-node={id}
      aria-label={`${label} node, ${state}`}
      style={{ left: pos.x, top: pos.y, width: pos.r * 2, height: pos.r * 2, '--c': color } as CSSProperties}
      {...hookProps(id, h)}
    >
      <Ripples k={done} />
      <Icon size={pos.r > 48 ? 26 : 22} strokeWidth={1.7} />
      <b>{label}</b>
      <i>{sub}</i>
      {odd && (state === 'done' || state === 'running' || state === 'error') && <OddTag engine={odd} defaultEngine={defaultEngine} />}
      {showIntrinsic && !odd && <span className={`eng eng-${intrinsic} intrinsic`} title="Deterministic function, no LLM">{intrinsic}</span>}
    </button>
  )
}
