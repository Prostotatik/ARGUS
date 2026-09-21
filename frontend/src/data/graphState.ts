import type { Result, TraceEvent } from '../types'
import { FIELD_KEYS, type FieldKey } from '../types'

export type NodeState = 'idle' | 'pending' | 'running' | 'done' | 'error' | 'skipped'

export interface NodeInfo {
  state: NodeState
  engine?: string | null
  duration_ms?: number | null
  summary?: string | null
  payload?: Record<string, unknown> | null
  t_ms?: number
  startT?: number
}

export type NodeMap = Record<string, NodeInfo>

export const FIELD_LABEL: Record<FieldKey, string> = {
  shipper: 'Shipper',
  consignee: 'Consignee',
  notify_party: 'Notify Party',
  port_of_loading: 'Port of Loading',
  port_of_discharge: 'Port of Discharge',
  container_count: 'Container Count',
  gross_weight_kg: 'Gross Weight (kg)',
}

export const FIELD_SHORT: Record<FieldKey, string> = {
  shipper: 'SH',
  consignee: 'CO',
  notify_party: 'NP',
  port_of_loading: 'PL',
  port_of_discharge: 'PD',
  container_count: 'CC',
  gross_weight_kg: 'GW',
}

/** one colour per field pill (reference: green, orange, red, purple, violet, cyan ...) */
export const FIELD_COLOR: Record<FieldKey, string> = {
  shipper: '#2fe0a0',
  consignee: '#f5a524',
  notify_party: '#ff4d6d',
  port_of_loading: '#d16bff',
  port_of_discharge: '#8b7bff',
  container_count: '#38bdf8',
  gross_weight_kg: '#22e5e5',
}

export const CATEGORY_LABEL: Record<string, string> = {
  BL_COMPARISON: 'Compare',
  SI_REQUEST: 'SI request',
  INVOICE_QUERY: 'Invoice',
  GENERAL: 'General',
  SPAM: 'Spam',
}

export const CATEGORY_COLOR: Record<string, string> = {
  BL_COMPARISON: '#4ea1ff',
  SI_REQUEST: '#f5a524',
  INVOICE_QUERY: '#b38bff',
  GENERAL: '#2fe0a0',
  SPAM: '#ff5d73',
}

export const STATUS_COLOR: Record<string, string> = {
  OK: '#2fe0a0',
  MISMATCH: '#ff5d73',
  NEEDS_REVIEW: '#f5b324',
}

export const ENGINE_COLOR: Record<string, string> = {
  gemini: '#b38bff',
  rules: '#4de3d1',
  pure: '#8ea0c9',
  flynet: '#f5b324',
}

export const isFieldNode = (id: string) => id.startsWith('field:')
export const fieldOfNode = (id: string) => id.slice(6) as FieldKey

export function foldEvents(events: TraceEvent[]): NodeMap {
  const m: NodeMap = {}
  if (!events.length) return m
  for (const e of events) {
    const prev = m[e.node]
    const hasPayload = e.payload && Object.keys(e.payload).length > 0
    let state: NodeState = 'idle'
    if (e.state === 'start') state = 'running'
    else if (e.state === 'done') state = 'done'
    else if (e.state === 'error') state = 'error'
    else if (e.state === 'skipped') state = 'skipped'
    m[e.node] = {
      state,
      engine: e.engine ?? prev?.engine,
      duration_ms: e.duration_ms ?? (e.state === 'start' ? null : prev?.duration_ms),
      summary: e.summary ?? prev?.summary,
      payload: hasPayload ? e.payload : prev?.payload,
      t_ms: e.t_ms,
      startT: e.state === 'start' ? e.t_ms : prev?.startT,
    }
  }
  // inbox is implicit: mark done as soon as anything happened
  if (!m.inbox) m.inbox = { state: 'done', engine: 'pure', t_ms: 0 }
  const reportDone = m.report?.state === 'done'
  const all = ['aggregator', 'compare', 'gate', ...FIELD_KEYS.map((k) => `field:${k}`)]
  for (const id of all) {
    if (!m[id]) m[id] = { state: reportDone ? 'skipped' : 'pending' }
  }
  for (const id of ['classifier', 'report']) if (!m[id]) m[id] = { state: 'pending' }
  return m
}

export function reportOf(events: TraceEvent[]): Result | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i]
    if (e.node === 'report' && e.state === 'done' && e.payload && 'category' in e.payload) {
      return e.payload as unknown as Result
    }
  }
  return null
}

export const fmtTime = (iso: string | undefined) => {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso.slice(11, 16) || iso.slice(0, 5)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
}

export const fmtMs = (ms: number | null | undefined) =>
  ms == null ? '' : ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`

export const pct = (v: number | null | undefined, digits = 0) => (v == null ? '-' : `${(v * 100).toFixed(digits)}%`)
