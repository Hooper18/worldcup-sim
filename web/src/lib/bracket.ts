// 淘汰赛对阵位描述：把赛程里的占位符（小组排名 / 上一轮胜负来源）翻成中文。
// 数据来自 knockout.json 的 bracket：r32 用 home_slot/away_slot（如 "2A"、"3ABCDF"），
// 其后各轮用 home_src/away_src（如 "W74"、"L101"）。

import type { Knockout } from '../types/data'

const RANK: Record<string, string> = { '1': '头名', '2': '第 2', '3': '第 3' }

function slotLabel(token: string): string {
  const r = token[0]
  const rest = token.slice(1)
  // "3ABCDF" = 8 个最佳第三名之一，候选组 A/B/C/D/F
  if (r === '3' && rest.length > 1) return `小组第 3（${rest.split('').join('/')}）`
  return `${rest} 组${RANK[r] ?? r}`
}

function srcLabel(s: string): string {
  return `M${s.slice(1)} ${s[0] === 'W' ? '胜者' : '负者'}`
}

// 取淘汰赛某一侧的对阵位描述（home / away）
export function koSide(bracket: Knockout['bracket'], id: number, side: 'home' | 'away'): string {
  const b = bracket[String(id)]
  if (!b) return '待定'
  const slot = side === 'home' ? b.home_slot : b.away_slot
  if (slot) return slotLabel(slot)
  const src = side === 'home' ? b.home_src : b.away_src
  if (src) return srcLabel(src)
  return '待定'
}

// ---------------------------------------------------------------------------
// 对阵树列顺序：按 bracket 的 home_src/away_src 从决赛中序遍历，让每个父场次恰好
// 夹在喂给它的两场子场次中间（修「列按 id 顺序排、上下游对不齐」的错位）。
// ---------------------------------------------------------------------------

type KoColumn = { stage: string; label: string; ids: number[] }

function range(a: number, b: number): number[] {
  return Array.from({ length: b - a + 1 }, (_, i) => a + i)
}

// id 缺失/不完整时回退到此静态顺序，保证健壮（如 e2e stub 的残缺 bracket）
const STATIC_KO_COLUMNS: KoColumn[] = [
  { stage: 'r32', label: '32 强', ids: range(73, 88) },
  { stage: 'r16', label: '16 强', ids: range(89, 96) },
  { stage: 'qf', label: '8 强', ids: range(97, 100) },
  { stage: 'sf', label: '半决赛', ids: [101, 102] },
  { stage: 'final', label: '决赛', ids: [104] },
]
const KO_EXPECTED: Record<string, number> = { r32: 16, r16: 8, qf: 4, sf: 2, final: 1 }

function koStageOf(id: number): string | null {
  if (id >= 73 && id <= 88) return 'r32'
  if (id >= 89 && id <= 96) return 'r16'
  if (id >= 97 && id <= 100) return 'qf'
  if (id === 101 || id === 102) return 'sf'
  if (id === 104) return 'final'
  return null // 季军赛 103 不进主对阵树
}

function koFeeders(bracket: Knockout['bracket'], id: number): number[] {
  const b = bracket[String(id)]
  if (!b) return []
  return [b.home_src, b.away_src]
    .filter((s): s is string => !!s)
    .map((s) => Number(s.slice(1))) // "W74" → 74, "L101" → 101
    .filter((n) => Number.isFinite(n))
}

export function bracketColumns(bracket?: Knockout['bracket']): KoColumn[] {
  if (!bracket || !bracket['104']) return STATIC_KO_COLUMNS
  const buckets = new Map<string, number[]>()
  const seen = new Set<number>()
  const visit = (id: number) => {
    if (seen.has(id)) return // 防御异常结构里的环
    seen.add(id)
    const kids = koFeeders(bracket, id)
    if (kids.length === 2) visit(kids[0]) // 中序：先左子树
    const st = koStageOf(id)
    if (st) buckets.set(st, [...(buckets.get(st) ?? []), id])
    if (kids.length === 2) visit(kids[1]) // 再右子树
  }
  visit(104)
  const cols = STATIC_KO_COLUMNS.map((c) => ({ ...c, ids: buckets.get(c.stage) ?? [] }))
  // 任一轮数目不符（结构异常/残缺）就整体回退，避免半成品错位
  return cols.some((c) => c.ids.length !== KO_EXPECTED[c.stage]) ? STATIC_KO_COLUMNS : cols
}
