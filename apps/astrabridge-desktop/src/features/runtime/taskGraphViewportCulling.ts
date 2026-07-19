import type {
  TaskGraphDefinition,
  TaskGraphNodePosition,
} from "../../types";

const NODE_CARD_WIDTH = 152;
const NODE_CARD_HEIGHT = 60;
const NODE_EDGE_ANCHOR_X = NODE_CARD_WIDTH / 2;
const NODE_EDGE_ANCHOR_Y = NODE_CARD_HEIGHT / 2;
const EDGE_CHIP_HALF_WIDTH = 84;
const EDGE_CHIP_HALF_HEIGHT = 24;
const DEFAULT_VIEWPORT_OVERSCAN = 220;

export type TaskGraphCanvasViewportSnapshot = {
  scrollLeft: number;
  scrollTop: number;
  clientWidth: number;
  clientHeight: number;
};

export type TaskGraphStageViewport = {
  left: number;
  top: number;
  right: number;
  bottom: number;
};

type TaskGraphStageRect = TaskGraphStageViewport;

type VisibleTaskGraphElementsOptions = {
  selectedNodeId?: string | null;
  selectedEdgeId?: string | null;
  edgeCreateSourceId?: string | null;
  draggedNodeId?: string | null;
  hoveredEdgeId?: string | null;
  highlightedTarget?:
    | { kind: "node"; id: string }
    | { kind: "edge"; id: string }
    | null;
};

export type VisibleTaskGraphElements = {
  visibleNodeIds: Set<string>;
  visibleEdgeIds: Set<string>;
};

function clampPositive(value: number, fallback = 0) {
  if (!Number.isFinite(value)) return Math.max(0, fallback);
  return Math.max(0, value);
}

function rectIntersectsViewport(
  rect: TaskGraphStageRect,
  viewport: TaskGraphStageViewport,
) {
  return (
    rect.left <= viewport.right &&
    rect.right >= viewport.left &&
    rect.top <= viewport.bottom &&
    rect.bottom >= viewport.top
  );
}

function nodeRect(position: TaskGraphNodePosition): TaskGraphStageRect {
  return {
    left: position.x,
    top: position.y,
    right: position.x + NODE_CARD_WIDTH,
    bottom: position.y + NODE_CARD_HEIGHT,
  };
}

function edgeRect(
  fromPosition: TaskGraphNodePosition,
  toPosition: TaskGraphNodePosition,
): TaskGraphStageRect {
  const x1 = fromPosition.x + NODE_EDGE_ANCHOR_X;
  const y1 = fromPosition.y + NODE_EDGE_ANCHOR_Y;
  const x2 = toPosition.x + NODE_EDGE_ANCHOR_X;
  const y2 = toPosition.y + NODE_EDGE_ANCHOR_Y;
  const midX = Math.round((x1 + x2) / 2);
  const midY = Math.round((y1 + y2) / 2);
  return {
    left: Math.min(x1, x2, midX - EDGE_CHIP_HALF_WIDTH),
    top: Math.min(y1, y2, midY - EDGE_CHIP_HALF_HEIGHT),
    right: Math.max(x1, x2, midX + EDGE_CHIP_HALF_WIDTH),
    bottom: Math.max(y1, y2, midY + EDGE_CHIP_HALF_HEIGHT),
  };
}

export function resolveTaskGraphStageViewport(
  snapshot: TaskGraphCanvasViewportSnapshot,
  canvasScale: number,
  stageWidth: number,
  stageHeight: number,
  overscan = DEFAULT_VIEWPORT_OVERSCAN,
): TaskGraphStageViewport {
  const safeStageWidth = clampPositive(stageWidth);
  const safeStageHeight = clampPositive(stageHeight);
  const safeScale = canvasScale > 0 ? canvasScale : 1;
  const safeClientWidth = clampPositive(snapshot.clientWidth);
  const safeClientHeight = clampPositive(snapshot.clientHeight);
  if (safeClientWidth === 0 || safeClientHeight === 0) {
    return {
      left: 0,
      top: 0,
      right: safeStageWidth,
      bottom: safeStageHeight,
    };
  }
  const left = Math.max(0, snapshot.scrollLeft / safeScale - overscan);
  const top = Math.max(0, snapshot.scrollTop / safeScale - overscan);
  const right = Math.min(
    safeStageWidth,
    (snapshot.scrollLeft + safeClientWidth) / safeScale + overscan,
  );
  const bottom = Math.min(
    safeStageHeight,
    (snapshot.scrollTop + safeClientHeight) / safeScale + overscan,
  );
  return { left, top, right, bottom };
}

export function collectVisibleTaskGraphElements(
  graph: TaskGraphDefinition | null,
  previewPositions: Record<string, TaskGraphNodePosition>,
  viewport: TaskGraphStageViewport,
  options: VisibleTaskGraphElementsOptions = {},
): VisibleTaskGraphElements {
  const visibleNodeIds = new Set<string>();
  const visibleEdgeIds = new Set<string>();
  if (!graph) {
    return { visibleNodeIds, visibleEdgeIds };
  }

  const forcedNodeIds = new Set<string>();
  const forcedEdgeIds = new Set<string>();
  for (const candidate of [
    options.selectedNodeId,
    options.edgeCreateSourceId,
    options.draggedNodeId,
  ]) {
    const normalized = String(candidate || "").trim();
    if (normalized) forcedNodeIds.add(normalized);
  }
  if (options.highlightedTarget?.kind === "node") {
    forcedNodeIds.add(options.highlightedTarget.id);
  }
  for (const candidate of [options.selectedEdgeId, options.hoveredEdgeId]) {
    const normalized = String(candidate || "").trim();
    if (normalized) forcedEdgeIds.add(normalized);
  }
  if (options.highlightedTarget?.kind === "edge") {
    forcedEdgeIds.add(options.highlightedTarget.id);
  }

  const nodePositions = new Map<string, TaskGraphNodePosition>();
  for (const node of graph.nodes) {
    const position = previewPositions[node.node_id] ?? node.position;
    nodePositions.set(node.node_id, position);
    if (
      forcedNodeIds.has(node.node_id) ||
      rectIntersectsViewport(nodeRect(position), viewport)
    ) {
      visibleNodeIds.add(node.node_id);
    }
  }

  for (const edge of graph.edges) {
    if (forcedEdgeIds.has(edge.edge_id)) {
      visibleEdgeIds.add(edge.edge_id);
      forcedNodeIds.add(edge.from_node_id);
      forcedNodeIds.add(edge.to_node_id);
    }
  }

  for (const forcedNodeId of forcedNodeIds) {
    if (nodePositions.has(forcedNodeId)) {
      visibleNodeIds.add(forcedNodeId);
    }
  }

  for (const edge of graph.edges) {
    const fromPosition = nodePositions.get(edge.from_node_id);
    const toPosition = nodePositions.get(edge.to_node_id);
    if (!fromPosition || !toPosition) continue;
    if (
      forcedEdgeIds.has(edge.edge_id) ||
      visibleNodeIds.has(edge.from_node_id) ||
      visibleNodeIds.has(edge.to_node_id) ||
      rectIntersectsViewport(edgeRect(fromPosition, toPosition), viewport)
    ) {
      visibleEdgeIds.add(edge.edge_id);
    }
  }

  return { visibleNodeIds, visibleEdgeIds };
}
