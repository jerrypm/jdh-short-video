import { request } from "./api";
import type { Project } from "./model";
import type { IdeaCard } from "./dailyIdeas";
import { defaultMotion, type Motion } from "./motion";
import { defaultQualitySettings } from "./quality";
export type DraftScene = {
  name: string;
  narration: string;
  caption: string;
  estimated_frames: number;
  visual_need: string;
  media_id: string | null;
  media_status: "available" | "missing";
  audio_id: string | null;
  effect: "static";
  motion_intent: string;
  motion?: Motion;
  source_project_ids: string[];
};
export type Draft = { hook: string; scenes: DraftScene[] };
export type Selection = {
  draft: Draft;
  selected: number[];
  mode: "append" | "replace";
};
export type Proposal = {
  id: string;
  project_id: string;
  base_revision: number;
  catalog_revision: number;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  message: string;
  draft: Draft | null;
  expires_in: number;
  sources: {
    project_id: string;
    name: string;
    summary: string;
    summary_origin: string;
    source_revision: number;
  }[];
  assets: {
    id: string;
    name: string;
    kind: "image" | "video" | "audio";
    frames: number;
  }[];
};
export type PlanSummary = {
  mode: "append" | "replace";
  added_scenes: number;
  removed_scenes: number;
  old_frames: number;
  total_frames: number;
  missing_media: number;
  exceeds_target: boolean;
  plan: {
    index: number;
    frames: number;
    estimated_frames: number;
    duration_origin: string;
    media_missing: boolean;
  }[];
};
export type IdeaOption = { card: IdeaCard; language: string };
export function assertUnchanged(current: Project, fingerprint: string) {
  if (JSON.stringify(current) !== fingerprint)
    throw new Error(
      "Proyek berubah selama review. Tutup dan buat proposal baru.",
    );
}
export function assertSavedSnapshot(current: Project, saved: Project) {
  const canonical = (value: unknown): unknown => {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value === "object")
      return Object.fromEntries(
        Object.entries(value)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([key, item]) => [key, canonical(item)]),
      );
    return value;
  };
  const content = (project: Project) => {
    const { revision, updated_at, ...rest } = project;
    void revision;
    void updated_at;
    return JSON.stringify(
      canonical({
        ...rest,
        motion_mode: rest.motion_mode ?? "gentle",
        upload: rest.upload ?? { title: "", description: "" },
        quality_settings: rest.quality_settings ?? defaultQualitySettings(),
        scenes: rest.scenes.map((scene) => ({
          ...scene,
          planning: scene.planning ?? null,
          motion: scene.motion ?? defaultMotion(),
        })),
      }),
    );
  };
  if (content(current) !== content(saved))
    throw new Error(
      "Proyek di penyimpanan berubah. Buka ulang proyek sebelum membuat proposal.",
    );
}
export function storyboardRequest<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
) {
  return request<T>(
    "/storyboards" + path,
    method,
    body,
    signal || AbortSignal.timeout(10000),
  );
}
export async function generateStoryboard(
  project: Project,
  ideaId: string,
  id: string,
  signal: AbortSignal,
): Promise<Proposal> {
  const path = `/${project.id}/requests/${id}`;
  let completed = false;
  const controller = new AbortController();
  const abort = () => controller.abort(signal.reason);
  signal.addEventListener("abort", abort, { once: true });
  const timeout = setTimeout(
    () =>
      controller.abort(
        new DOMException(
          "Nano belum selesai; coba ide lebih ringkas.",
          "TimeoutError",
        ),
      ),
    125000,
  );
  try {
    if (signal.aborted) abort();
    controller.signal.throwIfAborted();
    let value = await storyboardRequest<Proposal>(
      `/${project.id}/requests`,
      "POST",
      { id, idea_id: ideaId, base_revision: project.revision },
      controller.signal,
    );
    while (["queued", "running"].includes(value.status)) {
      await new Promise<void>((resolve, reject) => {
        const cancel = () => {
          clearTimeout(timer);
          controller.signal.removeEventListener("abort", cancel);
          reject(controller.signal.reason);
        };
        const timer = setTimeout(() => {
          controller.signal.removeEventListener("abort", cancel);
          resolve();
        }, 650);
        controller.signal.addEventListener("abort", cancel, { once: true });
        if (controller.signal.aborted) cancel();
      });
      value = await storyboardRequest<Proposal>(
        path,
        "GET",
        undefined,
        controller.signal,
      );
    }
    controller.signal.throwIfAborted();
    if (value.status !== "completed" || !value.draft)
      throw new Error(value.message || "Proposal belum tersedia.");
    completed = true;
    return value;
  } finally {
    clearTimeout(timeout);
    signal.removeEventListener("abort", abort);
    if (!completed)
      await storyboardRequest(
        path + "/cancel",
        "POST",
        {},
        AbortSignal.timeout(3000),
      ).catch(() => undefined);
  }
}
