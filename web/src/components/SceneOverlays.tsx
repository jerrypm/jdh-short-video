import { useEffect, useState } from "react";
import { captionBlob, calloutBlob } from "@/lib/api";
import { defaultMotion, evaluateText } from "@/lib/motion";
import type { Scene, CaptionStyle } from "@/lib/model";

function usePNG(payload: string, kind: "caption" | "callout") {
  const [url, setURL] = useState(""),
    [error, setError] = useState("");
  useEffect(() => {
    const abort = new AbortController();
    let created = "";
    setURL("");
    setError("");
    const value = JSON.parse(payload);
    if (!value) return;
    const work =
      kind === "caption"
        ? captionBlob(value.text, value.style, abort.signal)
        : calloutBlob(value, abort.signal);
    work
      .then((blob) => {
        if (abort.signal.aborted) return;
        created = URL.createObjectURL(blob);
        setURL(created);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => {
      abort.abort();
      if (created) URL.revokeObjectURL(created);
    };
  }, [payload, kind]);
  return { url, error };
}

/** Current and next scene stay mounted so text assets are ready at a cut.
 * Frame updates only change CSS; they never request new PNGs or touch audio.
 */
export default function SceneOverlays({
  scene,
  style,
  frame,
  active,
  enabled,
}: {
  scene: Scene;
  style: CaptionStyle;
  frame: number;
  active: boolean;
  enabled: boolean;
}) {
  const motion = scene.motion ?? defaultMotion();
  const caption = usePNG(
    JSON.stringify(
      scene.caption && style.enabled ? { text: scene.caption, style } : null,
    ),
    "caption",
  );
  const callout = usePNG(JSON.stringify(motion.callout), "callout");
  const text = evaluateText(motion.caption, frame, scene.duration, enabled);
  const label = motion.callout
    ? evaluateText(motion.callout.entrance, frame, scene.duration, enabled)
    : { opacity: 0, y: 0 };
  return (
    <>
      {caption.url && (
        <img
          className="caption-overlay"
          src={caption.url}
          alt=""
          style={{
            visibility: active ? "visible" : "hidden",
            opacity: text.opacity,
            transform: `translateY(${(text.y / 1920) * 100}%)`,
          }}
        />
      )}
      {callout.url && (
        <img
          className="caption-overlay callout-overlay"
          src={callout.url}
          alt=""
          style={{
            visibility: active ? "visible" : "hidden",
            opacity: label.opacity,
            transform: `translateY(${(label.y / 1920) * 100}%)`,
          }}
        />
      )}
      {active && (caption.error || callout.error) && (
        <p className="overlay-error" role="alert">
          {caption.error || callout.error}
        </p>
      )}
    </>
  );
}
