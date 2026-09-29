import { z } from "zod";
import { request } from "./api";
import type { Project } from "./model";

export type Availability = "unavailable" | "downloadable" | "downloading" | "available";
export type AIOperation = "hooks" | "draft";
export type AIStatus = {
  provider: "gemini-nano-local";
  transport: "chrome-companion";
  connected: boolean;
  availability: Availability;
  languages: { en: Availability; id: Availability };
  busy: boolean;
  download_progress: number;
  message: string;
};
type AIJob = {
  id: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  suggestions: string[] | null;
  message: string;
};
export interface AIProvider {
  status(): Promise<AIStatus>;
  generate(operation: AIOperation, input: string, signal: AbortSignal): Promise<string[]>;
}
export function validateSuggestions(value: unknown, operation: AIOperation): string[] {
  const count = operation === "hooks" ? 3 : 1;
  return z.array(z.string().trim().min(1).max(3000)).length(count)
    .refine((items) => new Set(items.map((text) => text.toLowerCase())).size === count, "Saran AI berulang.")
    .parse(value);
}
function delay(signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const abort = () => { clearTimeout(timer); signal.removeEventListener("abort", abort); reject(signal.reason); };
    const timer = setTimeout(() => { signal.removeEventListener("abort", abort); resolve(); }, 650);
    signal.addEventListener("abort", abort, { once: true });
    if (signal.aborted) abort();
  });
}
export class ChromeCompanionProvider implements AIProvider {
  status() {
    return request<AIStatus>("/ai/status", "GET", undefined, AbortSignal.timeout(5000));
  }
  async generate(operation: AIOperation, input: string, signal: AbortSignal) {
    if (!input.trim() || input.length > 12000) throw new Error("Naskah harus berisi 1–12.000 karakter.");
    signal.throwIfAborted();
    const id = crypto.randomUUID();
    const controller = new AbortController();
    const abort = () => controller.abort(signal.reason);
    signal.addEventListener("abort", abort, { once: true });
    const timer = setTimeout(() => controller.abort(new DOMException("Nano belum selesai. Coba naskah lebih pendek.", "TimeoutError")), 125000);
    let completed = false;
    try {
      let job = await request<AIJob>("/ai/requests", "POST", { id, operation, language: "en", input }, controller.signal);
      while (job.status === "queued" || job.status === "running") {
        await delay(controller.signal);
        job = await request<AIJob>("/ai/requests/" + id, "GET", undefined, controller.signal);
      }
      controller.signal.throwIfAborted();
      if (job.status === "cancelled") throw new DOMException(job.message, "AbortError");
      if (job.status !== "completed") throw new Error(job.message || "Nano gagal memproses naskah.");
      const result = validateSuggestions(job.suggestions, operation);
      completed = true;
      return result;
    } finally {
      clearTimeout(timer);
      signal.removeEventListener("abort", abort);
      if (!completed) {
        await request("/ai/requests/" + id + "/cancel", "POST", {}, AbortSignal.timeout(3000)).catch(() => {});
      }
    }
  }
}
export const nanoProvider: AIProvider = new ChromeCompanionProvider();
export async function availability(): Promise<Availability> {
  try { return (await nanoProvider.status()).availability; }
  catch { return "unavailable"; }
}
export function proposalFingerprint(project: Project) {
  return JSON.stringify(project);
}
export function applyScriptSuggestion(project: Project, base: string, script: string): Project {
  if (proposalFingerprint(project) !== base) throw new Error("Proyek berubah sejak saran dibuat. Buat saran baru untuk naskah terbaru.");
  return { ...project, script };
}
