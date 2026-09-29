import test from "node:test";
import assert from "node:assert/strict";
import { validateSuggestions, proposalFingerprint, applyScriptSuggestion, ChromeCompanionProvider } from "./ai";
import type { Project } from "./model";

test("AI output must match its requested operation and contain distinct nonempty text", () => {
  assert.deepEqual(validateSuggestions(["one", "two", "three"], "hooks"), ["one", "two", "three"]);
  assert.deepEqual(validateSuggestions(["draft"], "draft"), ["draft"]);
  for (const value of [null, ["only one"], ["one", "ONE", "three"], ["", "two", "three"], ["x".repeat(3001), "two", "three"]]) {
    assert.throws(() => validateSuggestions(value, "hooks"));
  }
});
test("applying a reviewed script leaves scenes intact and rejects changed project state", () => {
  const project = { id: "test", revision: 1, script: "Original", language: "en", scenes: [{ id: "scene" }] } as Project;
  const base = proposalFingerprint(project);
  const result = applyScriptSuggestion(project, base, "Reviewed suggestion");
  assert.equal(result.script, "Reviewed suggestion");
  assert.equal(result.scenes, project.scenes);
  assert.equal(project.script, "Original");
  for (const changed of [{ ...project, script: "New words" }, { ...project, revision: 2 }, { ...project, language: "id" as const }]) {
    assert.throws(() => applyScriptSuggestion(changed, base, "Stale"));
  }
});
test("an aborted submission cancels the same known request ID", async () => {
  const original = globalThis.fetch;
  const controller = new AbortController();
  const calls: { url: string; body: Record<string, unknown> }[] = [];
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    calls.push({ url, body });
    if (url === "/api/ai/requests") {
      controller.abort(new DOMException("Cancelled", "AbortError"));
      throw controller.signal.reason;
    }
    return new Response(JSON.stringify({ status: "cancelled" }), { status: 200 });
  };
  try {
    await assert.rejects(new ChromeCompanionProvider().generate("hooks", "A short script", controller.signal), { name: "AbortError" });
    assert.equal(calls.length, 2);
    assert.equal(calls[1].url, "/api/ai/requests/" + calls[0].body.id + "/cancel");
  } finally { globalThis.fetch = original; }
});
