import type { ReactNode } from 'react'

// 极淡 1px 边框 + 大圆角，无阴影（遵循全局设计规范）
export default function Card({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return <div className={`rounded-2xl border border-line bg-white/40 ${className}`}>{children}</div>
}
