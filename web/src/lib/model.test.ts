import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildScenes,
  newScene,
  splitScene,
  timecode,
  sceneRanges,
  removeScene,
} from "./model";
import { resolveTimelineSnap } from "../vendor/opencut/resolve";
test("deleting a scene selects its neighbour at the new timeline position", () => {
  const first = newScene("First", 90);
  const middle = { ...newScene("Middle", 150), audio_id: "original-voice" };
  const last = newScene("Last", 120);
  const scenes = [first, middle, last];
  const result = removeScene(scenes, middle.id)!;
  assert.deepEqual(result.scenes, [first, last]);
  assert.equal(result.selected, last.id);
  assert.equal(result.frame, 90);
  assert.equal(scenes[1].audio_id, "original-voice");
  assert.equal(scenes.length, 3);
  assert.deepEqual(removeScene(scenes, last.id), {
    scenes: [first, middle], selected: middle.id, frame: 90,
  });
  assert.deepEqual(removeScene([first], first.id), {
    scenes: [], selected: "", frame: 0,
  });
  assert.equal(removeScene(scenes, "missing"), null);
});
test("frame timeline split preserves duration and source offset", () => {
  const source = { ...newScene("Video", 300), source_in: 60 };
  const parts = splitScene([source], source.id, 90);
  assert.equal(parts.length, 2);
  assert.equal(parts[0].duration, 90);
  assert.equal(parts[1].source_in, 150);
  assert.equal(sceneRanges(parts).at(-1)?.end, 300);
});
test("splitting cannot silently cut narration", () => {
  const source = { ...newScene("Narration", 300), audio_id: "voice" };
  assert.equal(splitScene([source], source.id, 90).length, 1);
});
test("snapping uses nearest upstream point within threshold", () => {
  const result = resolveTimelineSnap({
    targetTime: 88,
    snapPoints: [
      { time: 90, type: "element-start" },
      { time: 110, type: "element-end" },
    ],
    maxSnapDistance: 10,
  });
  assert.equal(result.snappedTime, 90);
});
test("manual storyboard preserves script and makes no AI/caption claims", () => {
  const result = buildScenes("First idea. Second scene. Last line.", 30);
  assert.equal(result.length, 3);
  assert.equal(result[0].narration, "First idea.");
  assert.equal(result[0].caption, "");
  assert.equal(
    result.reduce((n, s) => n + s.duration, 0),
    900,
  );
  assert.equal(timecode(915), "00:30:15");
});
