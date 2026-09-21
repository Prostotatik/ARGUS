import { memo, useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import type { FieldResult, Mode, Result } from '../types'
import { FIELD_KEYS, type FieldKey } from '../types'
import {
  FIELD_COLOR, FIELD_LABEL, fieldOfNode, fmtMs, type NodeInfo, type NodeMap,
} from '../data/graphState'
import { FIELD_ICON, NODE_ICON } from './icons'
import NodePopover from './NodePopover'

export const W = 940
export const H = 600
const CY = 300
const PILL_W = 214
const PILL_H = 58
const PILL_X = 470
const PILL_GAP = 74

const POS = {
  inbox: { x: 74, y: CY, r: 46 },
  classifier: { x: 236, y: CY, r: 52 },
  aggregator: { x: 705, y: CY, r: 52 },
  gate: { x: 797, y: CY, r: 18 },
  report: { x: 873, y: CY, r: 44 },
}
const pillY = (i: number) => CY + (i - 3) * PILL_GAP
const theta = (i: number) => ((i - 3) / 3) * 0.78

interface Edge { id: string; d: string; color: string; from: string; to: string; dur: number }

function buildEdges(): Edge[] {
  const e: Edge[] = []
  e.push({ id: 'inbox>classifier', d: `M ${POS.inbox.x + POS.inbox.r} ${CY} L ${POS.classifier.x - POS.classifier.r} ${CY}`, color: '#4d8dff', from: 'inbox', to: 'classifier', dur: 1.6 })
  FIELD_KEYS.forEach((k, i) => {
    const th = theta(i)
    const sx = POS.classifier.x + POS.classifier.r * Math.cos(th)
    const sy = CY + POS.classifier.r * Math.sin(th)
    const ex = PILL_X - PILL_W / 2
    const ey = pillY(i)
    const c1x = sx + Math.cos(th) * 74
    const c1y = sy + Math.sin(th) * 74
    e.push({ id: `classifier>${k}`, d: `M ${sx.toFixed(1)} ${sy.toFixed(1)} C ${c1x.toFixed(1)} ${c1y.toFixed(1)}, ${ex - 64} ${ey}, ${ex} ${ey}`, color: FIELD_COLOR[k], from: 'classifier', to: `field:${k}`, dur: 2.4 + (i % 3) * 0.25 })
    const px = PILL_X + PILL_W / 2
    const ax = POS.aggregator.x - POS.aggregator.r * Math.cos(th)
    const ay = CY + POS.aggregator.r * Math.sin(th)
    const c2x = ax - Math.cos(th) * 74
    const c2y = ay + Math.sin(th) * 74
    e.push({ id: `${k}>aggregator`, d: `M ${px} ${ey} C ${px + 64} ${ey}, ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${ax.toFixed(1)} ${ay.toFixed(1)}`, color: FIELD_COLOR[k], from: `field:${k}`, to: 'aggregator', dur: 2.4 + (i % 3) * 0.25 })
  })
  e.push({ id: 'aggregator>gate', d: `M ${POS.aggregator.x + POS.aggregator.r} ${CY} L ${POS.gate.x - POS.gate.r} ${CY}`, color: '#6ea8ff', from: 'aggregator', to: 'gate', dur: 1.2 })
  e.push({ id: 'gate>report', d: `M ${POS.gate.x + POS.gate.r} ${CY} L ${POS.report.x - POS.report.r} ${CY}`, color: '#6ea8ff', from: 'gate', to: 'report', dur: 1.2 })
  return e
}
const EDGES = buildEdges()
// classifier -> report bypass (non-comparison emails stop after classifier)
const BYPASS = `M ${POS.classifier.x + 18} ${CY - POS.classifier.r + 2} C ${POS.classifier.x + 120} 14, ${POS.report.x - 150} 14, ${POS.report.x - 10} ${CY - POS.report.r + 2}`

type EdgeMode = 'ambient' | 'flow' | 'done' | 'dim' | 'error'
function edgeMode(from: NodeInfo | undefined, to: NodeInfo | undefined, active: boolean): EdgeMode {
  if (!active) return 'ambient'
  if (!from || !to) return 'dim'
  if (to.state === 'skipped' || from.state === 'skipped') return 'dim'
  if (from.state === 'error') return 'error'
  if (from.state === 'done' && to.state === 'done') return 'done'
  if (from.state === 'done') return 'flow'
  return 'dim'
}

const Particles = memo(function Particles({ d, color, n, dur }: { d: string; color: string; n: number; dur: number }) {
  return (
    <>
      {Array.from({ length: n }, (_, k) => (
        <g key={k} className="particle">
          <circle r="5.5" fill={color} opacity="0.28" />
          <circle r="2" fill="#fff" />
          <animateMotion dur={`${dur}s`} begin={`-${((k * dur) / n).toFixed(2)}s`} repeatCount="indefinite" path={d} />
        </g>
      ))}
    </>
  )
})

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
          <svg className="edges" width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
            <defs>
              <filter id="blur4" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="4.5" /></filter>
            </defs>
            {EDGES.map((e) => {
              const m = edgeMode(nodes[e.from], nodes[e.to], active)
              const n = m === 'flow' ? 3 : m === 'done' ? 2 : m === 'ambient' ? 1 : 0
              const dur = m === 'flow' ? e.dur * 0.7 : e.dur * 1.6
              return (
                <g key={e.id} className={`edge ${m}`} style={{ '--c': e.color } as CSSProperties}>
                  <path d={e.d} className="e-glow" filter="url(#blur4)" />
                  <path d={e.d} className="e-line" />
                  {!reduced && n > 0 && <Particles key={`${m}`} d={e.d} color={e.color} n={n} dur={dur} />}
                </g>
              )
            })}
            {active && nodes.aggregator?.state === 'skipped' && nodes.report?.state === 'done' && (
              <g className="edge flow" style={{ '--c': '#6ea8ff' } as CSSProperties}>
                <path d={BYPASS} className="e-glow" filter="url(#blur4)" />
                <path d={BYPASS} className="e-line dashed" />
                {!reduced && <Particles d={BYPASS} color="#6ea8ff" n={3} dur={2.4} />}
              </g>
            )}
          </svg>

          <CircleNode id="inbox" label="Inbox" sub={circleSub.inbox} pos={POS.inbox} color="#3b82f6" Icon={NODE_ICON.inbox}
            info={nodes.inbox} state={nodeState('inbox')} onEnter={onEnter} onLeave={onLeave} onClick={onClick} />
          <CircleNode id="classifier" label="Classifier" sub={circleSub.classifier} pos={POS.classifier} color="#6272ff" Icon={NODE_ICON.classifier}
            info={nodes.classifier} state={nodeState('classifier')} onEnter={onEnter} onLeave={onLeave} onClick={onClick} />

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
              <button
                key={k}
                type="button"
                className={`node pill${m === false && st === 'done' ? ' mismatch' : ''}`}
                data-state={st}
                data-node={id}
                aria-label={`${FIELD_LABEL[k]} field agent, ${st}${m === false ? ', mismatch' : ''}`}
                style={{ left: PILL_X, top: pillY(i), width: PILL_W, height: PILL_H, '--c': FIELD_COLOR[k] } as CSSProperties}
                onMouseEnter={(e) => onEnter(id, e.currentTarget)}
                onMouseLeave={onLeave}
                onFocus={(e) => onEnter(id, e.currentTarget)}
                onBlur={onLeave}
                onClick={(e) => onClick(id, e.currentTarget)}
              >
                <span className="pill-ico"><Icon size={20} strokeWidth={1.8} /></span>
                <span className="pill-txt"><b>{FIELD_LABEL[k]}</b><i>{sub}</i></span>
                {info?.engine && st !== 'idle' && st !== 'pending' && <span className={`eng eng-${info.engine}`}>{info.engine}</span>}
              </button>
            )
          })}

          <CircleNode id="aggregator" label="Aggregator" sub={circleSub.aggregator} pos={POS.aggregator} color="#8a7bff" Icon={NODE_ICON.aggregator}
            info={nodes.aggregator} state={nodeState('aggregator')} onEnter={onEnter} onLeave={onLeave} onClick={onClick} />

          <button
            type="button"
            className={`node gate-chip${result?.gate?.escalate ? ' escalate' : ''}`}
            data-state={nodeState('gate')}
            data-node="gate"
            aria-label="Fly-brain confidence gate"
            style={{ left: POS.gate.x, top: POS.gate.y, width: POS.gate.r * 2, height: POS.gate.r * 2 }}
            onMouseEnter={(e) => onEnter('gate', e.currentTarget)}
            onMouseLeave={onLeave}
            onFocus={(e) => onEnter('gate', e.currentTarget)}
            onBlur={onLeave}
            onClick={(e) => onClick('gate', e.currentTarget)}
          >
            <NODE_ICON.gate size={17} strokeWidth={1.9} />
            <span className="gate-lbl">fly gate</span>
          </button>

          <CircleNode id="report" label="Report" sub={circleSub.report} pos={POS.report} color="#4aa3ff" Icon={NODE_ICON.report}
            info={nodes.report} state={nodeState('report')} onEnter={onEnter} onLeave={onLeave} onClick={(id, el) => { onClick(id, el); }} />
        </div>
      </div>

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

