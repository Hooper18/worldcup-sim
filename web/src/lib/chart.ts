// 折线图共享类型与配色（与组件分离，便于 Vite fast-refresh 且可跨组件复用）。

export interface Series {
  label: string
  color: string
  values: number[]
}

// 6 色折线调色板走 CSS 变量（index.css 的 :root/.dark 各一套），暗色模式下用更亮的版本
// 以保证在 #212121 上的对比；var() 在 SVG presentation 属性与内联 style 均可解析。
const PALETTE_N = 6

export const seriesColor = (i: number): string => `var(--chart-${(i % PALETTE_N) + 1})`
