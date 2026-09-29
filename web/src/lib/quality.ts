import { request } from "./api";
import type { Job, Project } from "./model";
export type QualitySettings = {
  long_silence_seconds: number;
  silence_dbfs: number;
  peak_warning_dbfs: number;
  caption_cps: number;
};
export const defaultQualitySettings = (): QualitySettings => ({
  long_silence_seconds: 1.5,
  silence_dbfs: -40,
  peak_warning_dbfs: -0.1,
  caption_cps: 20,
});
export type UploadMetadata = { title: string; description: string };
export type Finding = {
  code: string;
  severity: "error" | "warning" | "info";
  message: string;
  scene_id: string | null;
  start_frame: number;
  end_frame: number;
};
export type QualityRow = {
  scene_id: string;
  name: string;
  start_frame: number;
  end_frame: number;
  duration: number;
  minimum_frames: number;
  caption: string;
  suggested_duration: number;
  suggested_caption: string;
};
export type QualityReport = {
  id: string;
  project_id: string;
  base_revision: number;
  preset: string;
  settings: QualitySettings;
  output: { width: number; height: number; frames: number; seconds: number };
  findings: Finding[];
  rows: QualityRow[];
  limitations: string[];
};
export type QualitySelection = {
  upload: UploadMetadata;
  scenes: { scene_id: string; duration: number; caption: string }[];
  caption_position: number;
  narration_volume: number;
  music_volume: number;
};
export type Editorial = {
  title: string;
  description: string;
  notes: {
    scene_id: string;
    start_frame: number;
    end_frame: number;
    category: string;
    suggestion: string;
    reason: string;
  }[];
};
export type EditorialRequest = {
  id: string;
  status: string;
  message: string;
  editorial: Editorial | null;
};
export function initialSelection(project: Project): QualitySelection {
  return {
    upload: {
      title: project.upload?.title || project.name.slice(0, 100),
      description: project.upload?.description || "",
    },
    scenes: [],
    caption_position: project.caption_style.position,
    narration_volume: project.narration_volume,
    music_volume: project.music_volume,
  };
}
export function delay(signal: AbortSignal, milliseconds = 650) {
  return new Promise<void>((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer);
      signal.removeEventListener("abort", abort);
      reject(signal.reason);
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, milliseconds);
    signal.addEventListener("abort", abort, { once: true });
    if (signal.aborted) abort();
  });
}
export async function editorialRequest(
  pid: string,
  checkId: string,
  id: string,
  signal: AbortSignal,
) {
  const path = `/quality/${pid}/${checkId}/editorial`;
  const bounded = AbortSignal.any([signal, AbortSignal.timeout(125000)]);
  let completed = false;
  try {
    bounded.throwIfAborted();
    let value = await request<EditorialRequest>(path, "POST", { id }, bounded);
    while (["queued", "running"].includes(value.status)) {
      await delay(bounded);
      value = await request<EditorialRequest>(
        `${path}/${id}`,
        "GET",
        undefined,
        bounded,
      );
    }
    bounded.throwIfAborted();
    if (value.status !== "completed" || !value.editorial)
      throw new Error(value.message || "Review Nano tidak tersedia.");
    completed = true;
    return value.editorial;
  } finally {
    if (!completed)
      await request(
        `${path}/${id}/cancel`,
        "POST",
        {},
        AbortSignal.timeout(3000),
      ).catch(() => undefined);
  }
}
export type QualityJob = Omit<Job, "result"> & { result: QualityReport | null };
