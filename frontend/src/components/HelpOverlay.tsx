import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

const KEYS: { k: string[]; d: string }[] = [
  { k: ['j'], d: 'Next email in the list (respects filter and search)' },
  { k: ['k'], d: 'Previous email' },
  { k: ['Space'], d: 'Play / pause. With nothing running it starts streaming the inbox' },
  { k: ['a'], d: 'Toggle auto-play (streams through the visible emails, throttled)' },
  { k: ['1', '2', '3'], d: 'Playback speed 0.25x / 0.5x / 1x' },
  { k: ['r'], d: 'Replay the selected email' },
  { k: ['g'], d: 'Switch between Pipeline and Report view' },
  { k: ['Esc'], d: 'Close popovers and this panel' },
  { k: ['?'], d: 'Show / hide this help' },
]

export default function HelpOverlay({ onClose }: { onClose: () => void }) {
  const btn = useRef<HTMLButtonElement>(null)
  useEffect(() => { btn.current?.focus() }, [])
  return (
    <div className="help-back" onClick={onClose} role="presentation">
      <div className="help" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" onClick={(e) => e.stopPropagation()}>
        <header>
          <h2>Keyboard shortcuts</h2>
          <button ref={btn} type="button" className="ib" onClick={onClose} aria-label="Close"><X size={15} /></button>
        </header>
        <ul>
          {KEYS.map((r) => (
            <li key={r.d}>
              <span className="keys">{r.k.map((x) => <kbd key={x}>{x}</kbd>)}</span>
              <span>{r.d}</span>
            </li>
          ))}
        </ul>
        <p className="help-note">Hover a node for its trace; hover an input or a Kenyon cell in the fly panel to see its real wiring and weight.</p>
      </div>
    </div>
  )
}
