import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ArrowLeft, CheckCircle2, FileSearch, Pencil, RotateCcw, ShieldAlert, XCircle } from 'lucide-react'
import type { FieldResult, FlyFeedback, Mode, Result, ReviewBody } from '../types'
import { FIELD_KEYS } from '../types'
import {
  CATEGORY_COLOR, CATEGORY_LABEL, FIELD_COLOR, FIELD_LABEL, STATUS_COLOR, fmtTime, pct, type NodeMap,
} from '../data/graphState'

const REASON_TEXT: Record<string, string> = {
  wrong_doc_type: 'Wrong document type: an attachment is not the SI/BL it should be.',
  missing_attachment: 'Missing attachment: the comparison needs both an SI and a BL.',
  unreadable: 'Unreadable document: text could not be extracted reliably.',
  missing_value: 'Missing value: a required field could not be found in a document.',
}

const label = (f: string) => (FIELD_LABEL as Record<string, string>)[f] ?? f
const val = (v: string | null | undefined) => (v == null || v === '' ? '—' : v)

interface Props {
  result: Result | null
  nodes: NodeMap
  mode: Mode
  busy: boolean
  feedback: FlyFeedback | null
  onBack: () => void
  onReview: (body: ReviewBody) => Promise<void>
  onRetry: () => void
}

