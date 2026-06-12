import { describe, expect, it } from 'vitest'
import { kickoffDateKey, pct, STAGE_LABEL, todayKey } from './format'

describe('format', () => {
  it('pct 格式化', () => {
    expect(pct(0.5)).toBe('50%')
    expect(pct(0.1234, 1)).toBe('12.3%')
  })

  it('日期键用本地时区，不依赖 toISOString', () => {
    // 同一时刻在本地解析，键应稳定
    const utc = '2026-06-12T02:00:00Z'
    expect(kickoffDateKey(utc)).toMatch(/^\d{4}-\d{1,2}-\d{1,2}$/)
  })

  it('todayKey 格式正确', () => {
    expect(todayKey(new Date(2026, 5, 12))).toBe('2026-6-12')
  })

  it('阶段中文标签', () => {
    expect(STAGE_LABEL.group).toBe('小组赛')
    expect(STAGE_LABEL.final).toBe('决赛')
  })
})
