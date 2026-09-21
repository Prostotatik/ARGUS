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
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden="true">
      <defs>
        <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#dbe7ff" />
          <stop offset="1" stopColor="#7aa7ff" />
        </linearGradient>
      </defs>
      <g stroke="url(#lg)" strokeWidth="3.4" strokeLinecap="round" fill="none">
        <path d="M20 5v30" />
        <path d="M7 12.5l26 15" />
        <path d="M33 12.5l-26 15" />
      </g>
      <circle cx="20" cy="20" r="2.6" fill="#eaf1ff" />
    </svg>
  )
}
