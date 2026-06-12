import { flagUrl } from '../lib/flags'

interface Props {
  code: string | null | undefined
  className?: string
}

// 国旗图片（flagcdn），替代 emoji——Windows 不渲染 emoji 国旗。
// 默认高度 14px（与 14px 正文对齐），4:3 比例，极淡描边让浅色旗（如日本）有边界。
export default function Flag({ code, className = '' }: Props) {
  const url = flagUrl(code)
  if (!url) return <span className={`inline-block ${className}`} aria-hidden />
  return (
    <img
      src={url}
      alt=""
      aria-hidden
      loading="lazy"
      className={`inline-block h-3.5 w-[18px] shrink-0 rounded-[2px] object-cover ring-1 ring-black/5 ${className}`}
    />
  )
}
