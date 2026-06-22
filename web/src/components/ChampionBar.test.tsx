import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ChampionBar from './ChampionBar'

describe('ChampionBar', () => {
  it('按队渲染夺冠概率（无 teams 字典时回退到 code）', () => {
    render(
      <ChampionBar
        data={[
          { code: 'ARG', p: 0.178 },
          { code: 'ESP', p: 0.165 },
        ]}
      />,
    )
    expect(screen.getByText('ARG')).toBeInTheDocument()
    expect(screen.getByText('17.8%')).toBeInTheDocument()
    expect(screen.getByText('16.5%')).toBeInTheDocument()
  })

  it('有 bootstrap 区间时标注 95% 区间', () => {
    render(<ChampionBar data={[{ code: 'ARG', p: 0.178 }]} ci={{ ARG: [0.09, 0.18, 0.24] }} />)
    expect(screen.getByText(/9%.*24%/)).toBeInTheDocument()
  })
})
