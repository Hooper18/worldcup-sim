// 概率演变快照去重。
// cron 按"每次运行"追加快照，所以早期同一 matches_played 会有多条（开赛日重跑多次），
// 且场数间隔不规则。按 matches_played 去重（保留每个场数的最新一条），
// 得到一条随"已赛场数"单调推进的横轴，更贴合"每打一场"的语义。

import type { Evolution } from '../types/data'

interface DedupedEvolution {
  keepIdx: number[] // 保留的快照下标（升序，对应单调递增的 matches_played）
  matchesPlayed: number[] // 每个保留点的已赛场数
  xLabels: string[] // x 轴标签，如 "12 场"
}

export function dedupeEvolution(evo: Evolution): DedupedEvolution {
  const lastByMp = new Map<number, number>()
  evo.snapshots.forEach((s, i) => lastByMp.set(s.matches_played, i))
  const keepIdx = [...lastByMp.values()].sort((a, b) => a - b)
  const matchesPlayed = keepIdx.map((i) => evo.snapshots[i].matches_played)
  const xLabels = matchesPlayed.map((mp) => `${mp} 场`)
  return { keepIdx, matchesPlayed, xLabels }
}

// 按保留下标抽取某队某指标的序列
export function pickSeries(arr: number[] | undefined, keepIdx: number[]): number[] {
  if (!arr) return []
  return keepIdx.map((i) => arr[i] ?? 0)
}
