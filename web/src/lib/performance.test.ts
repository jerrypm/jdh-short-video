import test from "node:test";
import assert from "node:assert/strict";
import {
  emptyMeasurement,
  measurementOnly,
  metricText,
  numericMetric,
  type PerformanceRecord,
} from "./performance";

test("missing metrics remain distinct from actual zero, including percent above 100", () => {
  assert.equal(numericMetric(""), null);
  assert.equal(numericMetric("0"), 0);
  assert.equal(numericMetric("120.5"), 120.5);
  assert.equal(metricText(null), "—");
  assert.equal(metricText(0), "0");
  assert.throws(() => numericMetric("Infinity"));
  assert.throws(() => numericMetric("-1"));
  assert.throws(() => numericMetric("1,000"));
});
test("editing a snapshot preserves provenance and missing values without sending persistence fields", () => {
  const row: PerformanceRecord = {
    ...emptyMeasurement(),
    id: "a".repeat(32),
    origin: "csv",
    imported_at: "today",
    included: false,
    exclusion_reason: "fixture",
    engaged_views: 0,
  };
  const editable = measurementOnly(row);
  assert.equal(editable.engaged_views, 0);
  assert.equal(editable.likes, null);
  assert.equal(editable.captured_at, row.captured_at);
  assert.equal("included" in editable, false);
  assert.equal("id" in editable, false);
  assert.equal("origin" in editable, false);
});
