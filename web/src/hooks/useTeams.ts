import { useData } from './useData'
import type { Teams } from '../types/data'

// 全站共享的 teams 字典（模块级缓存，多处调用只 fetch 一次）
export function useTeams(): Teams | null {
  return useData<Teams>('teams').data
}
