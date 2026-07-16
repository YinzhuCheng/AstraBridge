export type ComposerWorkflowMode = "default" | "goal" | "plan";

export function shouldShowGoalDock({
  workflowMode,
  hasPlan,
  hasProposedPlan,
}: {
  workflowMode: ComposerWorkflowMode;
  hasPlan: boolean;
  hasProposedPlan: boolean;
}) {
  if (workflowMode === "goal") return true;
  return workflowMode === "plan" && (hasPlan || hasProposedPlan);
}
