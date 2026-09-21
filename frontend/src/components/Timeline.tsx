import type { CSSProperties } from 'react'
import { Brain, FileText, Mail, Network, ShieldCheck } from 'lucide-react'
import type { FieldResult, Result } from '../types'
import { FIELD_KEYS } from '../types'
import { FIELD_COLOR, FIELD_LABEL, fmtMs, pct, type NodeInfo, type NodeMap, type NodeState } from '../data/graphState'
import { FIELD_ICON } from './icons'

interface Props {
  nodes: NodeMap
  active: boolean
  playing: boolean
  result: Result | null
  title: string | null
  totalMs: number | null
}

const st = (n: NodeInfo | undefined, active: boolean): NodeState => (active ? n?.state ?? 'pending' : 'idle')
const tPlus = (n: NodeInfo | undefined) => (n?.t_ms != null && n.state !== 'pending' ? `t+${n.t_ms}ms` : '')

export default function Timeline({ nodes, active, playing, result, title, totalMs }: Props) {
  const fields = FIELD_KEYS.map((k) => ({ k, n: nodes[`field:${k}`] }))
  const fDone = fields.filter((f) => f.n?.state === 'done').length
  const fErr = fields.filter((f) => f.n?.state === 'error').length
  const fSkipped = active && fields.every((f) => f.n?.state === 'skipped')
  const fState: NodeState = !active ? 'idle' : fSkipped ? 'skipped' : fErr ? 'error' : fDone === 7 ? 'done' : fields.some((f) => f.n?.state === 'running') || fDone > 0 ? 'running' : 'pending'
  const lastField = Math.max(0, ...fields.map((f) => f.n?.t_ms ?? 0))
  const cmp = (nodes.compare?.payload?.fields as FieldResult[] | undefined) ?? result?.fields
  const bad = cmp?.filter((f) => !f.match).length ?? 0
  const cat = nodes.classifier?.payload?.category as string | undefined
  const conf = nodes.classifier?.payload?.confidence as number | undefined
  const gate = nodes.gate?.payload as { suspicion?: number; escalate?: boolean } | null | undefined

  const steps = [
    { id: 'received', label: 'Received', Icon: Mail, state: st(nodes.inbox, active), t: tPlus(nodes.inbox), sub: result?.email_id ?? (active ? '' : 'idle'), eng: null as string | null },
    { id: 'classified', label: 'Classified', Icon: Brain, state: st(nodes.classifier, active), t: tPlus(nodes.classifier), sub: cat ? `${cat.replace('_', ' ').toLowerCase()}${conf != null ? ` ${pct(conf)}` : ''}` : '', eng: nodes.classifier?.engine ?? null, dur: nodes.classifier?.duration_ms },
    { id: 'fields', label: 'Field agents', Icon: FIELD_ICON.shipper, state: fState, t: fDone || fErr ? `t+${lastField}ms` : '', sub: fSkipped ? 'skipped' : active ? `${fDone}/7 done${fErr ? `, ${fErr} error` : ''}` : '', eng: nodes['field:shipper']?.engine ?? null, fields: true },
    { id: 'aggregated', label: 'Aggregate + compare', Icon: Network, state: st(nodes.aggregator, active), t: tPlus(nodes.compare?.state === 'done' ? nodes.compare : nodes.aggregator), sub: nodes.aggregator?.state === 'skipped' ? 'skipped' : cmp ? (bad ? `${bad} mismatch${bad > 1 ? 'es' : ''}` : 'all 7 match') : '', eng: nodes.aggregator?.engine ?? null, dur: nodes.aggregator?.duration_ms },
    { id: 'gate', label: 'Fly gate', Icon: ShieldCheck, state: st(nodes.gate, active), t: tPlus(nodes.gate), sub: nodes.gate?.state === 'skipped' ? 'skipped' : gate?.suspicion != null ? `${gate.suspicion.toFixed(2)} ${gate.escalate ? 'escalate' : 'confident'}` : '', eng: nodes.gate?.engine ?? null, dur: nodes.gate?.duration_ms },
    { id: 'report', label: 'Report ready', Icon: FileText, state: st(nodes.report, active), t: tPlus(nodes.report), sub: result ? result.status ?? 'classified only' : '', eng: nodes.report?.engine ?? null },
  ]

  return (
    <section className="timeline panel" aria-label="Processing timeline">
      <header className="panel-h">
        <h2>Processing Timeline</h2>
        {title && <span className="tl-title" title={title}>{title}</span>}
        {totalMs != null && <span className="tl-total">{fmtMs(totalMs)} total</span>}
      </header>
      <ol className="tl-steps">
        {steps.map((s, i) => (
          <li key={s.id} className={`tl-step s-${s.state}`} style={{ '--i': i } as CSSProperties}>
            <span className="tl-ico">
              <s.Icon size={18} strokeWidth={1.7} />
            </span>
            <span className="tl-lbl">{s.label}</span>
            {'fields' in s && s.fields ? (
              <span className="tl-fdots" aria-hidden="true">
                {fields.map(({ k, n }) => (
                  <i key={k} data-state={active ? n?.state ?? 'pending' : 'idle'} style={{ '--c': FIELD_COLOR[k] } as CSSProperties} title={`${FIELD_LABEL[k]}: ${n?.state ?? 'pending'}`} />
                ))}
              </span>
            ) : null}
            <span className="tl-t">{s.t || ' '}</span>
            <span className="tl-sub">{s.sub || ' '}</span>
            {s.eng && s.state !== 'idle' && s.state !== 'pending' ? <span className={`eng eng-${s.eng}`}>{s.eng}{'dur' in s && s.dur != null ? ` ${fmtMs(s.dur)}` : ''}</span> : null}
            {i < steps.length - 1 && <span className={`tl-link${playing && (s.state === 'running' || s.state === 'done') ? ' flow' : ''}`} aria-hidden="true" />}
          </li>
        ))}
      </ol>
    </section>
  )
}
