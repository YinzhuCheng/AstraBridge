import type { ReactNode, SVGProps } from "react";

type StarbridgeIconProps = Omit<SVGProps<SVGSVGElement>, "width" | "height"> & {
  size?: number;
  strokeWidth?: number;
};

function StarbridgeIconBase({
  size = 16,
  strokeWidth = 1.85,
  children,
  viewBox = "0 0 24 24",
  ...props
}: StarbridgeIconProps & { children: ReactNode; viewBox?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox={viewBox}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

function Node({ cx, cy, r = 1.25 }: { cx: number; cy: number; r?: number }) {
  return <circle cx={cx} cy={cy} r={r} fill="currentColor" stroke="none" />;
}

export function StarbridgeTaskCreateIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <rect x="4.5" y="5.5" width="11" height="13" rx="2.2" />
      <path d="M8 9h4.75" />
      <path d="M8 13h4.75" />
      <Node cx={7} cy={9} />
      <path d="M18 7.75v5.5" />
      <path d="M15.25 10.5h5.5" />
    </StarbridgeIconBase>
  );
}

export function StarbridgeSearchIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <circle cx="10.25" cy="10.25" r="4.75" />
      <path d="m13.8 13.8 4.4 4.4" />
      <Node cx={8.1} cy={10.25} />
    </StarbridgeIconBase>
  );
}

export function StarbridgeSessionIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <path d="M7.25 14.75c1.2-2.35 8.3-2.35 9.5 0" />
      <path d="M8.9 10.4c.95-1.55 5.25-1.55 6.2 0" />
      <path d="M11.2 17.6c.45.3 1.15.3 1.6 0" />
      <Node cx={12} cy={8.15} />
      <Node cx={8.5} cy={14.75} />
      <Node cx={15.5} cy={14.75} />
    </StarbridgeIconBase>
  );
}

export function StarbridgeSettingsIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <rect x="4.5" y="5.5" width="15" height="13" rx="2.2" />
      <path d="M7.5 9h9" />
      <path d="M7.5 15h9" />
      <Node cx={10.25} cy={9} />
      <Node cx={14} cy={15} />
    </StarbridgeIconBase>
  );
}

export function StarbridgeProjectIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <path d="M4.5 8a2 2 0 0 1 2-2h4.4l1.5 1.8h5.1a2 2 0 0 1 2 2v6.5a2 2 0 0 1-2 2h-11a2 2 0 0 1-2-2z" />
      <Node cx={8.1} cy={12.1} />
    </StarbridgeIconBase>
  );
}

export function StarbridgeFolderIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <path d="M4.75 9a1.9 1.9 0 0 1 1.9-1.9h3.7l1.45 1.7h5.55a1.9 1.9 0 0 1 1.9 1.9v5.75a1.95 1.95 0 0 1-1.95 1.95H6.7a1.95 1.95 0 0 1-1.95-1.95z" />
      <path d="M8.05 12.15h5.4" />
    </StarbridgeIconBase>
  );
}

export function StarbridgeTaskIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <rect x="5" y="5.5" width="14" height="13" rx="2.2" />
      <Node cx={8.2} cy={9.6} />
      <Node cx={8.2} cy={14.3} />
      <path d="M10.7 9.6h5.05" />
      <path d="M10.7 14.3h5.05" />
    </StarbridgeIconBase>
  );
}

export function StarbridgeCompactContextIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <path d="M5.5 8h4.25" />
      <path d="M5.5 12h8.5" />
      <path d="M5.5 16h4.25" />
      <path d="m18 8-3 4 3 4" />
    </StarbridgeIconBase>
  );
}

export function StarbridgeForkTaskIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <Node cx={6} cy={12} />
      <Node cx={17.5} cy={7.5} />
      <Node cx={17.5} cy={16.5} />
      <path d="M7.4 12h3.8c1.2 0 1.95-.8 1.95-1.95V8.7" />
      <path d="M11.2 12h1.95c1.2 0 1.95.8 1.95 1.95v1.35" />
      <rect x="15.5" y="5.5" width="4" height="4" rx="1" />
      <rect x="15.5" y="14.5" width="4" height="4" rx="1" />
    </StarbridgeIconBase>
  );
}

export function StarbridgeAttachIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <path d="M14.7 7.1 9.25 12.55a2.4 2.4 0 1 0 3.4 3.4l5.35-5.35a3.85 3.85 0 0 0-5.45-5.45l-6.2 6.2" />
      <Node cx={16.85} cy={6.85} />
    </StarbridgeIconBase>
  );
}

export function StarbridgeFileIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <path d="M7 4.8h6.85l3.15 3.15v10.25A1.8 1.8 0 0 1 15.2 20H7.95A1.95 1.95 0 0 1 6 18.05V6.75A1.95 1.95 0 0 1 7.95 4.8z" />
      <path d="M13.8 4.95v3.2H17" />
      <path d="M8.8 13.2h5.7" />
    </StarbridgeIconBase>
  );
}

export function StarbridgeImageIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <rect x="5" y="5.5" width="14" height="13" rx="2.1" />
      <path d="m8.1 15.1 2.75-3.1 2.35 2.35 2.7-3.2" />
      <Node cx={9} cy={9.2} />
    </StarbridgeIconBase>
  );
}

export function StarbridgeVoiceIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <rect x="9.15" y="5.2" width="5.7" height="9.2" rx="2.85" />
      <path d="M7.4 11.2a4.6 4.6 0 0 0 9.2 0" />
      <path d="M12 15.8v3.2" />
      <path d="M9.5 19h5" />
      <Node cx={16.95} cy={8.15} r={1.05} />
    </StarbridgeIconBase>
  );
}

