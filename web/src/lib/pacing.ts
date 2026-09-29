export type CaptionReport = {
  text: string;
  lines: string[];
  widths: number[];
  characters_per_second: number;
  suggested_reading_frames: number;
  errors: string[];
  warnings: string[];
};
export type PacingRow = {
  scene_id: string;
  name: string;
  old_duration: number;
  duration: number;
  minimum_frames: number;
  extra_gap_frames: number | null;
  audio: null | {
    seconds: number;
    frames: number;
    silences: { start_seconds: number; end_seconds: number; kind: string }[];
  };
  caption: CaptionReport;
  errors: string[];
  warnings: string[];
};
export type PacingProposal = {
  id: string;
  base_revision: number;
  caption_enabled: boolean;
  rows: PacingRow[];
};
export type PacingEdit = {
  scene_id: string;
  duration: number;
  caption: string;
};
export type PacingSummary = {
  scenes: {
    scene_id: string;
    name: string;
    old_duration: number;
    duration: number;
    caption: CaptionReport;
    warnings: string[];
  }[];
  old_frames: number;
  total_frames: number;
  exceeds_target: boolean;
};
export const seconds = (frames: number) => (frames / 30).toFixed(2);
