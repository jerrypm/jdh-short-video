import type { Motion } from "./motion";
import type { UploadMetadata, QualitySettings } from "./quality";
export type Asset = {
  id: string;
  name: string;
  file: string;
  kind: "image" | "video" | "audio";
  frames: number;
  width: number;
  height: number;
  has_audio: boolean;
  peaks: number[];
};
export type Scene = {
  id: string;
  name: string;
  narration: string;
  caption: string;
  duration: number;
  media_id: string | null;
  audio_id: string | null;
  audio_text: string;
  source_in: number;
  audio_in: number;
  fit: "fit" | "fill";
  scale: number;
  x: number;
  y: number;
  source_volume: number;
  motion?: Motion;
  planning?: {
    provider: "gemini-nano-local";
    visual_need: string;
    motion_intent: string;
    estimated_frames: number;
    source_revisions: Record<string, number>;
  } | null;
};
export type CaptionStyle = {
  preset: "putih" | "lime" | "bar";
  size: number;
  position: number;
  enabled: boolean;
};
export type Project = {
  schema_version: 1;
  id: string;
  name: string;
  language: "id" | "en";
  target: 15 | 30 | 45 | 60;
  script: string;
  reference: string;
  reference_notes: string;
  scenes: Scene[];
  assets: Asset[];
  caption_style: CaptionStyle;
  narration_volume: number;
  music_id: string | null;
  music_volume: number;
  motion_mode?: "gentle" | "none";
  upload?: UploadMetadata;
  quality_settings?: QualitySettings;
  updated_at: string;
  revision: number;
};
export type Job = {
  id: string;
  project_id: string;
  kind: "render" | "tts" | "quality";
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  message: string;
  files: string[];
  result: null | {
    asset?: Asset;
    scene_id?: string;
    text?: string;
    frames?: number;
    revision?: number;
    width?: number;
    height?: number;
    verification?: {
      verified_file: boolean;
      full_decode_passed: boolean;
      frames: number;
      fps: number;
      audio: { peak_dbfs: number | null; seconds: number };
    };
  };
};
export type Capabilities = {
  desktop?: boolean;
  ffmpeg: boolean;
  ffprobe: boolean;
  caption: boolean;
  storage: string;
  free_bytes: number;
  tts: { available: boolean; voices: string[]; message: string };
};
export const FPS = 30;
export function newScene(name = "Scene baru", duration = 150): Scene {
  return {
    id: crypto.randomUUID(),
    name,
    narration: "",
    caption: "",
    duration,
    media_id: null,
    audio_id: null,
    audio_text: "",
    source_in: 0,
    audio_in: 0,
    fit: "fill",
    scale: 1,
    x: 0,
    y: 0,
    source_volume: 0,
  };
}
export const totalFrames = (project: Project) =>
  project.scenes.reduce((n, s) => n + s.duration, 0);
export const timecode = (frames: number) =>
  `${Math.floor(frames / 1800)
    .toString()
    .padStart(
      2,
      "0",
    )}:${Math.floor(frames / 30) % 60 < 10 ? "0" : ""}${Math.floor(frames / 30) % 60}:${(Math.floor(frames) % 30).toString().padStart(2, "0")}`;
export const shortTime = (frames: number) =>
  `${Math.floor(frames / 1800)}:${(Math.floor(frames / 30) % 60).toString().padStart(2, "0")}`;
export function sceneRanges(scenes: Scene[]) {
  let offset = 0;
  return scenes.map((s) => {
    const start = offset;
    offset += s.duration;
    return { ...s, start, end: offset };
  });
}
export function removeScene(scenes: Scene[], id: string) {
  const index = scenes.findIndex((scene) => scene.id === id);
  if (index === -1) return null;
  const remaining = scenes.filter((scene) => scene.id !== id);
  const next = sceneRanges(remaining)[Math.min(index, remaining.length - 1)];
  return { scenes: remaining, selected: next?.id ?? "", frame: next?.start ?? 0 };
}
export function splitScene(
  scenes: Scene[],
  id: string,
  frame: number,
): Scene[] {
  const selected = sceneRanges(scenes).find((s) => s.id === id);
  if (!selected) return scenes;
  const local = frame - selected.start;
  if (local < 9 || selected.duration - local < 9) return scenes;
  // Narration is kept whole; splitting its spoken words is deliberately blocked.
  if (selected.audio_id) return scenes;
  return scenes.flatMap((s) =>
    s.id !== id
      ? [s]
      : [
          { ...s, duration: local },
          {
            ...s,
            id: crypto.randomUUID(),
            name: s.name + " · 2",
            duration: s.duration - local,
            source_in: s.source_in + local,
          },
        ],
  );
}
export function buildScenes(script: string, target: number): Scene[] {
  const paragraphs = script
    .trim()
    .split(/\n\s*\n/)
    .filter(Boolean)
    .slice(0, 30);
  const chunks =
    paragraphs.length > 1
      ? paragraphs
      : script
          .split(/(?<=[.!?])\s+/)
          .filter(Boolean)
          .slice(0, 30);
  const words = chunks.map((c) => Math.max(1, c.split(/\s+/).length));
  const sum = words.reduce((a, b) => a + b, 0);
  return chunks.map((text, i) => ({
    ...newScene(
      i === 0 ? "Hook" : i === chunks.length - 1 ? "Penutup" : `Scene ${i + 1}`,
      Math.min(1800, Math.max(9, Math.round((target * 30 * words[i]) / sum))),
    ),
    narration: text,
    caption: "",
  }));
}
