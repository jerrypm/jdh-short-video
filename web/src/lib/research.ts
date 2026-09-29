import { request } from "./api";
export type SourceInput = {
  title: string;
  url: string;
  published_on: string;
  accessed_on: string;
  text: string;
  kind: "summary" | "excerpt";
  included: boolean;
  conflict_with: string;
  caution: string;
};
export type ResearchSource = SourceInput & {
  id: string;
  updated_at: string;
  status: "ready" | "excluded" | "stale" | "conflict" | "duplicate";
  duplicate_of: string | null;
  publication_unknown: boolean;
};
export type ResearchView = {
  revision: number;
  sources: ResearchSource[];
  eligible_count: number;
  max_age_days: number;
};
export type ResearchClaim = { claim: string; source_id: string; quote: string };
export const sourceStatus = {
  ready: "Siap sebagai referensi",
  excluded: "Tidak disertakan",
  stale: "Lebih dari 30 hari",
  conflict: "Konflik belum ditinjau",
  duplicate: "Isi duplikat",
};
export const researchRequest = <T>(path = "", method = "GET", body?: unknown) =>
  request<T>("/research" + path, method, body, AbortSignal.timeout(15000));
export function emptySource(): SourceInput {
  return {
    title: "",
    url: "",
    published_on: "",
    accessed_on: new Date().toISOString().slice(0, 10),
    text: "",
    kind: "summary",
    included: true,
    conflict_with: "",
    caution: "",
  };
}
export function sourceOnly(source: ResearchSource): SourceInput {
  return Object.fromEntries(
    Object.keys(emptySource()).map((key) => [
      key,
      source[key as keyof SourceInput],
    ]),
  ) as SourceInput;
}
export function researchCardStale(
  claims: ResearchClaim[] = [],
  evidence: Record<string, ResearchSource>,
) {
  return claims.some(
    (claim) =>
      !evidence[claim.source_id] ||
      evidence[claim.source_id].status !== "ready",
  );
}
