import { test } from "node:test";
import assert from "node:assert/strict";
import {
  defaultMotion,
  evaluateVisual,
  evaluateText,
  frameRange,
  sourceGeometry,
} from "./motion";
import { assertSavedSnapshot } from "./storyboard";
import { newScene, type Project } from "./model";

test("legacy defaults and reduced motion keep static visuals and text", () => {
  const motion = defaultMotion();
  assert.deepEqual(evaluateVisual(motion.visual, 3, 9), {
    scale: 1,
    x: 0,
    y: 0,
  });
  motion.visual.preset = "zoom_out";
  motion.caption.preset = "slide_up";
  assert.deepEqual(evaluateVisual(motion.visual, 3, 9, false), {
    scale: 1,
    x: 0,
    y: 0,
  });
  assert.deepEqual(evaluateText(motion.caption, 3, 9, false), {
    opacity: 1,
    y: 0,
  });
});
test("entrance endpoints and clipped frame ranges are deterministic after a seek", () => {
  const motion = defaultMotion();
  motion.caption.preset = "slide_up";
  assert.deepEqual(evaluateText(motion.caption, 0, 9), { opacity: 0, y: 48 });
  assert.deepEqual(evaluateText(motion.caption, 4, 9), { opacity: 0.5, y: 24 });
  assert.deepEqual(evaluateText(motion.caption, 8, 9), { opacity: 1, y: 0 });
  assert.deepEqual(frameRange({ start_frame: 100, end_frame: 120 }, 9), [7, 8]);
  assert.deepEqual(evaluateText(motion.caption, 0, 9), { opacity: 0, y: 48 });
});
test("fit/fill geometry scales the source before canvas clipping", () => {
  const fit = sourceGeometry(1920, 1080, "fit", 1, 0, 0);
  assert.equal(fit.width, "100%");
  assert.equal(fit.height, "31.640625%");
  const fill = sourceGeometry(1080, 1920, "fill", 2, 108, -192);
  assert.deepEqual(fill, {
    width: "200%",
    height: "200%",
    left: "-40%",
    top: "-60%",
  });
});
test("saved legacy project can acquire motion defaults without a stale-review error", () => {
  const project = {
    id: "a".repeat(32),
    scenes: [newScene()],
    revision: 0,
    updated_at: "",
  } as Project;
  const saved = {
    ...project,
    motion_mode: "gentle" as const,
    scenes: project.scenes.map((s) => ({ ...s, motion: defaultMotion() })),
  };
  assert.doesNotThrow(() => assertSavedSnapshot(project, saved));
  saved.scenes[0].motion.visual.preset = "zoom_in";
  assert.throws(() => assertSavedSnapshot(project, saved));
});
