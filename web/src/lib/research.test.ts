import assert from "node:assert/strict";
import test from "node:test";
import {
  emptySource,
  researchCardStale,
  sourceOnly,
  type ResearchSource,
} from "./research";
const sid = "a".repeat(32);
const claim = {
  claim: "Fixture claim",
  source_id: sid,
  quote: "A sample source quotation.",
};
const source: ResearchSource = {
  ...emptySource(),
  id: sid,
  updated_at: "2026-09-28",
  status: "ready",
  duplicate_of: null,
  publication_unknown: true,
};
test("missing or ineligible research evidence prevents drafting", () => {
  assert.equal(researchCardStale([claim], {}), true);
  assert.equal(researchCardStale([claim], { [sid]: source }), false);
  for (const status of [
    "excluded",
    "stale",
    "conflict",
    "duplicate",
  ] as const) {
    assert.equal(
      researchCardStale([claim], { [sid]: { ...source, status } }),
      true,
    );
  }
  assert.equal(researchCardStale([], {}), false);
});
test("editing source omits server metadata and retains review fields", () => {
  const form = sourceOnly({
    ...source,
    title: "Note",
    caution: "Check facts",
    conflict_with: "b".repeat(32),
  });
  assert.equal(form.caution, "Check facts");
  assert.equal(form.conflict_with, "b".repeat(32));
  assert.equal(form.title, "Note");
  assert.equal("status" in form, false);
  assert.equal("id" in form, false);
});
