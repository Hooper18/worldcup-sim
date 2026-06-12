import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ProbBar from './ProbBar'

describe('ProbBar', () => {
  it('渲染胜平负百分比', () => {
    render(<ProbBar pHome={0.5} pDraw={0.3} pAway={0.2} />)
    expect(screen.getByText(/主胜 50%/)).toBeInTheDocument()
    expect(screen.getByText(/平 30%/)).toBeInTheDocument()
    expect(screen.getByText(/客胜 20%/)).toBeInTheDocument()
  })

  it('容忍越界/NaN 输入', () => {
    render(<ProbBar pHome={NaN} pDraw={1.5} pAway={-0.2} />)
    // NaN→0%、>1→100%、<0→0%，不抛错
    expect(screen.getByText(/主胜 0%/)).toBeInTheDocument()
    expect(screen.getByText(/平 100%/)).toBeInTheDocument()
    expect(screen.getByText(/客胜 0%/)).toBeInTheDocument()
  })

  it('支持自定义标签', () => {
    render(<ProbBar pHome={0.4} pDraw={0.3} pAway={0.3} labels={['巴西', '法国']} />)
    expect(screen.getByText(/巴西 40%/)).toBeInTheDocument()
    expect(screen.getByText(/法国 30%/)).toBeInTheDocument()
  })
})
