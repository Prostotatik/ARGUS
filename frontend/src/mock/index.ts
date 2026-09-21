// Last-resort fallback data (used only when neither /api nor /replay/* is reachable).
// Hand-written, NOT produced by the backend. UI marks it as MOCK.
import type { EmailRow, FlyBrain, GateInfo, Result, Stats, TraceEvent, FieldResult, FieldKey } from '../types'
import { FIELD_KEYS } from '../types'

interface FieldSpec {
  si: string
  bl: string
  siEv: string
  blEv: string
  match?: boolean
  conf?: number
  error?: boolean
  note?: string
}

const BASE: Record<FieldKey, FieldSpec> = {
  shipper: { si: 'Kowloon Trading Co. Ltd', bl: 'Kowloon Trading Co. Ltd', siEv: 'Shipper: Kowloon Trading Co. Ltd', blEv: 'SHIPPER Kowloon Trading Co. Ltd' },
  consignee: { si: 'Rotterdam Fresh Imports B.V.', bl: 'Rotterdam Fresh Imports B.V.', siEv: 'Consignee: Rotterdam Fresh Imports B.V.', blEv: 'CONSIGNEE Rotterdam Fresh Imports B.V.' },
  notify_party: { si: 'Van Der Berg Logistics', bl: 'Van Der Berg Logistics', siEv: 'Notify Party: Van Der Berg Logistics', blEv: 'NOTIFY Van Der Berg Logistics' },
  port_of_loading: { si: 'Hong Kong', bl: 'Hong Kong', siEv: 'Port of Loading: Hong Kong', blEv: 'Load Port: Hong Kong' },
  port_of_discharge: { si: 'Rotterdam', bl: 'Rotterdam', siEv: 'Port of Discharge: Rotterdam', blEv: 'Discharge Port: ROTTERDAM' },
  container_count: { si: '3', bl: '3', siEv: 'Total Containers: 3', blEv: 'No. of Containers 3' },
  gross_weight_kg: { si: '22000', bl: '22000', siEv: 'Gross Weight (kg): 22,000', blEv: 'G.W. 22000.00 KGS' },
}

function fieldsFor(over: Partial<Record<FieldKey, Partial<FieldSpec>>>): FieldResult[] {
  return FIELD_KEYS.map((k) => {
    const s = { ...BASE[k], ...over[k] }
    const match = s.si === s.bl && !s.error
    return {
      field: k,
      si_value: s.si === '' ? null : s.si,
      bl_value: s.bl === '' ? null : s.bl,
      si_norm: s.si,
      bl_norm: s.bl,
      match: s.match ?? match,
      confidence: s.conf ?? (match ? 0.97 : 0.93),
      si_evidence: s.siEv,
      bl_evidence: s.blEv,
      note: s.note ?? null,
    }
  })
}

let seq = 0
function ev(t: number, node: string, state: TraceEvent['state'], engine: string | null, dur: number | null, summary: string, payload: Record<string, unknown> = {}): TraceEvent {
  return { seq: seq++, t_ms: t, node, state, engine, duration_ms: dur, summary, payload }
}

interface CmpOpts {
  id: string
  from: string
  subject: string
  at: string
  fields: FieldResult[]
  status: Result['status']
  reason?: Result['review_reason']
  headline: string
  gate: GateInfo
  errorField?: FieldKey
  escalation?: Result['escalation']
  engine?: string
}

function comparison(o: CmpOpts): Result {
  seq = 0
  const engine = o.engine ?? 'rules'
  const events: TraceEvent[] = []
  events.push(ev(0, 'inbox', 'done', 'pure', 1, 'Email received'))
  events.push(ev(6, 'classifier', 'start', engine, null, 'Classifying'))
  events.push(ev(52, 'classifier', 'done', engine, 46, 'BL_COMPARISON (0.98)', { category: 'BL_COMPARISON', confidence: 0.98, reasons: ['Subject asks to check draft BL against SI', 'Two attachments: SI and BL'] }))
  o.fields.forEach((f, i) => events.push(ev(56 + i, `field:${f.field}`, 'start', engine, null, `Reading ${f.field}`)))
  o.fields.forEach((f, i) => {
    const node = `field:${f.field}`
    const t = 90 + i * 17
    if (o.errorField === f.field) {
      events.push(ev(t, node, 'error', engine, 31, 'Timeout reading BL attachment', { field: f.field, error: 'timeout' }))
    } else {
      events.push(ev(t, node, 'done', engine, 30 + i * 3, `${f.si_value ?? '-'} | ${f.bl_value ?? '-'}`, { field: f.field, si_value: f.si_value, bl_value: f.bl_value, si_evidence: f.si_evidence, bl_evidence: f.bl_evidence, confidence: f.confidence }))
    }
  })
  events.push(ev(230, 'aggregator', 'start', 'pure', null, 'Aggregating'))
  events.push(ev(238, 'aggregator', 'done', 'pure', 8, 'Report card assembled'))
  events.push(ev(240, 'compare', 'done', 'pure', 1, `${o.fields.filter((f) => !f.match).length} mismatched field(s)`, { fields: o.fields }))
  events.push(ev(262, 'gate', 'done', 'flynet', 22, o.gate.escalate ? 'Escalate to human' : 'Confident', { ...o.gate }))
  const result: Result = {
    email_id: o.id,
    from: o.from,
    subject: o.subject,
    received_at: o.at,
    category: 'BL_COMPARISON',
    status: o.status,
    review_reason: o.reason ?? null,
    has_defect: o.fields.some((f) => !f.match),
    defect_fields: o.fields.filter((f) => !f.match).map((f) => String(f.field)),
    headline: o.headline,
    fields: o.fields,
    gate: o.gate,
    escalation: o.escalation ?? null,
    engine: { classifier: engine, fields: engine },
    errors: o.errorField ? [{ node: `field:${o.errorField}`, error: 'timeout' }] : [],
  }
  events.push(ev(270, 'report', 'done', 'pure', 3, o.headline, { ...result } as unknown as Record<string, unknown>))
  result.events = events
  return result
}

