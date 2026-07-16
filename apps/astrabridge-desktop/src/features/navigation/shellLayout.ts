export const COMPACT_SHELL_BREAKPOINT = 1100;

export function isCompactShellViewport(width: number) {
  return width <= COMPACT_SHELL_BREAKPOINT;
}

export function resolveSidebarVisible({
  compactViewport,
  compactSidebarOpen,
  desktopSidebarOpen,
}: {
  compactViewport: boolean;
  compactSidebarOpen: boolean;
  desktopSidebarOpen: boolean;
}) {
  return compactViewport ? compactSidebarOpen : desktopSidebarOpen;
}
