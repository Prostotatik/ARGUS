import { AlertTriangle, Mail, Target, Truck, Loader2 } from 'lucide-react'
import type { Mode, Stats } from '../types'
import { FIELD_KEYS } from '../types'
import { FIELD_LABEL } from '../data/graphState'
import { Logo } from './icons'

interface Props {
  stats: Stats | null
  engine: string
  mode: Mode
  online: boolean
  canProcessAll: boolean
  busyAll: boolean
  onProcessAll: () => void
}

export default function Sidebar({ stats, engine, mode, online, canProcessAll, busyAll, onProcessAll }: Props) {
  const acc = stats?.accuracy_vs_labels
  const accText = acc == null ? '-' : `${(acc <= 1 ? acc * 100 : acc).toFixed(1)}%`

  // top issues: real defect-field counts, padded with zero-count fields to always show 5 rows
  const issues = [...(stats?.top_issues ?? [])].slice(0, 5)
  for (const k of FIELD_KEYS) {
    if (issues.length >= 5) break
    if (!issues.some((i) => i.label === k)) issues.push({ label: k, count: 0 })
  }

  const items = [
    { Icon: Mail, tone: 'blue', value: stats?.emails_total ?? '-', label: 'Emails to process', sub: stats ? `${stats.processed} processed` : '' },
    { Icon: Truck, tone: 'amber', value: stats?.comparisons ?? '-', label: 'Shipments compared', sub: stats?.classified ? `${Object.values(stats.classified).reduce((a, b) => a + b, 0) - (stats.comparisons ?? 0)} other emails` : '' },
    { Icon: AlertTriangle, tone: 'red', value: stats?.discrepancies_found ?? '-', label: 'Discrepancies found', sub: stats ? `${stats.mismatches ?? 0} mismatched, ${stats.needs_review ?? 0} to review` : '' },
    { Icon: Target, tone: 'green', value: accText, label: 'Accuracy vs. labels', sub: acc == null ? 'offline self-eval - n/a' : 'offline self-eval, not live' },
  ]

  return (
    <aside className="sidebar panel" aria-label="Overview">
      <div className="brand">
        <Logo />
        <div>
          <b>Asteris</b>
          <span>Document verification</span>
        </div>
      </div>
      <div className={`sys ${online ? 'on' : 'off'}`}>
        <span className="dot" />
        <span className="sys-t">{online ? 'System Online' : 'Offline'}</span>
        <span className="eng-tag" title="Engine that produced node outputs (gemini = LLM, rules = deterministic offline parsers)">engine: {engine}</span>
      </div>

      <div className="stats">
        {items.map((it) => (
          <div className={`stat tone-${it.tone}`} key={it.label}>
            <span className="stat-ico"><it.Icon size={20} strokeWidth={1.7} /></span>
            <div>
              <strong>{it.value}</strong>
              <span>{it.label}</span>
              {it.sub && <em>{it.sub}</em>}
            </div>
          </div>
        ))}
      </div>

      <div className="issues">
        <h3>Top issues</h3>
        <ol>
          {issues.map((i, n) => (
            <li key={i.label}>
              <span className="rank">{n + 1}</span>
              <span className="lbl">{(FIELD_LABEL as Record<string, string>)[i.label] ?? i.label}</span>
              <span className="cnt">{i.count}</span>
            </li>
          ))}
        </ol>
      </div>

      {canProcessAll && (
        <button type="button" className="btn side-btn" onClick={onProcessAll} disabled={busyAll}>
          {busyAll ? <><Loader2 size={14} className="spin" /> Processing inbox...</> : 'Process entire inbox'}
        </button>
      )}
      <div className="mode-note">{mode === 'live' ? 'Live backend' : mode === 'replay' ? 'Replay of precomputed traces' : 'Built-in mock data (no backend, no replay files)'}</div>

      <div className="side-foot">
        <svg viewBox="0 0 220 90" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="mt" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#17305c" stopOpacity=".7" /><stop offset="1" stopColor="#070d22" stopOpacity="0" /></linearGradient>
          </defs>
          <path d="M0 62 L28 44 L52 58 L84 30 L112 54 L140 38 L176 60 L220 40 L220 90 L0 90Z" fill="url(#mt)" />
        </svg>
        <p>Smarter checks.<br />Smoother trade.</p>
        <div className="bar"><span /></div>
      </div>
    </aside>
  )
}
