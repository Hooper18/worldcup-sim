// M1 待实现页面的占位（概率演变、模型说明、单场详情）
export default function Placeholder({ title }: { title: string }) {
  return (
    <div className="py-16 text-center">
      <h1 className="text-lg font-medium">{title}</h1>
      <p className="mt-2 text-sm text-ink-faint">该页面即将上线</p>
    </div>
  )
}
