import { useEffect, useRef } from 'react'

/**
 * Subtle depth: layered star-dust that drifts slowly (CSS, transform only) and shifts with the pointer at a
 * different rate per layer (parallax). One shared pointer listener + one rAF that stops once the layers settle.
 * Nothing here animates a layout property.
 */
interface LayerReg { el: HTMLElement; amp: number }
const layers = new Set<LayerReg>()
let tx = 0, ty = 0, cx = 0, cy = 0, raf = 0, bound = false

function loop() {
  cx += (tx - cx) * 0.07
  cy += (ty - cy) * 0.07
  layers.forEach((l) => { l.el.style.transform = `translate3d(${(-cx * l.amp).toFixed(2)}px, ${(-cy * l.amp * 0.8).toFixed(2)}px, 0)` })
  raf = Math.abs(tx - cx) + Math.abs(ty - cy) > 0.002 ? requestAnimationFrame(loop) : 0
}
function onMove(e: PointerEvent) {
  tx = (e.clientX / window.innerWidth - 0.5) * 2
  ty = (e.clientY / window.innerHeight - 0.5) * 2
  if (!raf) raf = requestAnimationFrame(loop)
}
function register(l: LayerReg) {
  layers.add(l)
  if (!bound) { window.addEventListener('pointermove', onMove, { passive: true }); bound = true }
  return () => {
    layers.delete(l)
    if (!layers.size && bound) { window.removeEventListener('pointermove', onMove); bound = false; if (raf) cancelAnimationFrame(raf); raf = 0 }
  }
}

function Layer({ cls, amp, reduced }: { cls: string; amp: number; reduced: boolean }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (reduced || !ref.current) return
    return register({ el: ref.current, amp })
  }, [amp, reduced])
  return <div className={`dust-wrap ${cls}`}><div ref={ref} className="dust-l" /></div>
}

/** variant "page": fixed behind everything (visible in the gutters and through the glass panels); "panel": inside the graph */
export default function DepthBg({ variant, reduced }: { variant: 'page' | 'panel'; reduced: boolean }) {
  return (
    <div className={`dust dust-${variant}`} aria-hidden="true">
      {variant === 'page' && <><div className="orb o1" /><div className="orb o2" /></>}
      <Layer cls="w1" amp={variant === 'page' ? 5 : 7} reduced={reduced} />
      <Layer cls="w2" amp={variant === 'page' ? 11 : 15} reduced={reduced} />
      <Layer cls="w3" amp={variant === 'page' ? 20 : 26} reduced={reduced} />
    </div>
  )
}
