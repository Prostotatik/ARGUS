import { useLayoutEffect, useRef } from 'react'
import { useReducedMotion } from '../hooks/useReducedMotion'

interface Props {
  value: number
  decimals?: number
  ms?: number
  suffix?: string
  /** locale grouping for big integers */
  group?: boolean
}

/**
 * Tweens the displayed number from its previous value to `value` with one rAF loop that writes
 * straight to the DOM node (no React re-render per frame). The final frame always shows the exact value.
 */
export default function CountUp({ value, decimals = 0, ms = 900, suffix = '', group = false }: Props) {
  const ref = useRef<HTMLSpanElement>(null)
  const shown = useRef<number | null>(null)
  const reduced = useReducedMotion()
  const fmt = (v: number) => (group ? v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : v.toFixed(decimals)) + suffix

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const from = shown.current ?? 0
    if (shown.current == null) el.textContent = fmt(0)
    if (reduced || from === value || ms <= 0) {
      shown.current = value
      el.textContent = fmt(value)
      return
    }
    let raf = 0
    const t0 = performance.now()
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / ms)
      const e = 1 - Math.pow(1 - p, 3)
      const v = from + (value - from) * e
      shown.current = v
      el.textContent = fmt(p >= 1 ? value : v)
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, decimals, ms, reduced])

  return <span ref={ref} />
}
