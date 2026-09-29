import { test } from "node:test";
import assert from "node:assert/strict";
import { PreviewMediaController } from "./preview-media";

class MediaDouble extends EventTarget {
  duration = 4.36;
  readyState = 4;
  paused = true;
  volume = 1;
  loop = false;
  seeks: number[] = [];
  plays = 0;
  pauses = 0;
  position = 0;
  rejectPlay?: Error;
  get currentTime() {
    return this.position;
  }
  set currentTime(value: number) {
    this.seeks.push(value);
    this.position = value;
  }
  play() {
    this.plays++;
    this.paused = false;
    return this.rejectPlay
      ? Promise.reject(this.rejectPlay)
      : Promise.resolve();
  }
  pause() {
    this.pauses++;
    this.paused = true;
  }
  controller(errors: string[] = []) {
    return new PreviewMediaController(
      this as unknown as HTMLMediaElement,
      (message) => errors.push(message),
    );
  }
}

test("preview lets coarse WebKit media time run without a seek/play feedback loop", () => {
  const media = new MediaDouble();
  const controller = media.controller();
  for (let frame = 0; frame < 120; frame++) {
    // Media time can lag/repeat between native decoder updates. This must not
    // cause a seek, which stalls the decoder again on the following frame.
    media.position = Math.max(0, Math.floor((frame / 30 - 0.25) * 4) / 4);
    controller.update({ time: frame / 30, playing: true, volume: 1 });
  }
  assert.equal(media.plays, 1);
  assert.deepEqual(media.seeks, []);
});

test("short narration stays silent after EOF until its nine-second scene ends", () => {
  const media = new MediaDouble();
  const controller = media.controller();
  controller.update({ time: 0, playing: true, volume: 1 });
  media.position = media.duration;
  media.paused = true;
  media.dispatchEvent(new Event("ended"));
  for (let frame = 130; frame < 270; frame++) {
    controller.update({ time: frame / 30, playing: true, volume: 1 });
  }
  assert.equal(media.plays, 1);
  assert.deepEqual(media.seeks, []);
  controller.update({ time: 1, playing: false, volume: 1 });
  controller.update({ time: 1, playing: true, volume: 1 });
  assert.equal(
    media.plays,
    2,
    "seeking back and pressing Play intentionally replays",
  );
  assert.equal(media.currentTime, 1);
});

test("pause, seek, trimmed start and resume apply position once per command", () => {
  const media = new MediaDouble();
  const controller = media.controller();
  controller.update({ time: 1.5, playing: true, volume: 0.4 });
  controller.update({ time: 2.1, playing: true, volume: 0 });
  assert.deepEqual(media.seeks, [1.5]);
  assert.equal(media.volume, 0);
  controller.update({ time: 2.1, playing: false, volume: 1 });
  controller.update({ time: 0.8, playing: false, volume: 1 });
  controller.update({ time: 0.8, playing: true, volume: 1 });
  assert.deepEqual(media.seeks, [1.5, 2.1, 0.8]);
  assert.equal(media.plays, 2);
  assert.equal(media.pauses, 1);
});

test("startup latency does not truncate the last syllable, and seeking into a gap stays silent", () => {
  const media = new MediaDouble();
  const controller = media.controller();
  controller.update({ time: 0, playing: true, volume: 1 });
  media.position = 4.1;
  controller.update({ time: 4.4, playing: true, volume: 1 });
  assert.equal(
    media.paused,
    false,
    "let the media clock finish the final syllable",
  );
  controller.update({ time: 6, playing: false, volume: 1 });
  controller.update({ time: 6, playing: true, volume: 1 });
  assert.equal(media.paused, true);
  assert.equal(
    media.plays,
    1,
    "Play in the silent gap must not restart narration",
  );
});

test("loading media starts at latest timeline time once, never after Pause/dispose", () => {
  const media = new MediaDouble();
  media.readyState = 0;
  const controller = media.controller();
  controller.update({ time: 0, playing: true, volume: 1 });
  controller.update({ time: 0.5, playing: true, volume: 1 });
  assert.equal(media.plays, 0);
  media.readyState = 4;
  media.dispatchEvent(new Event("canplay"));
  media.dispatchEvent(new Event("canplay"));
  assert.equal(media.plays, 1);
  assert.deepEqual(media.seeks, [0.5]);
  controller.dispose();
  media.dispatchEvent(new Event("canplay"));
  assert.equal(media.paused, true);
  assert.equal(media.plays, 1);

  const paused = new MediaDouble();
  paused.readyState = 0;
  const pending = paused.controller();
  pending.update({ time: 0, playing: true, volume: 1 });
  pending.update({ time: 0.4, playing: false, volume: 1 });
  paused.readyState = 4;
  paused.dispatchEvent(new Event("canplay"));
  assert.equal(paused.plays, 0);
});

test("preloaded next narration starts once and music loops natively without seeks", () => {
  const next = new MediaDouble();
  const controller = next.controller();
  for (let frame = 0; frame < 270; frame++) {
    controller.update({ time: 0, playing: false, volume: 1 });
  }
  assert.equal(next.plays, 0);
  controller.update({ time: 0, playing: true, volume: 1 });
  assert.equal(next.plays, 1);
  const music = new MediaDouble();
  const loop = music.controller();
  for (let frame = 0; frame < 900; frame++) {
    music.position = (frame / 30) % music.duration;
    loop.update({ time: frame / 30, playing: true, volume: 0.15, loop: true });
  }
  assert.equal(music.loop, true);
  assert.equal(music.plays, 1);
  assert.deepEqual(music.seeks, []);
  loop.update({ time: 10, playing: false, volume: 0.15, loop: true });
  assert.equal(music.currentTime, 10 % music.duration);
});

test("play failures surface once, while stale failures after disposal are ignored", async () => {
  const media = new MediaDouble();
  media.rejectPlay = new Error("decoder failure");
  const errors: string[] = [];
  const controller = media.controller(errors);
  controller.update({ time: 0, playing: true, volume: 1 });
  await Promise.resolve();
  controller.update({ time: 0.1, playing: true, volume: 1 });
  assert.equal(errors.length, 1);
  assert.equal(media.plays, 1);
  controller.dispose();
  media.dispatchEvent(new Event("error"));
  assert.equal(errors.length, 1);
  const stale = media.controller(errors);
  stale.update({ time: 0, playing: true, volume: 1 });
  stale.dispose();
  await Promise.resolve();
  assert.equal(errors.length, 1);
});

test("AI status renders and a delayed UI frame do not restart or seek narration", () => {
  const media = new MediaDouble();
  const controller = media.controller();
  for (const time of [0, 0, 0.03, 0.03, 0.1, 1.2, 1.2, 1.23, 2.5, 2.5, 4]) {
    // Repeated fresh state objects represent unrelated AI progress renders.
    controller.update({ time, playing: true, volume: 1 });
  }
  assert.equal(media.plays, 1);
  assert.deepEqual(media.seeks, []);
  controller.dispose();
  const next = new MediaDouble();
  const nextController = next.controller();
  nextController.update({ time: 0, playing: true, volume: 1 });
  assert.equal(media.paused, true);
  assert.equal(next.plays, 1);
});
