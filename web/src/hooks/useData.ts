import { useEffect, useState } from 'react'

// 模块级缓存：同一文件只 fetch 一次
const cache = new Map<string, unknown>()
const inflight = new Map<string, Promise<unknown>>()

async function load<T>(name: string): Promise<T> {
  if (cache.has(name)) return cache.get(name) as T
  if (!inflight.has(name)) {
    const p = fetch(`/data/${name}.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`加载 ${name} 失败：${r.status}`)
        return r.json()
      })
      .then((j) => {
        cache.set(name, j)
        inflight.delete(name)
        return j
      })
      .catch((e) => {
        // 失败也要清理 inflight，否则该 key 永久卡在 rejected promise，瞬时网络抖动后再也不会重试
        inflight.delete(name)
        throw e
      })
    inflight.set(name, p)
  }
  return inflight.get(name) as Promise<T>
}

interface DataState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

export function useData<T>(name: string): DataState<T> {
  const [state, setState] = useState<DataState<T>>({ data: null, loading: true, error: null })
  useEffect(() => {
    let alive = true
    load<T>(name)
      .then((data) => alive && setState({ data, loading: false, error: null }))
      .catch(
        (e) => alive && setState({ data: null, loading: false, error: String(e.message ?? e) }),
      )
    return () => {
      alive = false
    }
  }, [name])
  return state
}
