// 淘汰赛对阵位描述：把赛程里的占位符（小组排名 / 上一轮胜负来源）翻成中文。
// 数据来自 knockout.json 的 bracket：r32 用 home_slot/away_slot（如 "2A"、"3ABCDF"），
// 其后各轮用 home_src/away_src（如 "W74"、"L101"）。

import type { Knockout } from '../types/data'

const RANK: Record<string, string> = { '1': '头名', '2': '第 2', '3': '第 3' }

export function slotLabel(token: string): string {
  const r = token[0]
  const rest = token.slice(1)
  // "3ABCDF" = 8 个最佳第三名之一，候选组 A/B/C/D/F
  if (r === '3' && rest.length > 1) return `小组第 3（${rest.split('').join('/')}）`
  return `${rest} 组${RANK[r] ?? r}`
}

export function srcLabel(s: string): string {
  return `M${s.slice(1)} ${s[0] === 'W' ? '胜者' : '负者'}`
}

// 取淘汰赛某一侧的对阵位描述（home / away）
export function koSide(
  bracket: Knockout['bracket'],
  id: number,
  side: 'home' | 'away',
): string {
  const b = bracket[String(id)]
  if (!b) return '待定'
  const slot = side === 'home' ? b.home_slot : b.away_slot
  if (slot) return slotLabel(slot)
  const src = side === 'home' ? b.home_src : b.away_src
  if (src) return srcLabel(src)
  return '待定'
}
