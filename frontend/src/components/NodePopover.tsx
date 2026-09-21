import { useLayoutEffect, useRef, useState } from 'react'
import type { FieldResult, GateInfo, Mode, Result } from '../types'
import { FIELD_COLOR, FIELD_LABEL, fieldOfNode, fmtMs, isFieldNode, pct, type NodeMap } from '../data/graphState'

interface Props {
  nodeId: string
  anchor: DOMRect
  panelW: number
  panelH: number
  pinned: boolean
  nodes: NodeMap
  result: Result | null
  mode: Mode
  running: boolean
  onClose: () => void
  onRetry: () => void
  onOpenReport: () => void
  onEnter: () => void
  onLeave: () => void
}

const TITLES: Record<string, string> = {
  inbox: 'Inbox', classifier: 'Classifier agent', aggregator: 'Aggregator + compare', gate: 'Fly-brain confidence gate', report: 'Report',
}

const str = (v: unknown) => (v == null || v === '' ? '-' : String(v))

export default function NodePopover({ nodeId, anchor, panelW, panelH, pinned, nodes, result, mode, running, onClose, onRetry, onOpenReport, onEnter, onLeave }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ left: 0, top: 0 })
  const info = nodes[nodeId]
  const p = (info?.payload ?? {}) as Record<string, unknown>

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const w = el.offsetWidth
    const h = el.offsetHeight
    let left = anchor.right + 14
    if (left + w > panelW - 8) left = anchor.left - w - 14
    if (left < 8) left = Math.max(8, Math.min(panelW - w - 8, anchor.left))
    const top = Math.max(8, Math.min(panelH - h - 8, anchor.top + anchor.height / 2 - h / 2))
    setPos({ left, top })
  }, [anchor, panelW, panelH, nodeId, info])

  const isField = isFieldNode(nodeId)
  const fk = isField ? fieldOfNode(nodeId) : null
  const title = fk ? `${FIELD_LABEL[fk]} agent` : TITLES[nodeId] ?? nodeId
  const color = fk ? FIELD_COLOR[fk] : '#6ea8ff'
  const state = info?.state ?? 'idle'
  const cmp: FieldResult | undefined = fk ? (result?.fields ?? (nodes.compare?.payload?.fields as FieldResult[] | undefined))?.find((f) => f.field === fk) : undefined

  let body: React.ReactNode
  if (state === 'idle' || state === 'pending') {
    body = <p className="pop-dim">{state === 'idle' ? 'No email is being processed. Select an email to watch this node work.' : 'Waiting for upstream nodes.'}</p>
  } else if (nodeId === 'inbox') {
    body = (
      <dl className="kv">
        <dt>From</dt><dd>{str(result?.from)}</dd>
        <dt>Subject</dt><dd>{str(result?.subject)}</dd>
        <dt>Received</dt><dd title="Arrival time is simulated - the dataset has no timestamps">{str(result?.received_at)} <em className="pop-dim">(simulated)</em></dd>
        <dt>Email</dt><dd className="mono">{str(result?.email_id)}</dd>
      </dl>
    )
  } else if (nodeId === 'classifier') {
    const reasons = (p.reasons as string[] | undefined) ?? []
    body = (
      <>
        <dl className="kv"><dt>Category</dt><dd><b>{str(p.category)}</b></dd><dt>Confidence</dt><dd>{typeof p.confidence === 'number' ? pct(p.confidence as number) : '-'}</dd></dl>
        {reasons.length > 0 && <ul className="reasons">{reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>}
      </>
    )
  } else if (fk) {
    const si = p.si_value ?? cmp?.si_value
    const bl = p.bl_value ?? cmp?.bl_value
    const siEv = (p.si_evidence ?? cmp?.si_evidence) as string | undefined
    const blEv = (p.bl_evidence ?? cmp?.bl_evidence) as string | undefined
    const conf = (p.confidence ?? cmp?.confidence) as number | undefined
    const bad = cmp ? !cmp.match : false
    body = state === 'error' ? (
      <p className="pop-err">{info?.summary ?? 'Node failed.'}</p>
    ) : (
      <>
        <div className={`sibl${bad ? ' bad' : ''}`}>
          <div><span>SI</span><b>{str(si)}</b><em>{siEv ?? ''}</em></div>
          <div><span>BL</span><b>{str(bl)}</b><em>{blEv ?? ''}</em></div>
        </div>
        <dl className="kv">
          {cmp && <><dt>Verdict</dt><dd className={cmp.match ? 'ok' : 'bad'}>{cmp.match ? 'match' : 'mismatch'}{cmp.note ? ` - ${cmp.note}` : ''}</dd></>}
          {conf != null && <><dt>Confidence</dt><dd>{pct(conf)}</dd></>}
        </dl>
      </>
    )
  } else if (nodeId === 'aggregator') {
    const fs = result?.fields ?? (nodes.compare?.payload?.fields as FieldResult[] | undefined) ?? []
    const bad = fs.filter((f) => !f.match)
    body = (
      <>
        <p className="pop-line">{info?.summary ?? ''}</p>
        <dl className="kv">
          <dt>Compare</dt><dd>{fs.length ? `${fs.length - bad.length}/${fs.length} fields match (pure function, no LLM)` : 'pending'}</dd>
          {bad.length > 0 && <><dt>Mismatch</dt><dd className="bad">{bad.map((f) => f.field).join(', ')}</dd></>}
        </dl>
      </>
    )
  } else if (nodeId === 'gate') {
    const g = (Object.keys(p).length ? p : result?.gate ?? {}) as unknown as GateInfo
    body = (
      <>
        <dl className="kv">
          <dt>Suspicion</dt><dd>{g.suspicion?.toFixed?.(3) ?? '-'} <span className="dim">/ threshold {g.threshold?.toFixed?.(2) ?? '-'}</span></dd>
          <dt>Decision</dt><dd className={g.escalate ? 'warn' : 'ok'}>{g.escalate ? 'Escalate to human' : 'Confident - no escalation'}</dd>
          <dt>Active KCs</dt><dd>{g.kc_active?.length ?? 0}{g.winner_kc != null ? ` (winner #${g.winner_kc})` : ''}</dd>
        </dl>
        {g.reason && <p className="pop-line">{g.reason}</p>}
        {(g.drivers?.length ?? 0) > 0 && (
          <dl className="kv">
            <dt>Drivers</dt>
            <dd>{g.drivers!.map((d) => `${d.input.replace(/[_:]/g, ' ')} ${Math.round(d.share * 100)}%`).join(' · ')}</dd>
          </dl>
        )}
        <p className="pop-dim">Network architecture inspired by the fruit fly's olfactory system.</p>
      </>
    )
  } else if (nodeId === 'report') {
    body = (
      <>
        <p className="pop-line"><b>{result?.headline ?? info?.summary ?? ''}</b></p>
        <button type="button" className="btn small" onClick={onOpenReport}>Open full report</button>
      </>
    )
  }

  return (
    <div
      ref={ref}
      className={`popover${pinned ? ' pinned' : ''}`}
      style={{ left: pos.left, top: pos.top, borderColor: color + '66' }}
      role="dialog"
      aria-label={`${title} details`}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
    >
      <header>
        <span className="dot" style={{ background: color }} />
        <b>{title}</b>
        <span className={`chip st-${state}`}>{state}</span>
        {pinned && <button type="button" className="x" aria-label="Close" onClick={onClose}>x</button>}
      </header>
      <div className="meta">
        {info?.engine && <span className={`eng eng-${info.engine}`}>{info.engine}</span>}
        {info?.duration_ms != null && <span>{fmtMs(info.duration_ms)}</span>}
        {info?.t_ms != null && state !== 'idle' && <span>t+{info.t_ms}ms</span>}
      </div>
      {body}
      {state === 'error' && (
        <button type="button" className="btn small warn" disabled={running} onClick={onRetry}>
          Retry{mode !== 'live' ? ' (simulated)' : ''}
        </button>
      )}
      {!pinned && <div className="pop-hint">click to pin</div>}
    </div>
  )
}
