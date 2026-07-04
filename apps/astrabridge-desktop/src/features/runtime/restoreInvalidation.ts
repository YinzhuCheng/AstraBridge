import type { QueryClient } from "@tanstack/react-query";

export const RESTORE_STATE_INVALIDATION_QUERY_KEYS = [
  ["project"],
  ["project-tasks"],
  ["threads"],
  ["task-conversation"],
  ["thread"],
  ["goal"],
  ["runtime-supervisor"],
  ["project-review-status"],
] as const;

type QueryInvalidator = Pick<QueryClient, "invalidateQueries">;

export function invalidateRestoreStateQueries(queryClient: QueryInvalidator) {
  for (const queryKey of RESTORE_STATE_INVALIDATION_QUERY_KEYS) {
    void queryClient.invalidateQueries({ queryKey: [...queryKey] });
  }
}