export default function ReportView({ result, nodes, mode, busy, feedback, onBack, onReview, onRetry }: Props) {
  const [editField, setEditField] = useState<string | null>(null)
  const [si, setSi] = useState('')
  const [bl, setBl] = useState('')
  const [verdict, setVerdict] = useState<'escalation_correct' | 'escalation_unneeded'>('escalation_correct')
  const [err, setErr] = useState<string | null>(null)

  const fields: FieldResult[] = result?.fields ?? []
  const isCmp = result?.category === 'BL_COMPARISON'
  const needsReview = !!result && (result.status === 'NEEDS_REVIEW' || (!!result.escalation?.open && !result.escalation?.resolved))
  const resolved = !!result?.escalation?.resolved

  useEffect(() => { setEditField(null); setErr(null); setVerdict(result?.gate?.escalate || result?.status === 'NEEDS_REVIEW' ? 'escalation_correct' : 'escalation_unneeded') }, [result?.email_id])

  const startEdit = (f: string) => {
    const row = fields.find((x) => x.field === f)
    setEditField(f)
    setSi(row?.si_value ?? '')
    setBl(row?.bl_value ?? '')
  }

  const errored = useMemo(() => Object.entries(nodes).filter(([, n]) => n.state === 'error'), [nodes])

  const submit = async (body: ReviewBody) => {
    setErr(null)
    try {
      await onReview({ ...body, escalation_verdict: verdict })
      setEditField(null)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e))
    }
  }

  if (!result) {
    return (
      <div className="report empty-report">
        <button type="button" className="btn small ghost" onClick={onBack}><ArrowLeft size={14} /> Back to pipeline</button>
        <div className="empty-state">
          <FileSearch size={34} strokeWidth={1.4} />
          <p>No report yet. Select an email and let the pipeline finish.</p>
          {errored.length > 0 && (
            <div className="fail-box" role="alert">
              <b>Processing failed at {errored.map(([id]) => id).join(', ')}.</b>
              <button type="button" className="btn small warn" disabled={busy} onClick={onRetry}><RotateCcw size={13} /> Retry failed nodes</button>
            </div>
          )}
        </div>
      </div>
    )
  }

  const stColor = result.status ? STATUS_COLOR[result.status] : CATEGORY_COLOR[result.category] ?? '#6ea8ff'
  const catColor = CATEGORY_COLOR[result.category] ?? '#8ea0c9'
  const cls = nodes.classifier?.payload as { confidence?: number; reasons?: string[] } | null | undefined
  const bad = fields.filter((f) => !f.match)
  const ev = result.escalation?.evidence ?? []

  // Rendered right after the headline (above the comparison table) when a review is actually
  // needed, so it is not pushed below the fold by the table at 1536x1024 (reviews/judge.md #8);
  // kept in its normal place after the table for the "correct a field" / "already resolved" cases,
  // which are not urgent in the same way.
  const reviewSection = (needsReview || editField || resolved) && (
    <section className={`review${needsReview ? ' open' : ''}`} aria-label="Human review">
      <header>
        <ShieldAlert size={17} />
        <h4>{needsReview ? 'Human review needed' : resolved ? 'Human review recorded' : 'Correct a field'}</h4>
        {mode !== 'live' && <span className="sim" title="No backend in this mode; the update is applied locally only">{mode === 'replay' ? 'REPLAY: simulated locally' : 'MOCK: simulated locally'}</span>}
      </header>

      {(result.review_reason || result.escalation?.reason) && (
        <p className="why">
          {result.review_reason && <b>{REASON_TEXT[result.review_reason] ?? result.review_reason}</b>}
          {result.escalation?.reason && <span> {result.escalation.reason}</span>}
        </p>
      )}
      {ev.length > 0 && (
        <ul className="evidence">
          {ev.map((e, i) => (
            <li key={i}><span className="doc">{e.doc}</span>{e.field && <span className="ef">{label(e.field)}</span>}<q>{e.text}</q></li>
          ))}
        </ul>
      )}

      {!resolved && (
        <fieldset className="vd">
          <legend>Was the escalation warranted?</legend>
          <label><input type="radio" name="vd" checked={verdict === 'escalation_correct'} onChange={() => setVerdict('escalation_correct')} /> Yes, escalation was correct</label>
          <label><input type="radio" name="vd" checked={verdict === 'escalation_unneeded'} onChange={() => setVerdict('escalation_unneeded')} /> No, it was unneeded</label>
          <span className="pop-dim">Feeds the fly-net weight update.</span>
        </fieldset>
      )}

      {editField && (
        <form className="fix" onSubmit={(e) => { e.preventDefault(); void submit({ decision: 'correct_field', field: editField, corrected_si: si, corrected_bl: bl }) }}>
          <label>Field
            <select value={editField} onChange={(e) => startEdit(e.target.value)}>
              {FIELD_KEYS.map((k) => <option key={k} value={k}>{label(k)}</option>)}
            </select>
          </label>
          <label>Corrected SI value<input value={si} onChange={(e) => setSi(e.target.value)} /></label>
          <label>Corrected BL value<input value={bl} onChange={(e) => setBl(e.target.value)} /></label>
          <div className="row">
            <button type="submit" className="btn small primary" disabled={busy}>Apply correction</button>
            <button type="button" className="btn small ghost" onClick={() => setEditField(null)}>Cancel</button>
          </div>
        </form>
      )}

      {!resolved && !editField && (
        <div className="row actions">
          <button type="button" className="btn small primary" disabled={busy} onClick={() => void submit({ decision: 'confirm_mismatch', field: bad[0] ? String(bad[0].field) : null })}>Confirm mismatch</button>
          <button type="button" className="btn small" disabled={busy} onClick={() => void submit({ decision: 'confirm_ok' })}>Confirm: no mismatch</button>
          <button type="button" className="btn small ghost" disabled={busy} onClick={() => startEdit(String((bad[0] ?? fields[0])?.field ?? 'shipper'))}><Pencil size={13} /> Correct a field</button>
        </div>
      )}
      {err && <p className="pop-err" role="alert">{err}</p>}
      {feedback && feedback.skippedReason && (
        <p className="fb fb-skip" role="status">
          No fly-net weight update: {feedback.skippedReason}
        </p>
      )}
      {feedback && !feedback.skippedReason && (
        <p className="fb" role="status">
          Fly net updated from your verdict ({feedback.verdict.replace('_', ' ')}): suspicion {feedback.before.toFixed(2)} &rarr; {feedback.after.toFixed(2)}
          {feedback.simulated ? ' (simulated)' : ''}.
        </p>
      )}
    </section>
  )

  return (
    <div className="report">
      <div className="rep-top">
        <button type="button" className="btn small ghost" onClick={onBack}><ArrowLeft size={14} /> Back to pipeline</button>
        <span className="rep-id mono">{result.email_id}</span>
      </div>

      <div className="rep-mail">
        <div>
          <h3>{result.subject || '(no subject)'}</h3>
          <p>{result.from} &middot; <span title="Arrival time is simulated - the dataset has no timestamps">{fmtTime(result.received_at)} (simulated)</span></p>
        </div>
        <div className="rep-chips">
          <span className="cat" style={{ color: catColor, borderColor: catColor + '55', background: catColor + '18' }}>{CATEGORY_LABEL[result.category] ?? result.category}</span>
          {result.engine?.classifier && <span className={`eng eng-${result.engine.classifier}`} title="engine that classified this email">classifier: {result.engine.classifier}</span>}
          {result.engine?.fields && <span className={`eng eng-${result.engine.fields}`} title="engine that extracted the fields">fields: {result.engine.fields}</span>}
        </div>
      </div>

      <div className="headline" style={{ '--hc': stColor } as React.CSSProperties} role="status">
        {result.status === 'OK' && <CheckCircle2 size={26} />}
        {result.status === 'MISMATCH' && <XCircle size={26} />}
        {result.status === 'NEEDS_REVIEW' && <ShieldAlert size={26} />}
        {!result.status && <FileSearch size={26} />}
        <div>
          <strong>{result.headline ?? (result.status === 'OK' ? 'No mismatch detected' : result.status ?? 'Classified')}</strong>
          <span>{result.status ? `Status: ${result.status.replace('_', ' ')}` : 'Classification only. Only document-comparison requests are checked.'}{resolved ? ' · resolved by human review' : ''}</span>
        </div>
      </div>

      {!isCmp && (
        <div className="cls-card">
          <dl className="kv">
            <dt>Category</dt><dd><b>{result.category}</b></dd>
            <dt>Confidence</dt><dd>{cls?.confidence != null ? pct(cls.confidence) : '-'}</dd>
          </dl>
          {(cls?.reasons?.length ?? 0) > 0 && <ul className="reasons">{cls!.reasons!.map((r, i) => <li key={i}>{r}</li>)}</ul>}
          <p className="pop-dim">No field comparison was run for this category.</p>
        </div>
      )}

      {errored.length > 0 && (
        <div className="fail-box" role="alert">
          <AlertTriangle size={16} />
          <span><b>Processing failure</b> at {errored.map(([id, n]) => `${id}${n.summary ? ` (${n.summary})` : ''}`).join('; ')}</span>
          <button type="button" className="btn small warn" disabled={busy} onClick={onRetry}><RotateCcw size={13} /> Retry{mode !== 'live' ? ' (simulated)' : ''}</button>
        </div>
      )}

      {isCmp && needsReview && reviewSection}

      {isCmp && (
        <div className="cmp-wrap">
          <table className="cmp">
            <thead><tr><th>Field</th><th>Shipping Instruction (SI)</th><th>Bill of Lading (BL)</th><th aria-label="Verdict">Result</th><th /></tr></thead>
            <tbody>
              {(fields.length ? fields : FIELD_KEYS.map((k) => ({ field: k, si_value: null, bl_value: null, match: false }) as FieldResult)).map((f, ri) => (
                <tr key={`${result.email_id}:${f.field}:${f.match}`} className={!fields.length || f.match ? 'ok' : 'bad'} style={{ '--ri': ri } as React.CSSProperties}>
                  <th scope="row"><i style={{ background: FIELD_COLOR[f.field as keyof typeof FIELD_COLOR] ?? '#6ea8ff' }} />{label(f.field)}</th>
                  <td><b>{val(f.si_value)}</b>{f.si_evidence && <em title={f.si_evidence}>{f.si_evidence}</em>}</td>
                  <td><b>{val(f.bl_value)}</b>{f.bl_evidence && <em title={f.bl_evidence}>{f.bl_evidence}</em>}</td>
                  <td className="verdict">{fields.length ? (f.match ? <span className="ok">match</span> : <span className="bad">mismatch</span>) : <span className="warn">n/a</span>}{f.note && <em>{f.note}</em>}</td>
                  <td className="act">{fields.length > 0 && <button type="button" className="ib" aria-label={`Correct ${label(f.field)}`} title="Correct this field" onClick={() => startEdit(String(f.field))}><Pencil size={13} /></button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {result.gate && (
            <p className="gate-line">
              Fly gate: suspicion <b>{result.gate.suspicion.toFixed(2)}</b> vs threshold {result.gate.threshold.toFixed(2)} &rarr;{' '}
              <b className={result.gate.escalate ? 'warn' : 'ok'}>{result.gate.escalate ? 'escalate' : 'confident'}</b>{result.gate.reason ? ` · ${result.gate.reason}` : ''}
            </p>
          )}
        </div>
      )}

      {isCmp && !needsReview && (editField || resolved) && reviewSection}
    </div>
  )
}
