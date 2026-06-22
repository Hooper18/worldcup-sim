import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ScoreHeatGrid from './ScoreHeatGrid'

const matrix = Array.from({ length: 6 }, () => Array.from({ length: 6 }, () => 1 / 36))

describe('ScoreHeatGrid', () => {
  it('渲染 6x6 比分格与坐标说明', () => {
    render(<ScoreHeatGrid matrix={matrix} homeCode="ARG" awayCode="FRA" />)
    expect(screen.getByText('0:0')).toBeInTheDocument()
    expect(screen.getByText('5:5')).toBeInTheDocument()
    expect(screen.getByText(/客队进球/)).toBeInTheDocument()
  })
})
