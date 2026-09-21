import type {
  EmailRow, FlyBrain, FlyFeedback, FieldResult, Health, Mode, Result, ReviewBody, Stats, TraceEvent,
} from '../types'
import { MOCK_RESULTS, MOCK_ROWS, MOCK_STATS, schematicFly } from '../mock'

// ---------------------------------------------------------------- helpers

async function fetchJson<T>(url: string, init?: RequestInit, timeoutMs = 8000): Promise<T> {
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), timeoutMs)
  try {
    const res = await fetch(url, { ...init, signal: ctl.signal })
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
    const text = await res.text()
    return JSON.parse(text) as T // throws if SPA fallback returned html
  } finally {
    clearTimeout(timer)
  }
}

/** Read a text/event-stream (or ndjson) response body via fetch and hand each JSON payload to `onMsg`. */
export async function readStream(res: Response, onMsg: (m: unknown) => void, signal?: AbortSignal): Promise<void> {
  if (!res.ok || !res.body) throw new Error(`${res.status} ${res.statusText}`)
  const reader = res.body.getReader()
  const dec = new TextDecoder()
  let buf = ''
  const flush = (block: string) => {
    const data = block
      .split(/\r?\n/)
      .filter((l) => l.startsWith('data:'))
      .map((l) => l.slice(5).trimStart())
      .join('\n')
    const raw = data || (block.trim().startsWith('{') ? block.trim() : '')
    if (!raw || raw === '[DONE]') return
    try { onMsg(JSON.parse(raw)) } catch { /* ignore keep-alives / partial junk */ }
  }
  for (;;) {
    if (signal?.aborted) { void reader.cancel(); return }
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    const parts = buf.split(/\r?\n\r?\n/)
    buf = parts.pop() ?? ''
    parts.forEach(flush)
  }
  if (buf.trim()) flush(buf)
}

const isEvent = (m: unknown): m is TraceEvent =>
  !!m && typeof m === 'object' && 'node' in m && 'state' in m

// Accept several plausible shapes of index.json / GET /api/emails
type Raw = Record<string, unknown>
export function normalizeRows(raw: unknown): EmailRow[] {
  const arr: Raw[] = Array.isArray(raw)
    ? (raw as Raw[])
    : (((raw as Raw)?.emails ?? (raw as Raw)?.items ?? (raw as Raw)?.results ?? []) as Raw[])
  return arr.map((it) => {
    const r = (it.result ?? it.result_summary ?? (it.category ? it : null)) as Result | null
    return {
      email_id: String(it.email_id ?? r?.email_id ?? ''),
      from: String(it.from ?? r?.from ?? ''),
      subject: String(it.subject ?? r?.subject ?? ''),
      received_at: String(it.received_at ?? r?.received_at ?? ''),
      has_attachments: (it.has_attachments as boolean | undefined) ?? undefined,
      result: r ? ({ ...r, email_id: String(it.email_id ?? r.email_id) } as Result) : null,
    }
  }).filter((r) => r.email_id)
}

/** Derive stats locally when no stats endpoint/file exists. */
export function deriveStats(rows: EmailRow[]): Stats {
  const classified: Record<string, number> = {}
  const issues: Record<string, number> = {}
  let comparisons = 0, mismatches = 0, needs = 0, disc = 0, processed = 0
  for (const r of rows) {
    const x = r.result
    if (!x) continue
    processed++
    classified[x.category] = (classified[x.category] ?? 0) + 1
    if (x.category === 'BL_COMPARISON') {
      comparisons++
      if (x.status === 'MISMATCH') mismatches++
      if (x.status === 'NEEDS_REVIEW') needs++
      for (const f of x.defect_fields ?? []) { issues[f] = (issues[f] ?? 0) + 1; disc++ }
    }
  }
  return {
    emails_total: rows.length, processed, classified, comparisons, mismatches, needs_review: needs,
    discrepancies_found: disc, accuracy_vs_labels: null,
    top_issues: Object.entries(issues).map(([label, count]) => ({ label, count })).sort((a, b) => b.count - a.count),
  }
}

