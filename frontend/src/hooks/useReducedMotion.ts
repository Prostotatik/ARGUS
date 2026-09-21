import { useEffect, useState } from 'react'

/** true when the OS asks for reduced motion. */
export function useReducedMotion(): boolean {
  const q = '(prefers-reduced-motion: reduce)'
  const [r, setR] = useState(() => typeof matchMedia === 'function' && matchMedia(q).matches)
  useEffect(() => {
    if (typeof matchMedia !== 'function') return
    const m = matchMedia(q)
    const on = () => setR(m.matches)
    m.addEventListener('change', on)
    return () => m.removeEventListener('change', on)
  }, [])
  return r
}
