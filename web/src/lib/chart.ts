// 折线图共享类型与配色（与组件分离，便于 Vite fast-refresh 且可跨组件复用）。

export interface Series {
  label: string
  color: string
  values: number[]
}

const PALETTE = ['#2F6B4F', '#B5651D', '#3A5A8C', '#7A4E8C', '#8C5A3A', '#4A7A6A']

export const seriesColor = (i: number): string => PALETTE[i % PALETTE.length]
