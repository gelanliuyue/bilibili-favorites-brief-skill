import { get, set, del } from 'idb-keyval'
import { createStore } from 'zustand/vanilla'
import {
  createJSONStorage,
  persist,
  type StateStorage,
} from 'zustand/middleware'
import type {
  BriefTask,
  BriefTaskStatusUpdate,
} from '../types'

export interface BriefStoreState {
  tasks: BriefTask[]
  currentTaskId: string | null
  hydrated: boolean
  markHydrated: () => void
  addTask: (task: BriefTask) => void
  setCurrentTask: (taskId: string | null) => void
  applyTaskStatus: (taskId: string, update: BriefTaskStatusUpdate) => void
  removeTask: (taskId: string) => void
  clearTasks: () => void
}

const idbStateStorage: StateStorage = {
  getItem: (name) => get<string>(name).then((value) => value ?? null),
  setItem: (name, value) => set(name, value),
  removeItem: (name) => del(name),
}

export function createBriefStore(
  stateStorage: StateStorage = idbStateStorage,
  storageName = 'bili-brief-tasks',
) {
  return createStore<BriefStoreState>()(
    persist(
      (setState) => ({
        tasks: [],
        currentTaskId: null,
        hydrated: false,

        markHydrated: () => setState({ hydrated: true }),

        addTask: (task) =>
          setState((state) => ({
            tasks: [task, ...state.tasks.filter((item) => item.id !== task.id)],
            currentTaskId: task.id,
          })),

        setCurrentTask: (taskId) => setState({ currentTaskId: taskId }),

        applyTaskStatus: (taskId, update) =>
          setState((state) => ({
            tasks: state.tasks.map((task) => {
              if (task.id !== taskId) return task
              return {
                ...task,
                ...update,
                message: update.message ?? task.message,
                updatedAt: new Date().toISOString(),
              }
            }),
          })),

        removeTask: (taskId) =>
          setState((state) => ({
            tasks: state.tasks.filter((task) => task.id !== taskId),
            currentTaskId:
              state.currentTaskId === taskId ? null : state.currentTaskId,
          })),

        clearTasks: () => setState({ tasks: [], currentTaskId: null }),
      }),
      {
        name: storageName,
        storage: createJSONStorage(() => stateStorage),
        partialize: (state) => ({
          tasks: state.tasks,
          currentTaskId: state.currentTaskId,
        }),
        onRehydrateStorage: () => (state) => {
          state?.markHydrated()
        },
      },
    ),
  )
}

export const briefStore = createBriefStore()
