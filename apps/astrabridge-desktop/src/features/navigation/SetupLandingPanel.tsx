import type { ReactNode } from "react";

export type SetupLandingMetric = {
  id: string;
  label: string;
  value: string;
};

export type SetupLandingAction = {
  id: string;
  icon: ReactNode;
  title: string;
  detail: string;
  status: string;
  actionLabel: string;
  onClick: () => void;
};

type SetupLandingPanelProps = {
  testId: string;
  eyebrow: string;
  title: string;
  summary: string;
  stateLabel: string;
  stateItems: SetupLandingMetric[];
  sectionTitle: string;
  actions: SetupLandingAction[];
};

function ActionRow({ icon, title, detail, status, actionLabel, onClick }: Omit<SetupLandingAction, "id">) {
  return (
    <button type="button" className="setup-landing-action" onClick={onClick}>
      <span className="setup-landing-action-icon" aria-hidden="true">{icon}</span>
      <span className="setup-landing-action-copy">
        <strong>{title}</strong>
        <small>{detail}</small>
      </span>
      <span className="setup-landing-action-meta">
        <em>{status}</em>
        <span>{actionLabel}</span>
      </span>
    </button>
  );
}

export function SetupLandingPanel({
  testId,
  eyebrow,
  title,
  summary,
  stateLabel,
  stateItems,
  sectionTitle,
  actions,
}: SetupLandingPanelProps) {
  return (
    <div className="manager-panel setup-landing-panel" data-testid={testId}>
      <section className="setup-landing-header">
        <div className="setup-landing-summary">
          <span className="eyebrow">{eyebrow}</span>
          <h3>{title}</h3>
          <p className="muted">{summary}</p>
        </div>
        <div className="setup-landing-strip" aria-label={stateLabel}>
          {stateItems.map((item) => (
            <div className="setup-landing-strip-item" key={item.id}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="manager-section">
        <h4>{sectionTitle}</h4>
        <div className="setup-landing-actions">
          {actions.map((action) => (
            <ActionRow
              key={action.id}
              icon={action.icon}
              title={action.title}
              detail={action.detail}
              status={action.status}
              actionLabel={action.actionLabel}
              onClick={action.onClick}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
