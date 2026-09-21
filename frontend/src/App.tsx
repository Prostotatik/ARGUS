import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Activity, FileText, Network, Play, SkipForward } from 'lucide-react'
import type { EmailRow, FlyBrain, FlyFeedback, GateInfo, Result, ReviewBody, Stats, TraceEvent } from './types'
import { FIELD_KEYS } from './types'
import { deriveStats, detectSource, type DataSource } from './data/source'
import { foldEvents, reportOf, STATUS_COLOR } from './data/graphState'
import { usePlayer } from './data/usePlayer'
import { useReducedMotion } from './hooks/useReducedMotion'
import Sidebar from './components/Sidebar'
import EmailList from './components/EmailList'
import GraphPanel from './components/GraphPanel'
import FlyPanel from './components/FlyPanel'
import Timeline from './components/Timeline'
import ReportView from './components/ReportView'

type View = 'graph' | 'report'
const MODE_TEXT = { live: 'LIVE', replay: 'REPLAY', mock: 'MOCK' } as const
const MODE_HINT = {
  live: 'Connected to the backend (SSE)',
  replay: 'Replaying precomputed traces (no backend)',
  mock: 'Built-in mock data: no backend and no replay files found',
} as const

export default function App() {
  const reduced = useReducedMotion()
  const [source, setSource] = useState<DataSource | null>(null)
  const [rows, setRows] = useState<EmailRow[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [fly, setFly] = useState<FlyBrain | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [view, setView] = useState<View>('graph')
  const [overrides, setOverrides] = useState<Record<string, Result>>({})
  const [feedback, setFeedback] = useState<{ id: string; fb: FlyFeedback } | null>(null)
  const [busy, setBusy] = useState(false)
  const [busyAll, setBusyAll] = useState(false)
  const [toast, setToast] = useState<{ text: string; kind: 'info' | 'error' } | null>(null)
  const [bootError, setBootError] = useState<string | null>(null)

  const player = usePlayer(reduced)
  const runRef = useRef(0)
  const abortRef = useRef<AbortController | null>(null)
  const toastTimer = useRef<number | null>(null)
  const rowsRef = useRef<EmailRow[]>([])
  rowsRef.current = rows

  const say = useCallback((text: string, kind: 'info' | 'error' = 'info') => {
    setToast({ text, kind })
    if (toastTimer.current) window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(null), kind === 'error' ? 7000 : 4200)
  }, [])

  const refreshStats = useCallback(async (src: DataSource, r: EmailRow[]) => {
    try { setStats(await src.loadStats(r)) } catch { setStats(deriveStats(r)) }
  }, [])

  // ---- selecting / playing an email
  const select = useCallback(async (id: string, src: DataSource | null = source) => {
    if (!src) return
    const my = ++runRef.current
    abortRef.current?.abort()
    const ctl = new AbortController()
    abortRef.current = ctl
    setSelectedId(id)
    setView('graph')
    setFeedback(null)
    if (src.mode === 'live') {
      setOverrides((o) => { const n = { ...o }; delete n[id]; return n })
      player.begin(false)
      try {
        await src.process!(id, (ev) => { if (runRef.current === my) player.push(ev) }, ctl.signal)
      } catch (e) {
        if (!ctl.signal.aborted && runRef.current === my) say(`Backend error while processing ${id}: ${e instanceof Error ? e.message : e}`, 'error')
      } finally {
        if (runRef.current === my) {
          player.end()
          try {
            const rs = await src.loadEmails()
            setRows(rs)
            void refreshStats(src, rs)
          } catch { /* keep old rows */ }
        }
      }
    } else {
      const r = await src.loadTrace(id)
      if (runRef.current !== my) return
      if (!r?.events?.length) {
        player.reset()
        say(`No recorded trace for ${id}.`, 'error')
        return
      }
      player.playAll(r.events)
    }
  }, [source, player, say, refreshStats])

  // ---- boot
  useEffect(() => {
    let dead = false
    ;(async () => {
      try {
        const src = await detectSource()
        if (dead) return
        const r = await src.loadEmails()
        if (dead) return
        setSource(src)
        setRows(r)
        void refreshStats(src, r)
        void src.loadFly().then((f) => { if (!dead) setFly(f) })
        if (src.mode !== 'live' && r.length) {
          const pick =
            r.find((x) => x.result?.category === 'BL_COMPARISON' && x.result.status === 'MISMATCH') ??
            r.find((x) => x.result?.category === 'BL_COMPARISON') ?? r[0]
          void select(pick.email_id, src)
        }
      } catch (e) {
        if (!dead) setBootError(e instanceof Error ? e.message : String(e))
      }
    })()
    return () => { dead = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ---- derived state
  const nodes = useMemo(() => foldEvents(player.shown), [player.shown])
  const active = player.shown.length > 0
  const reportEv = useMemo(() => reportOf(player.shown), [player.shown])
  const override = selectedId ? overrides[selectedId] : undefined
  const result: Result | null = (!player.playing && override) || reportEv
  const row = rows.find((r) => r.email_id === selectedId) ?? null
  const totalMs = useMemo(() => (player.shown.length ? Math.max(...player.shown.map((e) => e.t_ms)) : null), [player.shown])
  const gate: GateInfo | null = (nodes.gate?.payload && 'suspicion' in nodes.gate.payload ? (nodes.gate.payload as unknown as GateInfo) : null) ?? (result?.gate ?? null)
  const gateShown = gate && nodes.gate?.state === 'done' ? gate : null
  const errored = Object.values(nodes).some((n) => n.state === 'error')
  const fb = feedback && feedback.id === selectedId ? feedback.fb : null

  // ---- retry
  const retry = useCallback(async () => {
    if (!source || !selectedId) return
    const my = ++runRef.current
    abortRef.current?.abort()
    const ctl = new AbortController()
    abortRef.current = ctl
    const failed = Object.entries(nodes).filter(([, n]) => n.state === 'error').map(([id]) => id)
    if (source.mode === 'live' && source.process) {
      player.begin(true)
      try {
        await source.process(selectedId, (ev) => { if (runRef.current === my) player.push(ev) }, ctl.signal, { retry: true })
      } catch (e) {
        if (!ctl.signal.aborted) say(`Retry failed: ${e instanceof Error ? e.message : e}`, 'error')
      } finally {
        if (runRef.current === my) player.end()
      }
    } else {
      // REPLAY/mock cannot re-run a node; replay the recorded outcome and say so.
      player.begin(true)
      let seq = 10000
      failed.forEach((id, i) => {
        player.push({ seq: seq++, t_ms: (totalMs ?? 0) + 10 + i, node: id, state: 'start', engine: nodes[id]?.engine, summary: 'retry (simulated)' })
      })
      failed.forEach((id, i) => {
        const prev = nodes[id]
        player.push({ seq: seq++, t_ms: (totalMs ?? 0) + 60 + i, node: id, state: 'error', engine: prev?.engine, duration_ms: prev?.duration_ms, summary: `${prev?.summary ?? 'error'} (same outcome: replay cannot re-run nodes)`, payload: prev?.payload } as TraceEvent)
      })
      player.end()
      say('Retry is simulated in REPLAY mode: recorded traces cannot be re-run. Start the backend for real retries.')
    }
  }, [source, selectedId, nodes, player, say, totalMs])

  // ---- human review
  const review = useCallback(async (body: ReviewBody) => {
    if (!source || !result || !selectedId) return
    setBusy(true)
    try {
      const { result: upd, feedback: f } = await source.review(selectedId, body, result)
      setOverrides((o) => ({ ...o, [selectedId]: upd }))
      const nextRows = rowsRef.current.map((r) => (r.email_id === selectedId ? { ...r, result: { ...upd, events: undefined } } : r))
      setRows(nextRows)
      if (f) setFeedback({ id: selectedId, fb: f })
      if (source.mode === 'live') { void source.loadFly().then(setFly).catch(() => undefined) }
      void refreshStats(source, nextRows)
      say(source.mode === 'live' ? 'Review saved; report and fly net updated.' : 'Review applied locally (REPLAY mode: simulated, nothing was sent).')
    } finally {
      setBusy(false)
    }
  }, [source, result, selectedId, refreshStats, say])

  const processAll = useCallback(async () => {
    if (!source?.processAll) return
    setBusyAll(true)
    const ctl = new AbortController()
    try {
      await source.processAll(() => undefined, ctl.signal)
      const rs = await source.loadEmails()
      setRows(rs)
      await refreshStats(source, rs)
      say('Whole inbox processed.')
    } catch (e) {
      say(`process_all failed: ${e instanceof Error ? e.message : e}`, 'error')
    } finally {
      setBusyAll(false)
    }
  }, [source, refreshStats, say])

  const mode = source?.mode ?? 'replay'
  const engine = source?.engine ?? 'rules'
  const title = row ? `${row.from || row.email_id} · ${row.subject}` : null
  const stColor = result?.status ? STATUS_COLOR[result.status] : '#6ea8ff'
  const total = stats?.emails_total ?? rows.length

  if (bootError) {
    return (
      <div className="boot-err" role="alert">
        <h1>Asteris could not load data</h1>
        <p>{bootError}</p>
        <p>Start the backend on :8000 or add replay files to <code>public/replay/</code>.</p>
      </div>
    )
  }

  return (
    <div className="app">
      <a className="skip" href="#emails">Skip to emails</a>
      <Sidebar
        stats={stats}
        engine={engine}
        mode={mode}
        online={!!source}
        canProcessAll={mode === 'live' && !!source?.processAll}
        busyAll={busyAll}
        onProcessAll={() => void processAll()}
      />

      <main className="center panel">
        <header className="c-head">
          <div className="c-title">
            <span className="eyebrow">AI processing pipeline</span>
            <h1>From inbox to verified report</h1>
            <p>Multi-agent analysis. Real-time insights.</p>
          </div>
          <div className="c-tools">
            <div className="seg" role="tablist" aria-label="Center view">
              <button type="button" role="tab" aria-selected={view === 'graph'} className={view === 'graph' ? 'on' : ''} onClick={() => setView('graph')}><Network size={14} /> Pipeline</button>
              <button type="button" role="tab" aria-selected={view === 'report'} className={view === 'report' ? 'on' : ''} onClick={() => setView('report')}><FileText size={14} /> Report</button>
            </div>
            {selectedId && (
              player.playing
                ? <button type="button" className="btn small" onClick={player.skip}><SkipForward size={13} /> Skip</button>
                : <button type="button" className="btn small" onClick={() => void select(selectedId)} title={mode === 'live' ? 'Run the pipeline again' : 'Replay the recorded trace'}><Play size={13} /> {mode === 'live' ? 'Re-run' : 'Replay'}</button>
            )}
            <span className={`mode-pill m-${mode}`} title={MODE_HINT[mode]}>
              <span className="dot" />
              {MODE_TEXT[mode]}
              <Activity size={14} />
            </span>
          </div>
        </header>

        <div className="c-body">
          {view === 'graph' ? (
            <>
              <GraphPanel
                nodes={nodes}
                active={active}
                running={player.playing}
                reduced={reduced}
                mode={mode}
                totalEmails={total}
                emailLabel={row ? row.email_id : null}
                result={result}
                onRetry={() => void retry()}
                onOpenReport={() => setView('report')}
              />
              {!active && (
                <div className="idle-hint">Select an email on the right to watch the pipeline work.</div>
              )}
              {result && !player.playing && (
                <button type="button" className={`result-banner${result.status === 'NEEDS_REVIEW' ? ' review' : ''}`} style={{ '--hc': stColor } as React.CSSProperties} onClick={() => setView('report')}>
                  <span className="rb-dot" />
                  <span className="rb-txt">
                    <b>{result.headline ?? result.status ?? 'Classified'}</b>
                    <i>{result.status === 'NEEDS_REVIEW' ? 'Human review needed - open the report to confirm or correct' : result.status ? `${result.status} - ${FIELD_KEYS.length} fields compared` : 'Classification only'}</i>
                  </span>
                  <span className="rb-go">{result.status === 'NEEDS_REVIEW' ? 'Review' : 'Open report'} &rarr;</span>
                </button>
              )}
              {errored && !player.playing && (
                <button type="button" className="retry-banner" onClick={() => void retry()}>A node failed. Retry{mode !== 'live' ? ' (simulated in replay)' : ''}</button>
              )}
            </>
          ) : (
            <ReportView
              result={result}
              nodes={nodes}
              mode={mode}
              busy={busy || player.playing}
              feedback={fb}
              onBack={() => setView('graph')}
              onReview={review}
              onRetry={() => void retry()}
            />
          )}
        </div>
      </main>

      <div className="right" id="emails">
        <EmailList rows={rows} selectedId={selectedId} onSelect={(id) => void select(id)} />
        <FlyPanel
          fly={fly}
          gate={gateShown}
          gateState={active ? nodes.gate?.state ?? 'pending' : 'idle'}
          reduced={reduced}
          feedback={fb}
        />
      </div>

      <Timeline nodes={nodes} active={active} playing={player.playing} result={result} title={title} totalMs={totalMs} />

      <div className="sr-only" aria-live="polite">{result ? `${result.headline ?? ''}` : ''}</div>
      {toast && <div className={`toast ${toast.kind}`} role="status">{toast.text}</div>}
    </div>
  )
}
