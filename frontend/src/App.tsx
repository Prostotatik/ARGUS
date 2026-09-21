import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Activity, AlertTriangle, FileText, Keyboard, Network, Pause, Play, SkipForward } from 'lucide-react'
import type { EmailRow, FlyBrain, FlyFeedback, GateInfo, KcDelta, Result, ReviewBody, Stats, TraceEvent } from './types'
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
import HelpOverlay from './components/HelpOverlay'
import DepthBg from './components/DepthBg'

type View = 'graph' | 'report'
type Speed = 0.25 | 0.5 | 1
const SPEEDS: Speed[] = [0.25, 0.5, 1]
const DEFAULT_SPEED: Speed = 0.5

/** documented plasticity of the backend gate (backend/sdoc/flybrain.py): LTD w*=(1-eta_dep), LTP w+=eta_pot*(1-w); suspicion = 1-exp(-sum(w[active])/tau) */
const ETA_DEP = 0.6
const ETA_POT = 0.5
function applyRule(fly: FlyBrain, w: number[], active: number[], verdict: string): { next: number[]; kc: KcDelta[]; before: number; after: number } {
  const k = Math.round(fly.n_kc * (fly.kc_sparsity ?? 0.05))
  const tau = fly.tau ?? 0.15 * Math.max(1, k)
  const sus = (ww: number[]) => 1 - Math.exp(-active.reduce((a, i) => a + (ww[i] ?? 0), 0) / tau)
  const next = w.slice()
  const kc: KcDelta[] = []
  for (const i of active) {
    const b = w[i] ?? 0
    const a = verdict === 'escalation_unneeded' ? b * (1 - (fly.eta_dep ?? ETA_DEP)) : b + (fly.eta_pot ?? ETA_POT) * (1 - b)
    next[i] = a
    kc.push({ i, before: b, after: a })
  }
  return { next, kc, before: sus(w), after: sus(next) }
}
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
  const [speed, setSpeed] = useState<Speed>(DEFAULT_SPEED)
  const [auto, setAuto] = useState(false)
  const [help, setHelp] = useState(false)
  /** REPLAY/mock only: KC weights after the human teaching done in this session (documented rule, applied locally) */
  const [simW, setSimW] = useState<number[] | null>(null)

  const player = usePlayer(reduced, speed)
  const visibleRef = useRef<string[]>([])
  const onVisible = useCallback((ids: string[]) => { visibleRef.current = ids }, [])
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
  const select = useCallback(async (id: string, src: DataSource | null = source, injectFail?: string) => {
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
        await src.process!(id, (ev) => { if (runRef.current === my) player.push(ev) }, ctl.signal, injectFail ? { injectFail } : undefined)
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
  const flyEff = useMemo<FlyBrain | null>(() => (fly && simW ? { ...fly, weights: simW, taught: true } : fly), [fly, simW])

  // ---- transport: keyboard, auto-play (streams through the visible list, throttled)
  const step = useCallback((dir: 1 | -1) => {
    const ids = visibleRef.current
    if (!ids.length) return
    const i = selectedId ? ids.indexOf(selectedId) : -1
    const next = i < 0 ? (dir > 0 ? 0 : ids.length - 1) : Math.min(ids.length - 1, Math.max(0, i + dir))
    if (next !== i) void select(ids[next])
  }, [selectedId, select])

  const startAuto = useCallback(() => {
    setAuto(true)
    if (!selectedId && visibleRef.current.length) void select(visibleRef.current[0])
  }, [selectedId, select])

  const togglePlay = useCallback(() => {
    if (!auto && !player.playing) { startAuto(); return }
    if (player.paused) player.resume(); else player.pause()
  }, [auto, player, startAuto])

  useEffect(() => {
    if (!auto || player.paused || player.playing || !selectedId || !source) return
    // current run finished: dwell so the result is readable, then advance (never faster than ~1 email / 0.45 s, 1.4 s in LIVE)
    const dwell = Math.max(source.mode === 'live' ? 1400 : 450, 2100 / speed)
    let t = 0
    const advance = () => {
      if (document.hidden) { t = window.setTimeout(advance, 1000); return }
      const ids = visibleRef.current
      const i = ids.indexOf(selectedId)
      if (i < 0 || i >= ids.length - 1) { setAuto(false); say('Auto-play reached the end of the list.'); return }
      void select(ids[i + 1])
    }
    t = window.setTimeout(advance, dwell)
    return () => window.clearTimeout(t)
  }, [auto, player.paused, player.playing, selectedId, speed, source, select, say])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return
      const k = e.key
      if (k === '?' || (k === '/' && e.shiftKey)) { e.preventDefault(); setHelp((h) => !h); return }
      if (k === 'Escape') { setHelp(false); return }
      if (help) return
      if (k === 'j' || k === 'J') { e.preventDefault(); step(1) }
      else if (k === 'k' || k === 'K') { e.preventDefault(); step(-1) }
      else if (k === ' ' || k === 'Spacebar') { e.preventDefault(); togglePlay() }
      else if (k === 'r' || k === 'R') { if (selectedId) { e.preventDefault(); void select(selectedId) } }
      else if (k === 'a' || k === 'A') { e.preventDefault(); if (auto) setAuto(false); else startAuto() }
      else if (k === '1' || k === '2' || k === '4') setSpeed(Number(k) as Speed)
      else if (k === 'g' || k === 'G') setView((v) => (v === 'graph' ? 'report' : 'graph'))
    }
    const onKeyUp = (e: KeyboardEvent) => { if (e.key === ' ' && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) e.preventDefault() }
    window.addEventListener('keydown', onKey)
    window.addEventListener('keyup', onKeyUp)
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener('keyup', onKeyUp) }
  }, [help, step, togglePlay, selectedId, select, auto, startAuto])

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
      const prevW = fly?.weights ? fly.weights.slice() : null
      const { result: upd, feedback: f } = await source.review(selectedId, body, result)
      setOverrides((o) => ({ ...o, [selectedId]: upd }))
      const nextRows = rowsRef.current.map((r) => (r.email_id === selectedId ? { ...r, result: { ...upd, events: undefined } } : r))
      setRows(nextRows)
      const act = gate?.kc_active ?? result.gate?.kc_active ?? []
      let fbFinal: FlyFeedback | null = f ? { ...f, nonce: Date.now() } : null
      if (source.mode === 'live') {
        // real per-KC before/after: diff the exported weights around the review
        try {
          const nf = await source.loadFly()
          setFly(nf)
          if (fbFinal && prevW && nf.weights) {
            const kc = act.map((i) => ({ i, before: prevW[i] ?? 0, after: nf.weights![i] ?? 0 })).filter((d) => Math.abs(d.after - d.before) > 1e-9)
            fbFinal = { ...fbFinal, kc }
          }
        } catch { /* keep the suspicion-only feedback */ }
      } else if (result.gate && result.gate.decided_by !== 'flynet') {
        // A deterministic trigger never went through the gate's own decision - mirror the
        // backend's honesty here too: no simulated weight update, an explicit "nothing to
        // learn" message instead of a misleading before==after no-op.
        const s = result.gate.suspicion ?? 0
        fbFinal = {
          before: s, after: s, verdict: body.escalation_verdict ?? 'escalation_correct', simulated: true,
          skippedReason: 'this escalation was a deterministic trigger, not a fly-gate decision - no weight '
            + 'update applied (the gate never decided anything here to reinforce)', nonce: Date.now(),
        }
      } else if (fly && fly.weights && act.length) {
        // REPLAY/mock: no backend, so apply the documented Hebbian rule to the exported weights locally (labelled simulated)
        const verdict = f?.verdict ?? body.escalation_verdict ?? (result.gate?.escalate ? 'escalation_correct' : 'escalation_unneeded')
        const r = applyRule(fly, simW ?? fly.weights, act, verdict)
        setSimW(r.next)
        fbFinal = { before: r.before, after: r.after, verdict, simulated: true, kc: r.kc, nonce: Date.now() }
      }
      if (fbFinal) setFeedback({ id: selectedId, fb: fbFinal })
      void refreshStats(source, nextRows)
      say(source.mode === 'live' ? 'Review saved; report and fly net updated.' : 'Review applied locally (REPLAY mode: simulated, nothing was sent).')
    } finally {
      setBusy(false)
    }
  }, [source, result, selectedId, refreshStats, say, fly, gate, simW])

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
        <h1>ARGUS could not load data</h1>
        <p>{bootError}</p>
        <p>Start the backend on :8000 or add replay files to <code>public/replay/</code>.</p>
      </div>
    )
  }

  return (
    <div className="app">
      <DepthBg variant="page" reduced={reduced} />
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
              <button type="button" role="tab" aria-label="Pipeline" aria-selected={view === 'graph'} className={view === 'graph' ? 'on' : ''} onClick={() => setView('graph')}><Network size={14} /><span className="lbl"> Pipeline</span></button>
              <button type="button" role="tab" aria-label="Report" aria-selected={view === 'report'} className={view === 'report' ? 'on' : ''} onClick={() => setView('report')}><FileText size={14} /><span className="lbl"> Report</span></button>
            </div>
            {selectedId && (
              player.playing
                ? <button type="button" className="btn small" onClick={player.skip}><SkipForward size={13} /> Skip</button>
                : <button type="button" className="btn small" onClick={() => void select(selectedId)} title={mode === 'live' ? 'Run the pipeline again' : 'Replay the recorded trace'}><Play size={13} /> {mode === 'live' ? 'Re-run' : 'Replay'}</button>
            )}
            {selectedId && mode === 'live' && !player.playing && (
              <button type="button" className="btn small warn" onClick={() => void select(selectedId, source, 'classifier')}
                title="Demo: force the classifier node to fail once on this email, so you can try the Retry button">
                <AlertTriangle size={13} /> Simulate failure
              </button>
            )}
            <span className={`mode-pill m-${mode}`} title={MODE_HINT[mode]}>
              <span className="dot" />
              {MODE_TEXT[mode]}
              <span className="pill-eng" title="Engine that produced the LLM-capable nodes (gemini = LLM, rules = deterministic offline parsers)">{engine} engine</span>
              <Activity size={14} />
            </span>
          </div>
        </header>

        <div className="c-body">
          {view === 'graph' && (
            <div className="transport" role="group" aria-label="Playback">
              <button type="button" className={`btn small tp-main${auto ? ' on' : ''}`} onClick={() => { if (auto && !player.paused) player.pause(); else if (auto) player.resume(); else startAuto() }} aria-pressed={auto && !player.paused} title="Stream through the emails in the list (Space)">
                {auto && !player.paused ? <Pause size={13} /> : <Play size={13} />}
                {auto ? (player.paused ? 'Paused' : 'Streaming inbox') : 'Play inbox'}
              </button>
              {auto && <button type="button" className="btn small ghost" onClick={() => { setAuto(false); player.resume() }} title="Stop auto-play (A)">Stop</button>}
              <div className="seg tp-speed" role="radiogroup" aria-label="Playback speed">
                {SPEEDS.map((sp) => <button key={sp} type="button" role="radio" aria-checked={speed === sp} className={speed === sp ? 'on' : ''} onClick={() => setSpeed(sp)}>{sp}x</button>)}
              </div>
              <button type="button" className="ib" onClick={() => setHelp(true)} aria-label="Keyboard shortcuts" title="Keyboard shortcuts (?)"><Keyboard size={14} /></button>
            </div>
          )}
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
        <EmailList rows={rows} selectedId={selectedId} onSelect={(id) => void select(id)} onVisible={onVisible} reduced={reduced} />
        <FlyPanel
          fly={flyEff}
          gate={gateShown}
          gateState={active ? nodes.gate?.state ?? 'pending' : 'idle'}
          reduced={reduced}
          feedback={fb}
          onResetTaught={simW ? () => { setSimW(null); setFeedback(null) } : undefined}
        />
      </div>

      <Timeline nodes={nodes} active={active} playing={player.playing} result={result} title={title} totalMs={totalMs} />

      <div className="sr-only" aria-live="polite">{result ? `${result.headline ?? ''}` : ''}</div>
      {toast && <div className={`toast ${toast.kind}`} role="status">{toast.text}</div>}
      {help && <HelpOverlay onClose={() => setHelp(false)} />}
    </div>
  )
}
