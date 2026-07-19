import type { RuntimeEvent } from "../../types";

type RuntimeEventBatchPayload = {
  cursor?: number | null;
  events?: RuntimeEvent[] | null;
};

type RuntimeEventFramePayload = {
  cursor?: number | null;
  event?: RuntimeEvent | null;
};

export type RuntimeEventCursorReconciliation = {
  nextCursor: number;
  acceptedEvents: RuntimeEvent[];
};

function normalizeCursor(value: number | null | undefined, fallback = 0) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return Math.max(0, Math.floor(fallback));
  }
  return Math.max(0, Math.floor(value));
}

export function reconcileRuntimeEventBatch(
  currentCursor: number,
  requestedAfter: number,
  payload: RuntimeEventBatchPayload,
): RuntimeEventCursorReconciliation {
  const safeCurrent = normalizeCursor(currentCursor);
  const safeAfter = normalizeCursor(requestedAfter);
  const payloadCursor = normalizeCursor(payload.cursor, safeAfter);
  const events = Array.isArray(payload.events) ? payload.events : [];
  if (events.length === 0) {
    return {
      nextCursor: Math.max(safeCurrent, payloadCursor),
      acceptedEvents: [],
    };
  }

  const acceptedEvents: RuntimeEvent[] = [];
  let nextCursor = safeCurrent;
  for (let index = 0; index < events.length; index += 1) {
    const eventCursor = safeAfter + index + 1;
    if (eventCursor > payloadCursor || eventCursor <= safeCurrent) {
      continue;
    }
    acceptedEvents.push(events[index]!);
    nextCursor = eventCursor;
  }

  return {
    nextCursor,
    acceptedEvents,
  };
}

export function reconcileRuntimeEventFrame(
  currentCursor: number,
  payload: RuntimeEventFramePayload,
): RuntimeEventCursorReconciliation {
  const payloadCursor = normalizeCursor(payload.cursor, currentCursor);
  return reconcileRuntimeEventBatch(currentCursor, Math.max(0, payloadCursor - 1), {
    cursor: payloadCursor,
    events: payload.event ? [payload.event] : [],
  });
}
