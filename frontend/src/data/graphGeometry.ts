import { FIELD_KEYS, type FieldKey } from '../types'
import { FIELD_COLOR, type NodeInfo } from './graphState'

export const W = 940
export const H = 600
export const CY = 300
export const PILL_W = 214
export const PILL_H = 58
export const PILL_X = 470
export const PILL_GAP = 74

export const POS = {
  inbox: { x: 74, y: CY, r: 46 },
  classifier: { x: 236, y: CY, r: 52 },
  aggregator: { x: 705, y: CY, r: 52 },
  gate: { x: 797, y: CY, r: 18 },
  report: { x: 873, y: CY, r: 44 },
}
export const pillY = (i: number) => CY + (i - 3) * PILL_GAP
const theta = (i: number) => ((i - 3) / 3) * 0.78

export interface Edge {
  id: string; d: string; color: string; from: string; to: string
  /** field agent this edge belongs to (bead speed follows that agent's real duration) */
  agent?: FieldKey
}

function buildEdges(): Edge[] {
  const e: Edge[] = []
  e.push({ id: 'inbox>classifier', d: `M ${POS.inbox.x + POS.inbox.r} ${CY} L ${POS.classifier.x - POS.classifier.r} ${CY}`, color: '#4d8dff', from: 'inbox', to: 'classifier' })
  FIELD_KEYS.forEach((k, i) => {
    const th = theta(i)
    const sx = POS.classifier.x + POS.classifier.r * Math.cos(th)
    const sy = CY + POS.classifier.r * Math.sin(th)
    const ex = PILL_X - PILL_W / 2
    const ey = pillY(i)
    const c1x = sx + Math.cos(th) * 74
    const c1y = sy + Math.sin(th) * 74
    e.push({ id: `classifier>${k}`, d: `M ${sx.toFixed(1)} ${sy.toFixed(1)} C ${c1x.toFixed(1)} ${c1y.toFixed(1)}, ${ex - 64} ${ey}, ${ex} ${ey}`, color: FIELD_COLOR[k], from: 'classifier', to: `field:${k}`, agent: k })
    const px = PILL_X + PILL_W / 2
    const ax = POS.aggregator.x - POS.aggregator.r * Math.cos(th)
    const ay = CY + POS.aggregator.r * Math.sin(th)
    const c2x = ax - Math.cos(th) * 74
    const c2y = ay + Math.sin(th) * 74
    e.push({ id: `${k}>aggregator`, d: `M ${px} ${ey} C ${px + 64} ${ey}, ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${ax.toFixed(1)} ${ay.toFixed(1)}`, color: FIELD_COLOR[k], from: `field:${k}`, to: 'aggregator', agent: k })
  })
  e.push({ id: 'aggregator>gate', d: `M ${POS.aggregator.x + POS.aggregator.r} ${CY} L ${POS.gate.x - POS.gate.r} ${CY}`, color: '#6ea8ff', from: 'aggregator', to: 'gate' })
  e.push({ id: 'gate>report', d: `M ${POS.gate.x + POS.gate.r} ${CY} L ${POS.report.x - POS.report.r} ${CY}`, color: '#6ea8ff', from: 'gate', to: 'report' })
  return e
}
export const EDGES = buildEdges()

/** classifier -> report bypass (non-comparison emails stop after classifier) */
export const BYPASS_EDGE: Edge = {
  id: 'bypass',
  d: `M ${POS.classifier.x + 18} ${CY - POS.classifier.r + 2} C ${POS.classifier.x + 120} 14, ${POS.report.x - 150} 14, ${POS.report.x - 10} ${CY - POS.report.r + 2}`,
  color: '#6ea8ff', from: 'classifier', to: 'report',
}

export type EdgeMode = 'ambient' | 'flow' | 'done' | 'dim' | 'error'
export function edgeMode(from: NodeInfo | undefined, to: NodeInfo | undefined, active: boolean): EdgeMode {
  if (!active) return 'ambient'
  if (!from || !to) return 'dim'
  if (to.state === 'skipped' || from.state === 'skipped') return 'dim'
  if (from.state === 'error') return 'error'
  if (from.state === 'done' && to.state === 'done') return 'done'
  if (from.state === 'done') return 'flow'
  return 'dim'
}

/**
 * Bead speed multiplier per field agent from REAL durations: fast agents (short duration_ms) get
 * quicker beads than slow ones, relative to the median agent of this run. 1 when unknown.
 */
export function agentSpeed(nodes: Record<string, NodeInfo>): Record<string, number> {
  const ds = FIELD_KEYS.map((k) => nodes[`field:${k}`]?.duration_ms).filter((d): d is number => typeof d === 'number' && d > 0)
  const out: Record<string, number> = {}
  if (ds.length < 2) return out
  const sorted = [...ds].sort((a, b) => a - b)
  const med = sorted[Math.floor(sorted.length / 2)]
  for (const k of FIELD_KEYS) {
    const d = nodes[`field:${k}`]?.duration_ms
    if (typeof d === 'number' && d > 0) out[k] = Math.max(0.6, Math.min(1.9, Math.pow(med / d, 0.8)))
  }
  return out
}
