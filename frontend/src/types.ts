// Types mirror CONTRACT.md (backend <-> frontend). snake_case on purpose.

export const FIELD_KEYS = [
  'shipper',
  'consignee',
  'notify_party',
  'port_of_loading',
  'port_of_discharge',
  'container_count',
  'gross_weight_kg',
] as const
export type FieldKey = (typeof FIELD_KEYS)[number]

export type Category = 'BL_COMPARISON' | 'SI_REQUEST' | 'INVOICE_QUERY' | 'GENERAL' | 'SPAM'
export type Status = 'OK' | 'MISMATCH' | 'NEEDS_REVIEW'
export type ReviewReason = 'wrong_doc_type' | 'missing_attachment' | 'unreadable' | 'missing_value'

export type NodeId =
  | 'inbox'
  | 'classifier'
  | `field:${FieldKey}`
  | 'aggregator'
  | 'compare'
  | 'gate'
  | 'report'

export type EventState = 'start' | 'done' | 'error' | 'skipped'
export type Engine = 'gemini' | 'rules' | 'pure' | 'flynet'

export interface TraceEvent {
  seq: number
  t_ms: number
  node: string
  state: EventState
  engine?: Engine | string | null
  duration_ms?: number | null
  summary?: string | null
  payload?: Record<string, unknown> | null
}

export interface FieldResult {
  field: FieldKey | string
  si_value: string | null
  bl_value: string | null
  si_norm?: string | number | null
  bl_norm?: string | number | null
  match: boolean
  confidence?: number | null
  si_evidence?: string | null
  bl_evidence?: string | null
  note?: string | null
}

export interface GateInfo {
  suspicion: number
  threshold: number
  escalate: boolean
  reason?: string | null
  input_vector?: number[]
  kc_active?: number[]
  winner_kc?: number | null
  /** per-input share of the drive that pushed suspicion up (backend explain()) */
  drivers?: { input: string; index: number; share: number }[]
}

export interface EvidenceItem {
  doc: string
  field?: string | null
  text: string
}

export interface Escalation {
  open: boolean
  reason?: string | null
  evidence?: EvidenceItem[]
  resolved?: boolean
}

export interface Result {
  email_id: string
  from?: string
  subject?: string
  received_at?: string
  category: Category | string
  status: Status | null
  review_reason?: ReviewReason | string | null
  has_defect?: boolean
  defect_fields?: string[]
  headline?: string
  fields?: FieldResult[]
  gate?: GateInfo | null
  escalation?: Escalation | null
  engine?: { classifier?: string; fields?: string } | null
  errors?: unknown[]
  events?: TraceEvent[]
}

/** Row in the inbox list. */
export interface EmailRow {
  email_id: string
  from: string
  subject: string
  received_at: string
  has_attachments?: boolean
  result: Result | null
}

export interface Stats {
  emails_total: number
  processed: number
  classified?: Record<string, number>
  comparisons?: number
  mismatches?: number
  needs_review?: number
  discrepancies_found?: number
  accuracy_vs_labels?: number | null
  top_issues?: { label: string; count: number }[]
}

export interface FlyBrain {
  n_inputs: number
  n_kc: number
  kc_sparsity?: number
  threshold?: number
  projection: number[][]
  weights?: number[]
  /** optional: human label per input (backend may provide); UI never invents one */
  input_labels?: string[]
  /** backend name per input, e.g. mismatch:shipper, low_conf:shipper, near_miss:*, doc-level flags */
  input_names?: string[]
  history?: { ts: string | number; before: number; after: number; verdict: string }[]
  /** true when we generated a schematic layout because backend/replay did not provide one */
  schematic?: boolean
  /** set by the UI in REPLAY/mock when the user taught the net in this session (weights are a local simulation) */
  taught?: boolean
  /** optional plasticity constants (backend may export them; UI falls back to the documented defaults in REPLAY) */
  eta_dep?: number
  eta_pot?: number
  tau?: number
}

export interface ReviewBody {
  decision: 'confirm_mismatch' | 'confirm_ok' | 'correct_field'
  field?: string | null
  corrected_si?: string | null
  corrected_bl?: string | null
  escalation_verdict?: 'escalation_correct' | 'escalation_unneeded' | null
}

export type Mode = 'live' | 'replay' | 'mock'

export interface Health {
  ok: boolean
  engine: 'gemini' | 'rules' | string
  n_emails?: number
}

/** one Kenyon cell whose KC->decision weight changed after a human verdict */
export interface KcDelta { i: number; before: number; after: number }

export interface FlyFeedback {
  before: number
  after: number
  verdict: string
  simulated: boolean
  /** per-KC weight change on the KCs that fired for this email (real diff when LIVE, documented rule applied locally when REPLAY) */
  kc?: KcDelta[]
  /** bumps on every new review so animations restart */
  nonce?: number
}
