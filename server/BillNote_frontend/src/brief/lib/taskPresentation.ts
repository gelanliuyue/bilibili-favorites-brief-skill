import type { BriefTask } from '../types'

export type TaskPresentation =
  | 'hydrating'
  | 'missing'
  | 'result'
  | 'incomplete'
  | 'processing'

export function describeTaskPresentation(
  task: BriefTask | undefined,
  hydrated: boolean,
): TaskPresentation {
  if (!hydrated) return 'hydrating'
  if (!task) return 'missing'
  if (task.status === 'SUCCESS') {
    return task.markdown && task.document ? 'result' : 'incomplete'
  }
  return 'processing'
}
