import { create } from 'zustand'
import type { BotStatus, Post, Trade, Position } from '../api/api'

interface AppState {
  // Data
  posts: Post[]
  trades: Trade[]
  positions: Record<string, Position>
  status: BotStatus | null
  wsConnected: boolean

  // Actions
  addPost: (post: Post) => void
  setTrades: (trades: Trade[]) => void
  setPositions: (positions: Record<string, Position>) => void
  setStatus: (status: BotStatus) => void
  updateStatus: (partial: Partial<BotStatus>) => void
  setWsConnected: (connected: boolean) => void
  setPosts: (posts: Post[]) => void
}

export const useStore = create<AppState>((set) => ({
  posts: [],
  trades: [],
  positions: {},
  status: null,
  wsConnected: false,

  addPost: (post) =>
    set((state) => ({
      posts: [post, ...state.posts].slice(0, 50),
    })),

  setPosts: (posts) => set({ posts }),

  setTrades: (trades) => set({ trades }),

  setPositions: (positions) => set({ positions }),

  setStatus: (status) => set({ status }),

  updateStatus: (partial) =>
    set((state) => ({
      status: state.status ? { ...state.status, ...partial } : (partial as BotStatus),
    })),

  setWsConnected: (wsConnected) => set({ wsConnected }),
}))