interface CNProps {
  id: string; label: string; sub: string; color: string
  pos: { x: number; y: number; r: number }
  Icon: typeof NODE_ICON.inbox
  info?: NodeInfo
  state: string
  onEnter: (id: string, el: HTMLElement) => void
  onLeave: () => void
  onClick: (id: string, el: HTMLElement) => void
}
function CircleNode({ id, label, sub, color, pos, Icon, info, state, onEnter, onLeave, onClick }: CNProps) {
  return (
    <button
      type="button"
      className="node cnode"
      data-state={state}
      data-node={id}
      aria-label={`${label} node, ${state}`}
      style={{ left: pos.x, top: pos.y, width: pos.r * 2, height: pos.r * 2, '--c': color } as CSSProperties}
      onMouseEnter={(e) => onEnter(id, e.currentTarget)}
      onMouseLeave={onLeave}
      onFocus={(e) => onEnter(id, e.currentTarget)}
      onBlur={onLeave}
      onClick={(e) => onClick(id, e.currentTarget)}
    >
      <Icon size={pos.r > 48 ? 26 : 22} strokeWidth={1.7} />
      <b>{label}</b>
      <i>{sub}</i>
      {info?.engine && (state === 'done' || state === 'running' || state === 'error') && <span className={`eng eng-${info.engine}`}>{info.engine}</span>}
    </button>
  )
}
