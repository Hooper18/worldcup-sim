import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import CalibrationSvg from './CalibrationSvg'

describe('CalibrationSvg', () => {
  it('渲染坐标轴标签与每个校准点', () => {
    const { container } = render(
      <CalibrationSvg
        points={[
          [0.1, 0.09, 50],
          [0.5, 0.52, 30],
          [0.8, 0.78, 20],
        ]}
      />,
    )
    expect(screen.getByText('预测概率')).toBeInTheDocument()
    expect(screen.getByText('实际频率')).toBeInTheDocument()
    expect(container.querySelectorAll('circle')).toHaveLength(3)
  })
})
