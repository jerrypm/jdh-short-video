import { test } from "node:test";
import assert from "node:assert/strict";
import {
  defaultQualitySettings,
  initialSelection,
  editorialRequest,
} from "./quality";
import { assertSavedSnapshot } from "./storyboard";
import { newScene, type Project } from "./model";
const project = {
  id: "a".repeat(32),
  name: "Local short",
  scenes: [newScene()],
  caption_style: { position: 78 },
  narration_volume: 1,
  music_volume: 0.15,
  revision: 0,
  updated_at: "",
} as Project;
test("old manifests acquire quality and metadata defaults without losing review freshness", () => {
  assertSavedSnapshot(project, {
    ...project,
    quality_settings: defaultQualitySettings(),
    upload: { title: "", description: "" },
  });
  assert.throws(() =>
    assertSavedSnapshot(project, {
      ...project,
      upload: { title: "Changed elsewhere", description: "" },
    }),
  );
  const selection = initialSelection(project);
  assert.equal(selection.upload.title, "Local short");
  assert.deepEqual(selection.scenes, []);
});
test("uncertain editorial submit is cancelled by the same request id", async () => {
  const original = globalThis.fetch;
  const controller = new AbortController();
  const id = "11111111-1111-4111-8111-111111111111";
  const paths: string[] = [];
  globalThis.fetch = async (input, options) => {
    const path = String(input);
    paths.push(path);
    if (path.endsWith("/cancel")) return new Response("{}");
    assert.equal(JSON.parse(String(options?.body)).id, id);
    controller.abort();
    throw new DOMException("Cancelled", "AbortError");
  };
  try {
    await assert.rejects(
      editorialRequest(project.id, "check", id, controller.signal),
    );
    assert.equal(
      paths.at(-1),
      `/api/quality/${project.id}/check/editorial/${id}/cancel`,
    );
  } finally {
    globalThis.fetch = original;
  }
});
test("completed editorial remains a proposal with no project write", async () => {
  const original = globalThis.fetch;
  const calls: string[] = [];
  globalThis.fetch = async (input) => {
    calls.push(String(input));
    return new Response(
      JSON.stringify({
        status: "completed",
        editorial: { title: "QA suggestion", description: "", notes: [] },
      }),
    );
  };
  try {
    const result = await editorialRequest(
      project.id,
      "check",
      "11111111-1111-4111-8111-111111111111",
      new AbortController().signal,
    );
    assert.equal(result.title, "QA suggestion");
    assert.equal(calls.length, 1);
    assert.ok(calls[0].endsWith("/editorial"));
  } finally {
    globalThis.fetch = original;
  }
});
