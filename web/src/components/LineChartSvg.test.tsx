import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import LineChartSvg from './LineChartSvg'
import type { Series } from '../lib/chart'

const series: Series[] = [{ label: '阿根廷', color: '#2F6B4F', values: [0.1, 0.2, 0.18] }]
const xLabels = ['1 场', '2 场', '3 场']

describe('LineChartSvg', () => {
  it('渲染坐标轴刻度、x 标签与折线', () => {
    const { container } = render(<LineChartSvg series={series} xLabels={xLabels} />)
    expect(container.querySelector('svg')).toBeTruthy()
    expect(container.querySelectorAll('path')).toHaveLength(1)
    expect(screen.getByText('3 场')).toBeInTheDocument()
    expect(screen.getByText('0%')).toBeInTheDocument()
  })

  it('hover 在该点显示各序列具体数值', () => {
    const { container } = render(<LineChartSvg series={series} xLabels={xLabels} />)
    const svg = container.querySelector('svg')!
    // jsdom 下 getBoundingClientRect 返回 0 宽，伪造布局以驱动 hover 命中坐标
    vi.spyOn(svg, 'getBoundingClientRect').mockReturnValue({
      left: 0,
      top: 0,
      width: 640,
      height: 240,
      right: 640,
      bottom: 240,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    } as DOMRect)
    fireEvent.pointerMove(svg, { clientX: 640, clientY: 120 })
    expect(screen.getByText('18.0%')).toBeInTheDocument() // 最右点 values[2]=0.18
  })
})