function simple(id: string, from: string, subject: string, at: string, category: string, reasons: string[], conf: number): Result {
  seq = 0
  const events = [
    ev(0, 'inbox', 'done', 'pure', 1, 'Email received'),
    ev(4, 'classifier', 'start', 'rules', null, 'Classifying'),
    ev(38, 'classifier', 'done', 'rules', 34, `${category} (${conf.toFixed(2)})`, { category, confidence: conf, reasons }),
  ]
  const result: Result = {
    email_id: id, from, subject, received_at: at, category, status: null, review_reason: null,
    has_defect: false, defect_fields: [], headline: `Classified as ${category}`, fields: [], gate: null,
    escalation: null, engine: { classifier: 'rules' }, errors: [],
  }
  events.push(ev(44, 'report', 'done', 'pure', 2, result.headline ?? '', { ...result } as unknown as Record<string, unknown>))
  result.events = events
  return result
}

const okVec = [0, 0, 0, 0, 0, 0, 0, 0.97, 0.97, 0.96, 0.97, 0.98, 0.97, 0.97]
const gateOk = (s: number): GateInfo => ({ suspicion: s, threshold: 0.5, escalate: false, reason: 'Familiar pattern: all fields agree with high extraction confidence', input_vector: okVec, kc_active: [3, 11, 19, 26, 40, 52], winner_kc: 26 })

