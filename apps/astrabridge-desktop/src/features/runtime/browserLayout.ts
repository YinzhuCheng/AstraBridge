const BROWSER_MOBILE_ASPECT_THRESHOLD = 1.28;
const BROWSER_TWO_PAGE_ASPECT_THRESHOLD = 2.14;
const BROWSER_TWO_PAGE_MAX_FIT_SCORE = 60;

export function browserStageAspectRatio(width: number, height: number) {
  const normalizedWidth = Math.max(0, Math.round(width || 0));
  const normalizedHeight = Math.max(0, Math.round(height || 0));
  if (!normalizedWidth || !normalizedHeight) return 0;
  return normalizedHeight / normalizedWidth;
}

export function desiredBrowserLayoutMode({
  isRemote,
  width,
  height,
}: {
  isRemote: boolean;
  width: number;
  height: number;
}): "desktop" | "mobile" {
  if (!isRemote) return "desktop";
  return browserStageAspectRatio(width, height) >= BROWSER_MOBILE_ASPECT_THRESHOLD ? "mobile" : "desktop";
}

export function shouldUseBrowserTwoPageStack({
  isRemote,
  desiredMode,
  aspect,
  mobileOptimized,
  responsiveFitScore,
  hasPeer,
}: {
  isRemote: boolean;
  desiredMode: "desktop" | "mobile";
  aspect: number;
  mobileOptimized?: boolean | null;
  responsiveFitScore?: number | null;
  hasPeer: boolean;
}) {
  const fitScore = typeof responsiveFitScore === "number" ? responsiveFitScore : null;
  return (
    isRemote &&
    desiredMode === "mobile" &&
    aspect >= BROWSER_TWO_PAGE_ASPECT_THRESHOLD &&
    mobileOptimized === false &&
    (fitScore == null || fitScore <= BROWSER_TWO_PAGE_MAX_FIT_SCORE) &&
    hasPeer
  );
}
