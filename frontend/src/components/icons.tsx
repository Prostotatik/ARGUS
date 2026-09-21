import {
  Anchor, Brain, Container, Scale, Ship, UserCheck, BellRing, MapPin, Mail, FileText, Network, Activity,
  ShieldCheck, Flag, Cpu,
} from 'lucide-react'
import type { FieldKey } from '../types'

export const FIELD_ICON: Record<FieldKey, typeof Anchor> = {
  shipper: Ship,
  consignee: UserCheck,
  notify_party: BellRing,
  port_of_loading: Anchor,
  port_of_discharge: MapPin,
  container_count: Container,
  gross_weight_kg: Scale,
}

export const NODE_ICON = {
  inbox: Mail,
  classifier: Brain,
  aggregator: Network,
  report: FileText,
  gate: ShieldCheck,
  pulse: Activity,
  flag: Flag,
  engine: Cpu,
}

/** Asteris mark: asterisk-like star (reference logo) */
export function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true" style={{ filter: 'drop-shadow(0 0 5px rgba(140, 180, 255, 0.55))' }}>
      <defs>
        <linearGradient id="asteris-lg" gradientUnits="userSpaceOnUse" x1="6" y1="4" x2="34" y2="36">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="1" stopColor="#8fb4ff" />
        </linearGradient>
      </defs>
      <g stroke="url(#asteris-lg)" strokeWidth="3.2" strokeLinecap="round" fill="none">
        <path d="M20 4.5v31" />
        <path d="M6.6 12.2l26.8 15.6" />
        <path d="M33.4 12.2L6.6 27.8" />
      </g>
      <circle cx="20" cy="20" r="2.8" fill="#fff" />
    </svg>
  )
}
