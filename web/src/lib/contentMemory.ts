export type MemoryLabels = {
  themes: string[];
  audience: string;
  series: string;
  summary: string;
  hook: string;
  format: string;
};
export type ChannelProfile = {
  name: string;
  description: string;
  audience: string;
  language: "en" | "id" | "mixed";
  themes: string[];
};
export type IdeaFeedback = {
  id: string;
  idea: string;
  verdict: "saved" | "skipped" | "used";
  reason: string;
  created_at: string;
};
export type MemoryReference = {
  project_id: string;
  included: boolean;
  category: "content" | "qa" | "duplicate";
  published: boolean;
  missing: boolean;
  observed: {
    source_revision: number;
    name: string;
    language: "en" | "id";
    updated_at: string;
    duration_frames: number;
    target_seconds: number;
    asset_ids: string[];
    excerpt: string;
    hook_excerpt: string;
    fingerprint: string;
    exported_revision: number | null;
    export_job_id: string | null;
  };
  confirmed: MemoryLabels;
  suggested: {
    provider: "gemini-nano-local";
    source_revision: number;
    labels: MemoryLabels;
  } | null;
  feedback: IdeaFeedback[];
};
export type MemoryView = {
  catalog: {
    schema_version: 1;
    revision: number;
    updated_at: string;
    profile: ChannelProfile;
    references: MemoryReference[];
  };
  projects: { id: string; name: string; language: string; qa_hint: boolean }[];
};
export type ReferenceUpdate = Pick<
  MemoryReference,
  "included" | "category" | "published" | "confirmed"
> & { source_revision: number };
export type MemoryContext = {
  catalog_revision: number;
  profile: ChannelProfile;
  references: {
    project_id: string;
    source_revision: number;
    name: string;
    language: string;
    summary: string;
    summary_origin: "user" | "project_excerpt";
    hook: string;
    hook_origin: "user" | "project_excerpt";
    themes: string[];
    audience: string;
    series: string;
    format: string;
    duration_frames: number;
    asset_ids: string[];
    asset_count: number;
    status: string;
    status_origin: string;
    exported_revision: number | null;
    feedback: IdeaFeedback[];
  }[];
};
export const parseThemes = (text: string) =>
  text
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
export const isActiveReference = (ref: MemoryReference) =>
  ref.included && ref.category === "content" && !ref.missing;
export const memoryStatus = (ref: MemoryReference) =>
  ref.published
    ? "Dipublikasikan · Anda"
    : ref.observed.exported_revision !== null
      ? "Diekspor · lokal"
      : "Draf";
