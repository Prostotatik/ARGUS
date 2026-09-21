import { memo, useMemo, useState } from 'react'
import type { EmailRow } from '../types'
import { CATEGORY_COLOR, CATEGORY_LABEL, STATUS_COLOR, fmtTime } from '../data/graphState'

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'BL_COMPARISON', label: 'Compare' },
  { id: 'flagged', label: 'Flagged' },
  { id: 'SI_REQUEST', label: 'SI' },
  { id: 'INVOICE_QUERY', label: 'Invoice' },
  { id: 'GENERAL', label: 'General' },
  { id: 'SPAM', label: 'Spam' },
] as const

const Row = memo(function Row({ row, selected, onSelect }: { row: EmailRow; selected: boolean; onSelect: (id: string) => void }) {
  const r = row.result
  const cat = r?.category
  const dot = r?.status ? STATUS_COLOR[r.status] : undefined
  return (
    <li>
      <button type="button" className={`mail${selected ? ' sel' : ''}`} onClick={() => onSelect(row.email_id)} aria-pressed={selected}
        aria-label={`${row.from}: ${row.subject}. ${cat ?? 'not processed'}${r?.status ? ', ' + r.status : ''}`}>
        <span className={`sdot${dot ? '' : r ? ' neutral' : ' hollow'}`} style={dot ? { background: dot, boxShadow: `0 0 8px ${dot}` } : undefined} title={r?.status ?? (r ? 'classified' : 'not processed')} />
        <span className="mail-txt">
          <b>{row.from || row.email_id}</b>
          <i>{row.subject}</i>
        </span>
        {cat && <span className="cat" style={{ color: CATEGORY_COLOR[cat] ?? '#8ea0c9', borderColor: (CATEGORY_COLOR[cat] ?? '#8ea0c9') + '55', background: (CATEGORY_COLOR[cat] ?? '#8ea0c9') + '18' }}>{CATEGORY_LABEL[cat] ?? cat}</span>}
        <time>{fmtTime(row.received_at)}</time>
      </button>
    </li>
  )
})

interface Props {
  rows: EmailRow[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export default function EmailList({ rows, selectedId, onSelect }: Props) {
  const [filter, setFilter] = useState<string>('all')
  const [q, setQ] = useState('')

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
      <ul className="mail-list">
        {visible.map((r) => <Row key={r.email_id} row={r} selected={r.email_id === selectedId} onSelect={onSelect} />)}
        {visible.length === 0 && <li className="empty">No emails match.</li>}
      </ul>
    </section>
  )
}