export function StarbridgeSendIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <Node cx={6.1} cy={16.4} />
      <path d="M7.55 16.15h3.2c1.25 0 2.1-.35 2.95-1.25l4.55-4.85" />
      <path d="m14.6 9.9 3.85-.1-.25 3.85" />
      <path d="M10.2 11.2h2.1" />
    </StarbridgeIconBase>
  );
}

export function StarbridgePermissionAskIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <path d="M7.2 7.2h9.6v4.35c0 3.25-2.05 5.45-4.8 6.3-2.75-.85-4.8-3.05-4.8-6.3z" />
      <path d="M9.1 11.6h5.8" />
      <Node cx={12} cy={9.55} />
    </StarbridgeIconBase>
  );
}

export function StarbridgePermissionAutoIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <path d="M8 8.3c1.2-1.55 3.5-2.25 5.55-1.65 2 .6 3.55 2.35 3.85 4.45.3 2.15-.7 4.3-2.55 5.55" />
      <path d="M16 15.7c-1.2 1.55-3.5 2.25-5.55 1.65-2-.6-3.55-2.35-3.85-4.45-.3-2.15.7-4.3 2.55-5.55" />
      <Node cx={8} cy={8.3} />
      <Node cx={16} cy={15.7} />
    </StarbridgeIconBase>
  );
}

export function StarbridgePermissionFullIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <path d="M7.35 8.1V6.85A3.65 3.65 0 0 1 11 3.2h1.9a3.1 3.1 0 0 1 3.1 3.1V8.1" />
      <rect x="6" y="8.1" width="8.8" height="9.6" rx="2" />
      <path d="M14.8 12.9H18.9" />
      <Node cx={18.9} cy={12.9} />
    </StarbridgeIconBase>
  );
}

export function StarbridgeWorkflowDefaultIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <rect x="4.8" y="5.6" width="14.4" height="11.8" rx="2.2" />
      <path d="M8 10h7.2" />
      <path d="M8 13.7h4.4" />
      <Node cx={6.7} cy={10} />
    </StarbridgeIconBase>
  );
}

export function StarbridgeWorkflowPlanIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <rect x="5" y="5.3" width="14" height="13.4" rx="2.2" />
      <Node cx={8} cy={9.2} />
      <Node cx={8} cy={12} />
      <Node cx={8} cy={14.8} />
      <path d="M10.5 9.2H16" />
      <path d="M10.5 12H16" />
      <path d="M10.5 14.8H14.2" />
    </StarbridgeIconBase>
  );
}

export function StarbridgeWorkflowGoalIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <circle cx="16.5" cy="7.6" r="2.7" />
      <path d="M6.2 17.2c1.2-4.4 4.25-7.45 8.45-8.55" />
      <Node cx={6.2} cy={17.2} />
      <path d="M16.5 4.9v5.4" />
      <path d="M13.8 7.6h5.4" />
    </StarbridgeIconBase>
  );
}

export function StarbridgeStatusIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <rect x="5" y="5.5" width="14" height="13" rx="2.2" />
      <path d="M8.1 15.2V8.8" />
      <path d="M12 15.2v-3.4" />
      <path d="M15.9 15.2v-5.5" />
      <Node cx={12} cy={10.2} />
    </StarbridgeIconBase>
  );
}

export function StarbridgeReviewIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <rect x="4.8" y="5.5" width="14.4" height="13" rx="2.2" />
      <path d="M12 7.6v8.8" />
      <path d="M7.4 10.1h2.7" />
      <path d="M13.9 13.7h2.7" />
      <Node cx={8.75} cy={13.7} />
      <Node cx={15.25} cy={10.1} />
    </StarbridgeIconBase>
  );
}

export function StarbridgeBrowserIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <rect x="4.8" y="5.2" width="14.4" height="13.6" rx="2.2" />
      <path d="M4.8 8.5h14.4" />
      <Node cx={7.3} cy={6.9} r={0.95} />
      <path d="m8.2 14.8 2.8-2.85 2.2 2.1 2.55-3.2" />
    </StarbridgeIconBase>
  );
}

export function StarbridgeFilesIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <path d="M8.2 5h7l2.2 2.2v10.05a1.75 1.75 0 0 1-1.75 1.75H8.85a1.65 1.65 0 0 1-1.65-1.65z" />
      <path d="M6.6 7.2H5.7A1.7 1.7 0 0 0 4 8.9v8.4A1.7 1.7 0 0 0 5.7 19h6.1" />
      <path d="M12 5v3.1h3.2" />
    </StarbridgeIconBase>
  );
}

export function StarbridgeRenameIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <path d="m8 16 1.05-3.2 6.45-6.45a1.55 1.55 0 0 1 2.2 2.2L11.25 15l-3.25 1Z" />
      <path d="M13.8 8.3l1.9 1.9" />
    </StarbridgeIconBase>
  );
}

export function StarbridgeArchiveIcon(props: StarbridgeIconProps) {
  return (
    <StarbridgeIconBase {...props}>
      <path d="M5.4 7.2h13.2l-1.1 9.05A1.9 1.9 0 0 1 15.6 18H8.4a1.9 1.9 0 0 1-1.9-1.75z" />
      <path d="M4.5 7.2V5.6h15v1.6" />
      <path d="M9.1 11.7h5.8" />
      <Node cx={12} cy={14.65} />
    </StarbridgeIconBase>
  );
}
