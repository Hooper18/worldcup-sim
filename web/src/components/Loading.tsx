export function Loading() {
  return <p className="py-12 text-center text-sm text-ink-faint">加载中…</p>
}

export function ErrorMsg({ msg }: { msg: string }) {
  return <p className="py-12 text-center text-sm text-ink-secondary">{msg}</p>
}
