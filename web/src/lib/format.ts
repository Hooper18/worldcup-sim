// 展示格式化工具。日期一律按本地时区显示，绝不用 toISOString 切日期（UTC 偏移坑）。

export function pct(p: number, digits = 0): string {
  return `${(p * 100).toFixed(digits)}%`
}

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

export function formatKickoff(utc: string): string {
  const d = new Date(utc)
  const m = d.getMonth() + 1
  const day = d.getDate()
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${m}月${day}日 ${WEEKDAYS[d.getDay()]} ${hh}:${mm}`
}

export function kickoffDateKey(utc: string): string {
  // 本地年月日键（用于"今天/明天"分组），避免 toISOString 的 UTC 偏移
  const d = new Date(utc)
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`
}

export function formatDay(utc: string): string {
  // 仅日期（本地时区），用于赛程按日分组的标题
  const d = new Date(utc)
  return `${d.getMonth() + 1}月${d.getDate()}日 ${WEEKDAYS[d.getDay()]}`
}

export function formatTime(utc: string): string {
  const d = new Date(utc)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export function todayKey(now = new Date()): string {
  return `${now.getFullYear()}-${now.getMonth() + 1}-${now.getDate()}`
}

export const STAGE_LABEL: Record<string, string> = {
  group: '小组赛',
  r32: '32 强',
  r16: '16 强',
  qf: '8 强',
  sf: '半决赛',
  third: '季军赛',
  final: '决赛',
}

export const AFTER_LABEL: Record<string, string> = {
  FT: '',
  AET: '加时',
  PEN: '点球',
}
