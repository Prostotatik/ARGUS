import { useCallback, useEffect, useRef, useState } from 'react'
import type { TraceEvent } from '../types'

interface Item { ev: TraceEvent; gap: number }

/**
 * Paces trace events onto the screen. REPLAY: gaps derived from recorded t_ms deltas (clamped so the
 * animation is watchable). LIVE: events are released as they arrive with a small minimum gap.
 * `speed` divides every gap (1x / 2x / 4x playback); `paused` freezes the queue without dropping events.
 */
export function usePlayer(reduced: boolean, speed = 1) {
  const [shown, setShown] = useState<TraceEvent[]>([])
  const [playing, setPlaying] = useState(false)
  const [paused, setPaused] = useState(false)
  const queue = useRef<Item[]>([])
  const timer = useRef<number | null>(null)
  const inflight = useRef<Item | null>(null)
  const closed = useRef(true)
  const reducedRef = useRef(reduced)
  reducedRef.current = reduced
  const speedRef = useRef(speed)
  speedRef.current = speed
  const pausedRef = useRef(false)

  const stopTimer = () => {
    if (timer.current != null) { window.clearTimeout(timer.current); timer.current = null }
  }

  const drain = useCallback(() => {
    if (timer.current != null || pausedRef.current) return
    const item = queue.current.shift()
    if (!item) {
      if (closed.current) setPlaying(false)
      return
    }
    inflight.current = item
    timer.current = window.setTimeout(() => {
      timer.current = null
      inflight.current = null
      setShown((s) => s.concat(item.ev))
      drain()
    }, Math.max(6, item.gap / speedRef.current))
  }, [])

  const gapFor = (ev: TraceEvent, dt: number | null) => {
    if (reducedRef.current) return 12
    const min = ev.state === 'start' ? 45 : 130
    return Math.min(800, Math.max(min, dt ?? 0))
  }

  /** start a fresh run; `keep` retains already-shown events (retry). */
  const begin = useCallback((keep = false) => {
    stopTimer()
    inflight.current = null
    queue.current = []
    closed.current = false
    if (!keep) { pausedRef.current = false; setPaused(false); setShown([]) }
    setPlaying(true)
  }, [])

  const push = useCallback((ev: TraceEvent, recordedDt: number | null = null) => {
    queue.current.push({ ev, gap: gapFor(ev, recordedDt) })
    drain()
  }, [drain])

  const end = useCallback(() => {
    closed.current = true
    if (!queue.current.length && timer.current == null && !pausedRef.current) setPlaying(false)
  }, [])

  /** REPLAY convenience */
  const playAll = useCallback((events: TraceEvent[]) => {
    begin(false)
    let prev = 0
    const sorted = [...events].sort((a, b) => a.seq - b.seq)
    sorted.forEach((ev, i) => {
      const dt = i === 0 ? 260 : ev.t_ms - prev
      prev = ev.t_ms
      queue.current.push({ ev, gap: gapFor(ev, dt) })
    })
    end()
    drain()
  }, [begin, end, drain])

  const skip = useCallback(() => {
    stopTimer()
    const rest = [...(inflight.current ? [inflight.current] : []), ...queue.current].map((i) => i.ev)
    inflight.current = null
    queue.current = []
    if (rest.length) setShown((s) => s.concat(rest))
    if (closed.current) setPlaying(false)
  }, [])

  const reset = useCallback(() => {
    stopTimer()
    inflight.current = null
    queue.current = []
    closed.current = true
    pausedRef.current = false
    setPaused(false)
    setShown([])
    setPlaying(false)
  }, [])

  const pause = useCallback(() => {
    if (pausedRef.current) return
    pausedRef.current = true
    setPaused(true)
    if (timer.current != null && inflight.current) {
      stopTimer()
      queue.current.unshift(inflight.current)
      inflight.current = null
    }
  }, [])

  const resume = useCallback(() => {
    if (!pausedRef.current) return
    pausedRef.current = false
    setPaused(false)
    drain()
  }, [drain])

  useEffect(() => () => stopTimer(), [])

  return { shown, playing, paused, begin, push, end, playAll, skip, reset, pause, resume }
}
