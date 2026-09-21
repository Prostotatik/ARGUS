import { memo, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { EmailRow } from '../types'
import { CATEGORY_COLOR, CATEGORY_LABEL, FIELD_LABEL, STATUS_COLOR, fmtTime } from '../data/graphState'

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'BL_COMPARISON', label: 'Compare' },
  { id: 'flagged', label: 'Flagged' },
  { id: 'SI_REQUEST', label: 'SI' },
  { id: 'INVOICE_QUERY', label: 'Invoice' },
  { id: 'GENERAL', label: 'General' },
  { id: 'SPAM', label: 'Spam' },
] as const

/** The chip carries information: for a compared shipment it is the outcome (defect count / OK / Review), otherwise the category. */
function chipFor(r: EmailRow['result']): { text: string; color: string; title: string } | null {
  if (!r) return null
  const catColor = CATEGORY_COLOR[r.category] ?? '#8ea0c9'
  if (r.category === 'BL_COMPARISON' && r.status) {
    const fields = (r.defect_fields ?? []).map((f) => (FIELD_LABEL as Record<string, string>)[f] ?? f)
    if (r.status === 'MISMATCH') {
      const n = Math.max(1, fields.length)
      return { text: `${n} defect${n > 1 ? 's' : ''}`, color: STATUS_COLOR.MISMATCH, title: `Mismatch: ${fields.join(', ') || 'see report'}` }
    }
    if (r.status === 'NEEDS_REVIEW') return { text: 'Review', color: STATUS_COLOR.NEEDS_REVIEW, title: `Needs human review${r.review_reason ? ': ' + String(r.review_reason).replace(/_/g, ' ') : ''}` }
    return { text: 'OK', color: STATUS_COLOR.OK, title: 'All 7 fields match' }
  }
  return { text: CATEGORY_LABEL[r.category] ?? r.category, color: catColor, title: `Category: ${r.category}` }
}

const Row = memo(function Row({ row, selected, onSelect }: { row: EmailRow; selected: boolean; onSelect: (id: string) => void }) {
  const r = row.result
  const cat = r?.category
  const dot = cat ? CATEGORY_COLOR[cat] : undefined
  const chip = chipFor(r)
  return (
    <li data-id={row.email_id}>
      <button type="button" className={`mail${selected ? ' sel' : ''}`} onClick={() => onSelect(row.email_id)} aria-pressed={selected}
        aria-label={`${row.from}: ${row.subject}. ${cat ?? 'not processed'}${r?.status ? ', ' + r.status : ''}${r?.defect_fields?.length ? ', ' + r.defect_fields.length + ' defects' : ''}`}>
        <span className={`sdot${dot ? '' : ' hollow'}`} style={dot ? { background: dot, boxShadow: `0 0 8px ${dot}` } : undefined} title={cat ? `Category: ${cat}` : 'not processed'} />
        <span className="mail-txt">
          <b>{row.from || row.email_id}</b>
          <i>{row.subject}</i>
        </span>
        {chip && <span className="cat" title={chip.title} style={{ color: chip.color, borderColor: chip.color + '4d', background: chip.color + '26' }}>{chip.text}</span>}
        <time title="Arrival time is simulated (the dataset has no timestamps)">{fmtTime(row.received_at)}</time>
      </button>
    </li>
  )
})

interface Props {
  rows: EmailRow[]
  selectedId: string | null
  onSelect: (id: string) => void
  /** ids in the order currently shown (after filter/search): used by keyboard nav and auto-play */
  onVisible?: (ids: string[]) => void
  reduced?: boolean
}

export default function EmailList({ rows, selectedId, onSelect, onVisible, reduced = false }: Props) {
  const [filter, setFilter] = useState<string>('all')
  const [q, setQ] = useState('')
  const listRef = useRef<HTMLUListElement>(null)
  const [ind, setInd] = useState<{ y: number; h: number } | null>(null)
  const ready = useRef(false)

  const sorted = useMemo(() => [...rows].sort((a, b) => (b.received_at || '').localeCompare(a.received_at || '') || a.email_id.localeCompare(b.email_id)), [rows])
  const visible = useMemo(() => {
    const s = q.trim().toLowerCase()
    return sorted.filter((r) => {
      if (filter === 'flagged') { if (r.result?.status !== 'MISMATCH' && r.result?.status !== 'NEEDS_REVIEW') return false }
      else if (filter !== 'all' && r.result?.category !== filter) return false
      if (s && !(`${r.from} ${r.subject} ${r.email_id}`.toLowerCase().includes(s))) return false
      return true
    })
  }, [sorted, filter, q])

  useEffect(() => { onVisible?.(visible.map((r) => r.email_id)) }, [visible, onVisible])

  // sliding selection highlight (transform only) + keep the selected row in view
  useLayoutEffect(() => {
    const ul = listRef.current
    if (!ul || !selectedId) { setInd(null); return }
    const li = ul.querySelector<HTMLElement>(`li[data-id="${CSS.escape(selectedId)}"]`)
    if (!li) { setInd(null); return }
    setInd({ y: li.offsetTop, h: li.offsetHeight })
    const top = li.offsetTop, bottom = top + li.offsetHeight
    if (top < ul.scrollTop || bottom > ul.scrollTop + ul.clientHeight) {
      ul.scrollTo({ top: Math.max(0, top - ul.clientHeight / 2 + li.offsetHeight / 2), behavior: reduced || !ready.current ? 'auto' : 'smooth' })
    }
    requestAnimationFrame(() => { ready.current = true })
  }, [selectedId, visible, reduced])

  return (
    <section className="mails panel" aria-label="Incoming emails">
      <header className="panel-h">
        <h2>Incoming Emails</h2>
        <span className="count">{rows.length}</span>
        <span className="showing">{visible.length !== rows.length ? `${visible.length} shown` : ''}</span>
      </header>
      <div className="filters" role="toolbar" aria-label="Filter emails">
        {FILTERS.map((f) => (
          <button key={f.id} type="button" className={`fchip${filter === f.id ? ' on' : ''}`} onClick={() => setFilter(f.id)} aria-pressed={filter === f.id}>{f.label}</button>
        ))}
      </div>
      <input className="search" type="search" placeholder="Search sender, subject, id" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search emails" />
      <ul className="mail-list" ref={listRef}>
        {ind && <li className={`sel-ind${ready.current ? ' anim' : ''}`} style={{ transform: `translateY(${ind.y}px)`, height: ind.h }} aria-hidden="true" />}
        {visible.map((r) => <Row key={r.email_id} row={r} selected={r.email_id === selectedId} onSelect={onSelect} />)}
        {visible.length === 0 && <li className="empty">No emails match.</li>}
      </ul>
    </section>
  )
}
