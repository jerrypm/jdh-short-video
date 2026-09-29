import test from "node:test";
import assert from "node:assert/strict";
import {
  assertSavedSnapshot,
  assertUnchanged,
  generateStoryboard,
} from "./storyboard";
import { newScene, type Project } from "./model";

const project = {
  id: "a".repeat(32),
  script: "Original",
  revision: 1,
  updated_at: "yesterday",
  language: "en",
  scenes: [newScene("Original")],
  assets: [],
} as unknown as Project;
test("review rejects changed local content; a save receipt alone is safe but external edits are not", () => {
  const fingerprint = JSON.stringify(project);
  assert.doesNotThrow(() => assertUnchanged(project, fingerprint));
  assert.throws(() =>
    assertUnchanged({ ...project, script: "New unsaved content" }, fingerprint),
  );
  const saved = {
    ...project,
    revision: 9,
    updated_at: "today",
    scenes: project.scenes.map((scene) => ({ ...scene, planning: null })),
  };
  assert.doesNotThrow(() => assertSavedSnapshot(project, saved));
  assert.doesNotThrow(() =>
    assertSavedSnapshot(
      project,
      Object.fromEntries(Object.entries(saved).reverse()) as Project,
    ),
  );
  assert.throws(() =>
    assertSavedSnapshot(project, {
      ...saved,
      script: "Edited by another client",
    }),
  );
  assert.throws(() =>
    assertSavedSnapshot(project, {
      ...saved,
      scenes: saved.scenes.map((s) => ({ ...s, duration: 300 })),
    }),
  );
});
test("cancelling an uncertain storyboard POST cancels the same request without applying anything", async () => {
  const original = globalThis.fetch;
  const controller = new AbortController();
  const id = crypto.randomUUID();
  const calls: string[] = [];
  globalThis.fetch = async (input) => {
    const url = String(input);
    calls.push(url);
    if (url.endsWith("/requests")) {
      controller.abort(new DOMException("Cancelled", "AbortError"));
      throw controller.signal.reason;
    }
    return new Response(JSON.stringify({ cancelled: true }));
  };
  try {
    await assert.rejects(
      generateStoryboard(project, "b".repeat(32), id, controller.signal),
      { name: "AbortError" },
    );
    assert.deepEqual(calls, [
      `/api/storyboards/${project.id}/requests`,
      `/api/storyboards/${project.id}/requests/${id}/cancel`,
    ]);
    assert.equal(project.script, "Original");
  } finally {
    globalThis.fetch = original;
  }
});
test("a completed proposal is returned for review and never auto-applied", async () => {
  const original = globalThis.fetch;
  const calls: string[] = [];
  globalThis.fetch = async (input) => {
    calls.push(String(input));
    return new Response(
      JSON.stringify({
        status: "completed",
        draft: { hook: "Review me", scenes: [] },
      }),
    );
  };
  try {
    const value = await generateStoryboard(
      project,
      "b".repeat(32),
      crypto.randomUUID(),
      new AbortController().signal,
    );
    assert.equal(value.status, "completed");
    assert.equal(calls.length, 1);
    assert.ok(!calls[0].includes("apply"));
    assert.equal(project.script, "Original");
  } finally {
    globalThis.fetch = original;
  }
});
