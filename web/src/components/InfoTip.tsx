import { useEffect, useId, useRef, useState } from 'react'
import { GLOSSARY, type GlossaryKey } from '../lib/glossary'

// 行内「ⓘ」按钮：点开弹出该术语的大白话解释。点按钮或按 Esc / 点外部关闭。
// 低调样式（极淡描边圆圈 + 小写 i），遵循全局设计规范：不抢注意力。
export default function InfoTip({ k, className = '' }: { k: GlossaryKey; className?: string }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)
  const panelId = useId()
  const entry = GLOSSARY[k]

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
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
    <span ref={ref} className={`relative inline-flex align-middle ${className}`}>
      <button
        type="button"
        aria-label={`${entry.term}：是什么？`}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="mx-0.5 inline-flex h-3.5 w-3.5 items-center justify-center rounded-full border border-ink-faint/60 text-[9px] font-medium not-italic leading-none text-ink-faint transition-colors hover:border-accent hover:text-accent"
      >
        i
      </button>
      {open && (
        <span
          id={panelId}
          role="tooltip"
          className="absolute left-1/2 top-full z-50 mt-1.5 block w-64 max-w-[78vw] -translate-x-1/2 rounded-xl border border-line bg-paper p-3 text-left font-normal shadow-sm"
        >
          <span className="block text-xs font-medium text-ink">{entry.term}</span>
          <span className="mt-1 block text-xs leading-relaxed text-ink-secondary">
            {entry.body}
          </span>
        </span>
      )}
    </span>
  )
}
