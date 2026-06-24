import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import InfoTip from './InfoTip'
import { GLOSSARY } from '../lib/glossary'

describe('InfoTip', () => {
  it('默认不显示解释，点击 ⓘ 后弹出术语与大白话', () => {
    render(<InfoTip k="elo" />)
    expect(screen.queryByRole('tooltip')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /是什么/ }))
    const tip = screen.getByRole('tooltip')
    expect(tip).toHaveTextContent(GLOSSARY.elo.term)
    expect(tip).toHaveTextContent('国际象棋') // 解释正文里的关键词
  })

  it('再次点击关闭；按 Esc 也关闭', () => {
    render(<InfoTip k="rps" />)
    const btn = screen.getByRole('button', { name: /是什么/ })
    fireEvent.click(btn)
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    fireEvent.click(btn)
    expect(screen.queryByRole('tooltip')).toBeNull()
    fireEvent.click(btn)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('aria-expanded 跟随开合状态', () => {
    render(<InfoTip k="ece" />)
    const btn = screen.getByRole('button', { name: /是什么/ })
    expect(btn).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(btn)
    expect(btn).toHaveAttribute('aria-expanded', 'true')
  })
})
