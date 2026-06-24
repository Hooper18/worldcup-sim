import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { GLOSSARY, type GlossaryKey } from '../lib/glossary'

// 行内「ⓘ」按钮：点开弹出该术语的大白话解释。点按钮或按 Esc / 点外部关闭。
// 低调样式（极淡描边圆圈 + 小写 i），遵循全局设计规范：不抢注意力。
// 弹层用 portal + fixed 定位：既不被 overflow-x-auto 的表格/卡片裁切，也按视口边缘收口防溢出；
// 触达区用透明 ::before 扩到 ~26px（视觉圈仍 14px），满足触控可达性。
const PANEL_W = 256
const MARGIN = 8

export default function InfoTip({ k, className = '' }: { k: GlossaryKey; className?: string }) {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null)
  const btnRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLSpanElement>(null)
  const panelId = useId()
  const entry = GLOSSARY[k]

  // 开启时按钮位置算弹层落点（视口坐标），并随滚动/缩放重算
  useLayoutEffect(() => {
    if (!open) return
    const place = () => {
      const b = btnRef.current?.getBoundingClientRect()
      if (!b) return
      const vw = window.innerWidth
      const width = Math.min(PANEL_W, vw - 2 * MARGIN)
      const left = Math.max(MARGIN, Math.min(b.left + b.width / 2 - width / 2, vw - MARGIN - width))
      setPos({ top: b.bottom + 6, left, width })
    }
    place()
    window.addEventListener('scroll', place, true)
    window.addEventListener('resize', place)
    return () => {
      window.removeEventListener('scroll', place, true)
      window.removeEventListener('resize', place)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (btnRef.current?.contains(t) || panelRef.current?.contains(t)) return
      setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <span className={`relative inline-flex align-middle ${className}`}>
      <button
        ref={btnRef}
        type="button"
        aria-label={`${entry.term}：是什么？`}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="relative mx-0.5 inline-flex h-3.5 w-3.5 items-center justify-center rounded-full border border-ink-secondary/70 text-[9px] font-medium not-italic leading-none text-ink-secondary transition-colors before:absolute before:-inset-1.5 before:content-[''] hover:border-accent hover:text-accent"
      >
        i
      </button>
      {open &&
        pos &&
        createPortal(
          <span
            ref={panelRef}
            id={panelId}
            role="tooltip"
            style={{ position: 'fixed', top: pos.top, left: pos.left, width: pos.width }}
            className="z-50 block rounded-xl border border-line bg-paper p-3 text-left font-normal shadow-sm"
          >
            <span className="block text-xs font-medium text-ink">{entry.term}</span>
            <span className="mt-1 block text-xs leading-relaxed text-ink-secondary">
              {entry.body}
            </span>
          </span>,
          document.body,
        )}
    </span>
  )
}