const norm = (v: string | null | undefined) => (v ?? '').toLowerCase().replace(/[.,]/g, '').replace(/\s+/g, ' ').trim()

/** Local simulation of POST /api/review, used in REPLAY/mock mode only. */
export function simulateReview(cur: Result, body: ReviewBody): { result: Result; feedback: FlyFeedback } {
  // strip events first: a report event's payload may reference the result itself (circular)
  const { events, ...rest } = cur
  const res: Result = JSON.parse(JSON.stringify(rest))
  res.events = events
  let fields: FieldResult[] = res.fields ?? []
  if (body.decision === 'correct_field' && body.field) {
    fields = fields.map((f) => {
      if (f.field !== body.field) return f
      const si = body.corrected_si ?? f.si_value
      const bl = body.corrected_bl ?? f.bl_value
      return { ...f, si_value: si, bl_value: bl, match: norm(si) === norm(bl) && norm(si) !== '', note: 'Corrected by human reviewer' }
    })
  }
  if (body.decision === 'confirm_ok') fields = fields.map((f) => (f.match ? f : { ...f, match: true, note: 'Confirmed OK by human reviewer' }))
  const bad = fields.filter((f) => !f.match)
  res.fields = fields
  res.defect_fields = bad.map((f) => String(f.field))
  res.has_defect = bad.length > 0
  res.status = bad.length ? 'MISMATCH' : 'OK'
  res.review_reason = null
  res.headline = bad.length
    ? bad.map((f) => `${f.field}: SI ${f.si_value ?? '-'} / BL ${f.bl_value ?? '-'}`).join('; ')
    : 'No mismatch detected'
  if (res.escalation) res.escalation = { ...res.escalation, open: false, resolved: true }
  const before = res.gate?.suspicion ?? 0.5
  const verdict = body.escalation_verdict ?? (res.gate?.escalate ? 'escalation_correct' : 'escalation_unneeded')
  const after = Math.min(0.99, Math.max(0.01, verdict === 'escalation_unneeded' ? before * 0.82 : before * 1.08 + 0.02))
  return { result: res, feedback: { before, after, verdict, simulated: true } }
}

// ---------------------------------------------------------------- sources

export interface DataSource {
  mode: Mode
  engine: string
  nEmails?: number
  loadEmails(): Promise<EmailRow[]>
  loadStats(rows: EmailRow[]): Promise<Stats>
  loadFly(): Promise<FlyBrain>
  loadTrace(id: string): Promise<Result | null>
  /** live only: run pipeline, streaming events. Resolves when stream ends. */
  process?(id: string, onEvent: (e: TraceEvent) => void, signal: AbortSignal, opts?: { retry?: boolean; forceEngine?: string }): Promise<void>
  processAll?(onProgress: (m: unknown) => void, signal: AbortSignal): Promise<void>
  review(id: string, body: ReviewBody, current: Result): Promise<{ result: Result; feedback: FlyFeedback | null }>
}

const looksLikeFly = (x: unknown): x is FlyBrain =>
  !!x && typeof x === 'object' && Array.isArray((x as FlyBrain).projection) && typeof (x as FlyBrain).n_kc === 'number'

