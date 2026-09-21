import { AlertTriangle, Mail, Target, Truck, Loader2 } from 'lucide-react'
import type { Mode, Stats } from '../types'
import { FIELD_KEYS } from '../types'
import { FIELD_LABEL } from '../data/graphState'
import { Logo } from './icons'
import CountUp from './CountUp'

interface Props {
  stats: Stats | null
  engine: string
  mode: Mode
  online: boolean
  canProcessAll: boolean
  busyAll: boolean
  onProcessAll: () => void
}

/** backend labels look like "container_count mismatch" or "needs review: wrong doc type" */
const issueKey = (label: string) => label.replace(/ mismatch$/, '')
function issueText(label: string): { text: string; tail: string } {
  const m = label.match(/^(\w+) mismatch$/)
  if (m && (FIELD_LABEL as Record<string, string>)[m[1]]) return { text: (FIELD_LABEL as Record<string, string>)[m[1]], tail: '' }
  if ((FIELD_LABEL as Record<string, string>)[label]) return { text: (FIELD_LABEL as Record<string, string>)[label], tail: '' }
  const r = label.match(/^needs review: (.+)$/)
  if (r) return { text: r[1].charAt(0).toUpperCase() + r[1].slice(1), tail: 'needs review' }
  return { text: label, tail: '' }
}

export default function Sidebar({ stats, engine, mode, online, canProcessAll, busyAll, onProcessAll }: Props) {
  const acc = stats?.accuracy_vs_labels
  const accPct = acc == null ? null : acc <= 1 ? acc * 100 : acc

  // top issues: real defect-field counts, padded with zero-count fields to always show 5 rows
  const issues = [...(stats?.top_issues ?? [])].slice(0, 5)
  for (const k of FIELD_KEYS) {
    if (issues.length >= 5) break
    if (!issues.some((i) => issueKey(i.label) === k)) issues.push({ label: k, count: 0 })
  }

  const items = [
    { Icon: Mail, tone: 'blue', value: stats?.emails_total ?? null, dec: 0, label: 'Emails to process', sub: stats ? `${stats.processed} processed` : '' },
    { Icon: Truck, tone: 'amber', value: stats?.comparisons ?? null, dec: 0, label: 'Shipments compared', sub: stats?.classified ? `${Object.values(stats.classified).reduce((a, b) => a + b, 0) - (stats.comparisons ?? 0)} other emails` : '' },
    { Icon: AlertTriangle, tone: 'red', value: stats?.discrepancies_found ?? null, dec: 0, label: 'Discrepancies found', sub: stats ? `${stats.mismatches ?? 0} mismatch · ${stats.needs_review ?? 0} review` : '' },
    { Icon: Target, tone: 'green', value: accPct, dec: 1, suffix: '%', label: 'Accuracy vs. labels', sub: acc == null ? 'offline self-eval: n/a' : 'offline self-eval on the synthetic set' },
  ]

  return (
    <aside className="sidebar panel" aria-label="Overview">
      <div className="brand">
        <Logo />
        <div>
          <b>ARGUS</b>
          <span title="Autonomous Review &amp; Guidance for Uncertain Shipping">Shipping document verification</span>
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
              <strong>{it.value == null ? '-' : <CountUp value={it.value} decimals={it.dec} suffix={it.suffix ?? ''} group />}</strong>
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
              <span className="lbl" title={i.label}>{issueText(i.label).text}{issueText(i.label).tail && <em>{issueText(i.label).tail}</em>}</span>
              <span className="cnt"><CountUp value={i.count} ms={700} /></span>
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
        <svg viewBox="0 0 220 140" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="mt-back" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#1c4a6e" stopOpacity=".55" /><stop offset="1" stopColor="#0a1a30" stopOpacity=".2" /></linearGradient>
            <linearGradient id="mt-mid" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#12324f" stopOpacity=".85" /><stop offset="1" stopColor="#060e20" stopOpacity=".6" /></linearGradient>
            <linearGradient id="mt-haze" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2a7f95" stopOpacity="0" /><stop offset=".55" stopColor="#2a7f95" stopOpacity=".2" /><stop offset="1" stopColor="#0a1a30" stopOpacity="0" /></linearGradient>
          </defs>
          <path d="M0 78 L22 62 L44 74 L76 42 L104 68 L134 48 L168 72 L196 54 L220 66 L220 140 L0 140Z" fill="url(#mt-back)" />
          <rect x="0" y="66" width="220" height="30" fill="url(#mt-haze)" />
          <path d="M0 100 L30 84 L58 96 L92 70 L128 94 L160 80 L190 96 L220 84 L220 140 L0 140Z" fill="url(#mt-mid)" />
          <path d="M0 122 L40 110 L84 120 L132 106 L176 118 L220 108 L220 140 L0 140Z" fill="#050b1a" fillOpacity=".9" />
        </svg>
        <p>Compare with confidence.<br />Escalate when unsure.</p>
        <div className="bar"><span /></div>
      </div>
    </aside>
  )
}
