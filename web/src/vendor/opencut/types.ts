// Adapted from OpenCut Classic cf5e79e9 (MIT). MediaTime is integer project frames here.
type MediaTime = number;

export type SnapPointType =
  | "element-start"
  | "element-end"
  | "playhead"
  | "bookmark"
  | "keyframe";

export interface SnapPoint {
  time: MediaTime;
  type: SnapPointType;
  elementId?: string;
  trackId?: string;
}

export interface SnapResult {
  snappedTime: MediaTime;
  snapPoint: SnapPoint | null;
  snapDistance: number;
}

export type TimelineSnapPointSource = () => Iterable<SnapPoint>;
