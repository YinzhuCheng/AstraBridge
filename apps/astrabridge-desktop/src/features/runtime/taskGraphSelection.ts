import type { TaskGraphDefinition } from "../../types";

export function hasRenderableTaskGraphStructure(
  graph: TaskGraphDefinition | null | undefined,
): graph is TaskGraphDefinition {
  return Boolean(
    graph &&
      Array.isArray(graph.nodes) &&
      Array.isArray(graph.edges),
  );
}

type ResolvePreferredTaskGraphIdArgs = {
  currentGraphId?: string | null;
  persistedGraphId?: string | null;
  routeGraphId?: string | null;
  latestGraphId?: string | null;
  fallbackGraphId?: string | null;
  taskGraphIds?: string[];
  taskGraphRouteUnavailable: boolean;
  firstHydrationForTask: boolean;
};

type ResolveTaskGraphRouteUnavailableArgs = {
  templatesError: boolean;
  taskGraphErrorMessage?: string | null;
  routeGraph?: TaskGraphDefinition | null;
  persistedGraphs?: Array<TaskGraphDefinition | null | undefined> | null;
  fallbackGraph?: TaskGraphDefinition | null;
};

export function resolveTaskGraphRouteUnavailable({
  templatesError,
  taskGraphErrorMessage,
  routeGraph,
  persistedGraphs,
  fallbackGraph,
}: ResolveTaskGraphRouteUnavailableArgs) {
  const hasRenderableGraphSource =
    hasRenderableTaskGraphStructure(routeGraph) ||
    (persistedGraphs ?? []).some((graph) => hasRenderableTaskGraphStructure(graph)) ||
    hasRenderableTaskGraphStructure(fallbackGraph);
  if (templatesError) {
    return !hasRenderableGraphSource;
  }
  const notFound = String(taskGraphErrorMessage || "").includes("Not found");
  if (!notFound) {
    return false;
  }
  if (hasRenderableGraphSource) {
    return false;
  }
  return true;
}

export function resolvePreferredTaskGraphId({
  currentGraphId,
  persistedGraphId,
  routeGraphId,
  latestGraphId,
  fallbackGraphId,
  taskGraphIds = [],
  taskGraphRouteUnavailable,
  firstHydrationForTask,
}: ResolvePreferredTaskGraphIdArgs): string | null {
  const current = currentGraphId?.trim() || null;
  const persisted = persistedGraphId?.trim() || null;
  const route = routeGraphId?.trim() || null;
  const latest = latestGraphId?.trim() || null;
  const fallback = fallbackGraphId?.trim() || null;
  const knownTaskGraphIds = taskGraphIds.filter(Boolean);

  if (taskGraphRouteUnavailable) {
    const fallbackLatest = fallback ?? latest ?? null;
    if (!current) {
      if (persisted && persisted === fallback) return persisted;
      return fallbackLatest;
    }
    return current === fallback ? current : fallbackLatest;
  }

  if (firstHydrationForTask && route) {
    return route;
  }
  if (firstHydrationForTask) {
    return route ?? latest ?? fallback ?? persisted ?? null;
  }

  if (!current) {
    if (persisted && knownTaskGraphIds.includes(persisted)) {
      return persisted;
    }
    if (persisted && persisted === fallback) {
      return persisted;
    }
    return route ?? latest ?? fallback ?? null;
  }

  if (current === fallback) {
    return current;
  }
  if (knownTaskGraphIds.includes(current)) {
    return current;
  }
  if (route && current === route) {
    return current;
  }
  return route ?? latest ?? fallback ?? null;
}
