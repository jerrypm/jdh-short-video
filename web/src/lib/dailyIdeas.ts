import { request } from "./api";
import type { PerformanceEvidence } from "./performance";
import type { ResearchClaim, ResearchSource } from "./research";

export type IdeaPreferences = {
  source_mode: "history" | "research";
  mode: "daily" | "manual";
  language: "en" | "id";
  topic: string;
  audience: string;
};
export type IdeaCard = {
  id: string;
  category: "series" | "new_angle" | "experiment";
  title: string;
  hook: string;
  concept: string;
  reason: string;
  difference: string;
  estimated_seconds: number;
  media_needs: string[];
  source_project_ids: string[];
  performance_ids?: string[];
  research_claims?: ResearchClaim[];
};
export type IdeaFeedback = {
  card: IdeaCard;
  verdict: "saved" | "skipped";
  performance_stale?: boolean;
  research_stale?: boolean;
  source_mode: "history" | "research";
  reason: string;
  created_at: string;
  language: string;
};
export type IdeaStatus = {
  preferences: IdeaPreferences;
  settings_revision: number;
  date: string;
  timezone: string;
  batch: {
    id: string;
    source_mode: "history" | "research";
    date: string;
    timezone: string;
    created_at: string;
    language: string;
    cards: IdeaCard[];
  } | null;
  stale: boolean;
  feedback: IdeaFeedback[];
  active_id: string | null;
  message: string;
  onboarding: boolean;
  source_count: number;
  can_generate: boolean;
  auto_due: boolean;
  retry_after: number;
  source_names: Record<string, string>;
  performance_evidence: Record<string, PerformanceEvidence>;
  research_evidence: Record<string, ResearchSource>;
  research_source_count: number;
};
export const localTimezone = () =>
  Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
export const ideaRequest = <T = IdeaStatus>(
  path: string,
  method = "GET",
  body?: unknown,
) => request<T>("/ideas" + path, method, body, AbortSignal.timeout(8000));

let clientId = "";
let activityQueue: Promise<unknown> = Promise.resolve();
export function ideaActivity(editing: boolean) {
  clientId ||= crypto.randomUUID();
  // Serialize navigation heartbeats so a delayed old response cannot re-enable inference.
  activityQueue = activityQueue
    .catch(() => undefined)
    .then(() =>
      ideaRequest("/activity", "POST", { client_id: clientId, editing }),
    );
  return activityQueue;
}
export const categoryLabel = (card: IdeaCard) =>
  ({
    series: card.source_project_ids.length
      ? "Lanjutan seri"
      : "Mulai seri baru",
    new_angle: "Sudut pandang baru",
    experiment: "Eksperimen relevan",
  })[card.category];
