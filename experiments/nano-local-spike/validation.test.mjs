import test from "node:test";
import assert from "node:assert/strict";
import { validateIdeas } from "./validation.mjs";

const example = () => ({ ideas: [
  { title: "State", hook: "See a counter update." },
  { title: "Layout", hook: "Build a simple grid." },
  { title: "Images", hook: "Fit an image in a card." },
] });
test("accepts a valid three-idea proposal", () => {
  assert.deepEqual(validateIdeas(JSON.stringify(example())), example());
});
test("rejects structured but invalid or executable proposals", () => {
  for (const change of [
    (x) => { x.command = "run"; },
    (x) => { x.ideas[0].path = "/tmp/video"; },
    (x) => { x.ideas[0].hook = " "; },
    (x) => { x.ideas[0].title = "a".repeat(121); },
    (x) => { x.ideas[1].title = " state "; },
    (x) => { x.ideas.pop(); },
    (x) => { x.ideas[0] = null; },
  ]) {
    const value = example();
    change(value);
    assert.throws(() => validateIdeas(JSON.stringify(value)));
  }
  assert.throws(() => validateIdeas("not JSON"));
  assert.throws(() => validateIdeas("null"));
  assert.throws(() => validateIdeas("[]"));
});
