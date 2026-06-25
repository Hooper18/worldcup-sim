import type { Knockout } from '../types/data'

// 按夺冠概率降序取前 n 队（多页复用：仪表盘 Top 榜、概率演变默认选队、赛程走势）。
export function topChampions(teams: Knockout['teams'], n: number): { code: string; p: number }[] {
  return Object.entries(teams)
    .map(([code, t]) => ({ code, p: t.p_champion }))
    .sort((a, b) => b.p - a.p)
    .slice(0, n)
}