export const MOCK_RESULTS: Result[] = [
  comparison({
    id: 'mock_001', from: 'Maersk Line', subject: 'Container count discrepancy - draft BL check', at: '2026-09-18T12:42:00Z',
    fields: fieldsFor({ container_count: { bl: '4', blEv: 'No. of Containers 4' } }), status: 'MISMATCH',
    headline: 'container_count: SI 3 / BL 4',
    gate: { suspicion: 0.31, threshold: 0.5, escalate: false, reason: 'Single clean numeric mismatch, high confidence', input_vector: [0, 0, 0, 0, 0, 1, 0, 0.97, 0.97, 0.96, 0.97, 0.98, 0.93, 0.97], kc_active: [5, 9, 21, 33, 34, 47], winner_kc: 33 },
  }),
  comparison({
    id: 'mock_002', from: 'CMA CGM', subject: 'Please verify BL draft vs SI', at: '2026-09-18T12:37:00Z',
    fields: fieldsFor({}), status: 'OK', headline: 'No mismatch detected', gate: gateOk(0.12),
  }),
  comparison({
    id: 'mock_003', from: 'DHL Global Forwarding', subject: 'Weight mismatch - BL 7845123', at: '2026-09-18T12:21:00Z',
    fields: fieldsFor({ consignee: { bl: 'Rotterdam Fresh Imports BV', blEv: 'CONSIGNEE Rotterdam Fresh Imports BV', match: false, note: 'Legal-form suffix differs' }, gross_weight_kg: { bl: '24500', blEv: 'G.W. 24500.00 KGS' } }),
    status: 'MISMATCH', headline: 'consignee: SI Rotterdam Fresh Imports B.V. / BL Rotterdam Fresh Imports BV; gross_weight_kg: SI 22000 / BL 24500',
    gate: { suspicion: 0.47, threshold: 0.5, escalate: false, reason: 'Two mismatches; one is a formatting-class difference', input_vector: [0, 1, 0, 0, 0, 0, 1, 0.97, 0.9, 0.96, 0.97, 0.98, 0.97, 0.95], kc_active: [2, 8, 14, 22, 31, 43, 55], winner_kc: 22 },
  }),
  comparison({
    id: 'mock_004', from: 'Customs Malaysia', subject: 'Check BL draft - scan attached', at: '2026-09-18T11:58:00Z',
    fields: fieldsFor({ gross_weight_kg: { bl: '', blEv: '(no text layer on page 2)', error: true, match: false, conf: 0.2 } }),
    status: 'NEEDS_REVIEW', reason: 'unreadable', errorField: 'gross_weight_kg',
    headline: 'Needs review: unreadable',
    gate: { suspicion: 0.83, threshold: 0.5, escalate: true, reason: 'Unreadable BL page and low extraction confidence on gross weight', input_vector: [0, 0, 0, 0, 0, 0, 1, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.2], kc_active: [1, 6, 15, 28, 37, 44, 51, 58], winner_kc: 44 },
    escalation: { open: true, reason: 'Gross weight on BL could not be read (scanned page, no text layer).', evidence: [{ doc: 'SI', field: 'gross_weight_kg', text: 'Gross Weight (kg): 22,000' }, { doc: 'BL', field: 'gross_weight_kg', text: '(no text layer on page 2)' }], resolved: false },
  }),
  comparison({
    id: 'mock_005', from: 'MSC', subject: 'Shipment verification - SGS report', at: '2026-09-18T11:42:00Z',
    fields: fieldsFor({ shipper: { bl: '', blEv: '(BL attachment missing)', error: true, match: false, conf: 0.1 } }),
    status: 'NEEDS_REVIEW', reason: 'missing_attachment', headline: 'Needs review: missing_attachment',
    gate: { suspicion: 0.91, threshold: 0.5, escalate: true, reason: 'No BL attached; nothing to compare against', input_vector: [1, 1, 1, 1, 1, 1, 1, 0.9, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1], kc_active: [0, 4, 10, 17, 25, 36, 48, 53, 59], winner_kc: 25 },
    escalation: { open: true, reason: 'Comparison requested but only one attachment (SI) was found.', evidence: [{ doc: 'EMAIL', text: 'Please check the attached SI against the BL draft.' }], resolved: false },
  }),
  simple('mock_006', 'Evergreen Line', 'New SI request - 2x40HC to Singapore', '2026-09-18T11:17:00Z', 'SI_REQUEST', ['Asks to prepare a new shipping instruction'], 0.95),
  simple('mock_007', 'ONE', 'Invoice 9987 query', '2026-09-18T10:26:00Z', 'INVOICE_QUERY', ['Invoice number and amount referenced'], 0.94),
  simple('mock_008', 'Hapag-Lloyd', 'Port delay update - Tanjung Pelepas', '2026-09-18T10:53:00Z', 'GENERAL', ['Operational update, no action requested'], 0.9),
  simple('mock_009', 'Prize Desk', 'You have won a free cruise!!!', '2026-09-18T09:12:00Z', 'SPAM', ['Promotional language', 'Unknown sender'], 0.99),
  comparison({
    id: 'mock_010', from: 'Yang Ming', subject: 'Draft BL for review', at: '2026-09-18T09:02:00Z',
    fields: fieldsFor({ port_of_loading: { bl: 'HONG KONG', blEv: 'Port of Loading: HONG KONG' } }).map((f) => f.field === 'port_of_loading' ? { ...f, match: true, note: 'Case-only difference, normalised' } : f),
    status: 'OK', headline: 'No mismatch detected', gate: gateOk(0.18),
  }),
]

export const MOCK_ROWS: EmailRow[] = MOCK_RESULTS.map((r) => ({
  email_id: r.email_id, from: r.from ?? '', subject: r.subject ?? '', received_at: r.received_at ?? '', has_attachments: true,
  result: { ...r, events: undefined },
}))

export const MOCK_STATS: Stats = {
  emails_total: MOCK_RESULTS.length, processed: MOCK_RESULTS.length,
  classified: { BL_COMPARISON: 6, SI_REQUEST: 1, INVOICE_QUERY: 1, GENERAL: 1, SPAM: 1 },
  comparisons: 6, mismatches: 2, needs_review: 2, discrepancies_found: 4, accuracy_vs_labels: null,
  top_issues: [{ label: 'gross_weight_kg', count: 2 }, { label: 'container_count', count: 1 }, { label: 'consignee', count: 1 }],
}

/** seeded schematic projection so the fly panel still renders without backend/replay flybrain.json */
export function schematicFly(nInputs = 14, nKc = 60, per = 4): FlyBrain {
  let s = 1337
  const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296)
  const projection = Array.from({ length: nKc }, () => {
    const set = new Set<number>()
    while (set.size < per) set.add(Math.floor(rnd() * nInputs))
    return [...set]
  })
  return { n_inputs: nInputs, n_kc: nKc, kc_sparsity: 0.1, threshold: 0.5, projection, weights: Array.from({ length: nKc }, () => 0.2 + rnd() * 0.2), history: [], schematic: true }
}
