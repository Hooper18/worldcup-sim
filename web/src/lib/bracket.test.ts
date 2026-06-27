import { describe, it, expect } from 'vitest'
import { bracketColumns } from './bracket'
import type { Knockout } from '../types/data'

// 2026 赛制对阵树的真实上游链（home_src/away_src 的场次号）
const SRC: Record<number, [number, number]> = {
  89: [74, 77],
  90: [73, 75],
  91: [76, 78],
  92: [79, 80],
  93: [83, 84],
  94: [81, 82],
  95: [86, 88],
  96: [85, 87],
  97: [89, 90],
  98: [93, 94],
  99: [91, 92],
  100: [95, 96],
  101: [97, 98],
  102: [99, 100],
  104: [101, 102],
}
const fullBracket = Object.fromEntries(
  Object.entries(SRC).map(([id, [h, a]]) => [id, { home_src: `W${h}`, away_src: `W${a}` }]),
) as Knockout['bracket']

describe('bracketColumns', () => {
  it('按对阵树中序排列，每个父场次恰好夹在其两场上游中间', () => {
    const cols = bracketColumns(fullBracket)
    const by = Object.fromEntries(cols.map((c) => [c.stage, c.ids]))
    expect(by.r32).toEqual([74, 77, 73, 75, 83, 84, 81, 82, 76, 78, 79, 80, 86, 88, 85, 87])
    expect(by.r16).toEqual([89, 90, 93, 94, 91, 92, 95, 96])
    expect(by.qf).toEqual([97, 98, 99, 100])
    expect(by.sf).toEqual([101, 102])
    expect(by.final).toEqual([104])
    // 关键不变量：R16 第 i 场的两场 R32 上游就在 R32 列的第 2i、2i+1 位（相邻、对齐）
    by.r16.forEach((id, i) => {
      const [home, away] = SRC[id]
      expect(by.r32[2 * i]).toBe(home)
      expect(by.r32[2 * i + 1]).toBe(away)
    })
  })

  it('bracket 缺失或不完整时回退到静态 id 顺序', () => {
    expect(bracketColumns(undefined)[0].ids).toEqual([
      73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88,
    ])
    const partial = { '73': { home_slot: '2A', away_slot: '2B' } } as Knockout['bracket']
    expect(bracketColumns(partial)[0].ids[0]).toBe(73) // 无 104 → 静态
  })
})
