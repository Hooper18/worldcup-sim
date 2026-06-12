import { useTeams } from '../hooks/useTeams'

interface Props {
  code: string | null | undefined
  size?: 'sm' | 'md'
  showFlag?: boolean
  className?: string
}

// 旗帜 + 中文队名。code 为 null（淘汰赛未定槽位）时显示占位。
export default function TeamLabel({ code, size = 'md', showFlag = true, className = '' }: Props) {
  const teams = useTeams()
  if (!code) return <span className="text-ink-faint">待定</span>
  const t = teams?.[code]
  const text = size === 'sm' ? 'text-sm' : 'text-base'
  return (
    <span className={`inline-flex items-center gap-1.5 ${text} ${className}`}>
      {showFlag && <span aria-hidden>{t?.flag ?? '🏳️'}</span>}
      <span>{t?.name_zh ?? code}</span>
    </span>
  )
}
