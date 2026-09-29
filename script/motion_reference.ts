// QA runner for the exact evaluator imported by React, not a duplicate formula.
import { readFileSync } from "node:fs";
import {
  evaluateVisual,
  evaluateText,
  sourceGeometry,
} from "../web/src/lib/motion";
const cases = JSON.parse(readFileSync(0, "utf8"));
process.stdout.write(
  JSON.stringify(
    cases.map((item: any) => ({
      visual: evaluateVisual(
        item.motion.visual,
        item.frame,
        item.duration,
        item.enabled,
      ),
      caption: evaluateText(
        item.motion.caption,
        item.frame,
        item.duration,
        item.enabled,
      ),
      callout: item.motion.callout
        ? evaluateText(
            item.motion.callout.entrance,
            item.frame,
            item.duration,
            item.enabled,
          )
        : null,
      geometry: item.asset
        ? sourceGeometry(
            item.asset.width,
            item.asset.height,
            item.fit,
            item.scale,
            item.x,
            item.y,
          )
        : null,
    })),
  ),
);
