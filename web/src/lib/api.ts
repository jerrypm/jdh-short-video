import type { Project } from "./model";
let token = "";
export async function bootstrap() {
  const result = await fetch("/api/session").then((r) => r.json());
  token = result.csrf;
}
export async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const multipart = body instanceof FormData;
  const response = await fetch("/api" + path, {
    method,
    signal,
    headers: {
      "X-JDH-CSRF": token,
      ...(!multipart && body !== undefined
        ? { "Content-Type": "application/json" }
        : {}),
    },
    body:
      body === undefined ? undefined : multipart ? body : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: `HTTP ${response.status}` }));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : JSON.stringify(error.detail),
    );
  }
  return response.json();
}
export const assetURL = (project: Project, id: string) =>
  `/api/projects/${project.id}/media/${id}`;
export async function captionBlob(
  text: string,
  style: Project["caption_style"],
  signal: AbortSignal,
) {
  const response = await fetch("/api/caption-preview", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-JDH-CSRF": token },
    body: JSON.stringify({ text, style }),
    signal,
  });
  if (!response.ok) {
    const result = await response.json();
    throw new Error(result.detail ?? "Caption gagal dimuat.");
  }
  return response.blob();
}

export async function calloutBlob(value: unknown, signal: AbortSignal) {
  const response = await fetch("/api/callout-preview", {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json", "X-JDH-CSRF": token },
    body: JSON.stringify(value),
  });
  if (!response.ok) {
    const result = await response.json();
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Callout tidak valid.",
    );
  }
  return response.blob();
}