class LiveSource implements DataSource {
  mode: Mode = 'live'
  constructor(public engine: string, public nEmails?: number) {}
  async loadEmails() { return normalizeRows(await fetchJson<unknown>('/api/emails')) }
  async loadStats(rows: EmailRow[]) {
    try { return await fetchJson<Stats>('/api/stats') } catch { return deriveStats(rows) }
  }
  async loadFly() {
    try {
      const f = await fetchJson<FlyBrain>('/api/flybrain')
      if (looksLikeFly(f)) return f
    } catch { /* fall through */ }
    return schematicFly()
  }
  async loadTrace(id: string) {
    try { return await fetchJson<Result>(`/api/result/${encodeURIComponent(id)}`) } catch { return null }
  }
  async process(id: string, onEvent: (e: TraceEvent) => void, signal: AbortSignal, opts: { retry?: boolean; forceEngine?: string } = {}) {
    const q = opts.forceEngine ? `?force_engine=${opts.forceEngine}` : ''
    const path = opts.retry ? 'retry' : 'process'
    const res = await fetch(`/api/${path}/${encodeURIComponent(id)}${q}`, { method: 'POST', signal })
    await readStream(res, (m) => { if (isEvent(m)) onEvent(m) }, signal)
  }
  async processAll(onProgress: (m: unknown) => void, signal: AbortSignal) {
    const res = await fetch('/api/process_all', { method: 'POST', signal })
    await readStream(res, onProgress, signal)
  }
  async review(id: string, body: ReviewBody, current: Result) {
    let before = current.gate?.suspicion ?? 0.5
    const res = await fetch(`/api/review/${encodeURIComponent(id)}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error(`review failed: ${res.status} ${await res.text().catch(() => '')}`)
    const result = (await res.json()) as Result
    let feedback: FlyFeedback | null = null
    try {
      const f = await fetchJson<FlyBrain>('/api/flybrain')
      const h = f.history?.[f.history.length - 1]
      if (h) { before = h.before; feedback = { before, after: h.after, verdict: h.verdict, simulated: false } }
    } catch { /* optional */ }
    return { result, feedback }
  }
}

class ReplaySource implements DataSource {
  mode: Mode
  engine = 'rules'
  private overrides = new Map<string, Result>()
  private mockRows = false
  constructor(mock: boolean, engine = 'rules') { this.mode = mock ? 'mock' : 'replay'; this.mockRows = mock; this.engine = engine }
  get nEmails() { return undefined }
  async loadEmails() {
    if (this.mockRows) return MOCK_ROWS
    return normalizeRows(await fetchJson<unknown>('/replay/index.json'))
  }
  async loadStats(rows: EmailRow[]) {
    if (this.mockRows) return MOCK_STATS
    try { return await fetchJson<Stats>('/replay/stats.json') } catch { return deriveStats(rows) }
  }
  async loadFly() {
    if (!this.mockRows) {
      try {
        const f = await fetchJson<FlyBrain>('/replay/flybrain.json')
        if (looksLikeFly(f)) return f
      } catch { /* schematic fallback */ }
    }
    return schematicFly()
  }
  async loadTrace(id: string) {
    const o = this.overrides.get(id)
    if (o) return o
    if (!this.mockRows) {
      try { return await fetchJson<Result>(`/replay/traces/${encodeURIComponent(id)}.json`) } catch { /* fall through */ }
    }
    return MOCK_RESULTS.find((r) => r.email_id === id) ?? null
  }
  async review(_id: string, body: ReviewBody, current: Result) {
    const { result, feedback } = simulateReview(current, body)
    this.overrides.set(current.email_id, result)
    return { result, feedback }
  }
}

/** Auto-detect: LIVE if /api/health answers JSON ok, else REPLAY if /replay/index.json parses, else MOCK. */
export async function detectSource(): Promise<DataSource> {
  const forced = new URLSearchParams(location.search).get('mode')
  if (forced !== 'replay' && forced !== 'mock') {
    try {
      const h = await fetchJson<Health>('/api/health', undefined, 1500)
      if (h && h.ok) return new LiveSource(h.engine, h.n_emails)
    } catch { /* not live */ }
    if (forced === 'live') return new LiveSource('unknown')
  }
  if (forced !== 'mock') {
    try {
      const idx = normalizeRows(await fetchJson<unknown>('/replay/index.json', undefined, 4000))
      if (idx.length) {
        let engine = 'rules'
        try {
          const first = await fetchJson<Result>(`/replay/traces/${encodeURIComponent(idx[0].email_id)}.json`, undefined, 3000)
          engine = first.engine?.fields ?? first.engine?.classifier ?? 'rules'
        } catch { /* keep default */ }
        return new ReplaySource(false, engine)
      }
    } catch { /* fall through to mock */ }
  }
  return new ReplaySource(true)
}
