import { useEffect, useRef, type KeyboardEvent as ReactKeyboardEvent } from "react";

import type { RuntimeRouteAdmission } from "../../types";
import { routeAdmissionCopy } from "./routeAdmissionPresentation";

function focusableElements(container: HTMLElement | null) {
  if (!container) return [] as HTMLElement[];
  return Array.from(
    container.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((element) => element.offsetParent !== null);
}

function trapTab(event: ReactKeyboardEvent<HTMLElement>, container: HTMLElement | null) {
  if (event.key !== "Tab") return;
  const elements = focusableElements(container);
  if (elements.length === 0) {
    event.preventDefault();
    return;
  }
  const first = elements[0]!;
  const last = elements[elements.length - 1]!;
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

export function RouteAdmissionDialog({
  admission,
  locale,
  onCancel,
  onConfirm,
}: {
  admission: RuntimeRouteAdmission;
  locale: "en" | "zh-CN";
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const copy = routeAdmissionCopy(admission, locale);
  const titleId = "route-admission-title";

  useEffect(() => {
    const first = focusableElements(dialogRef.current)[0];
    first?.focus();
  }, []);

  function onKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
      return;
    }
    trapTab(event, dialogRef.current);
  }

  return (
    <div className="modal-scrim route-admission-scrim">
      <div
        ref={dialogRef}
        className={`modal-card route-admission-dialog route-admission-${copy.tone}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        data-testid="route-admission-dialog"
        onKeyDown={onKeyDown}
      >
        <div className="card-header">
          <h2 id={titleId}>{copy.title}</h2>
          <span className={`status-tag route-admission-tag route-admission-tag-${copy.tone}`}>{copy.badge}</span>
        </div>
        <p className="route-admission-summary">{copy.summary}</p>
        <p className="route-admission-effective" data-testid="route-admission-effective">{copy.effectiveLine}</p>
        {copy.reasons.length > 0 ? (
          <ul className="route-admission-reasons">
            {copy.reasons.map((reason) => <li key={reason}>{reason}</li>)}
          </ul>
        ) : null}
        {copy.fallbackLine ? <p className="route-admission-fallback">{copy.fallbackLine}</p> : null}
        <div className="modal-actions route-admission-actions">
          {copy.canContinue ? (
            <button type="button" className="primary-button" data-testid="route-admission-confirm" onClick={onConfirm}>
              {copy.continueLabel}
            </button>
          ) : null}
          <button type="button" className="ghost-button" data-testid="route-admission-cancel" onClick={onCancel}>
            {copy.cancelLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
