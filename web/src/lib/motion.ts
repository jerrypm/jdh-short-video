export type FrameRange = { start_frame: number; end_frame: number | null };
export type VisualMotion = FrameRange & {
  preset:
    | "none"
    | "zoom_in"
    | "zoom_out"
    | "pan_left"
    | "pan_right"
    | "pan_up"
    | "pan_down";
  amount: number;
  focus_x: number;
  focus_y: number;
  easing: "linear" | "smoothstep";
};
export type TextMotion = FrameRange & {
  preset: "none" | "fade" | "slide_up";
  easing: "linear";
};
export type Callout = {
  text: string;
  x: number;
  y: number;
  width: number;
  size: number;
  target_x: number;
  target_y: number;
  entrance: TextMotion;
};
export type Motion = {
  version: 1;
  visual: VisualMotion;
  caption: TextMotion;
  callout: Callout | null;
};
export const visualPresets: Record<VisualMotion["preset"], string> = {
  none: "Tanpa gerak",
  zoom_in: "Zoom masuk",
  zoom_out: "Zoom keluar",
  pan_left: "Pan kiri",
  pan_right: "Pan kanan",
  pan_up: "Pan atas",
  pan_down: "Pan bawah",
};
export const textPresets: Record<TextMotion["preset"], string> = {
  none: "Tanpa gerak",
  fade: "Fade masuk",
  slide_up: "Slide naik",
};
export const defaultText = (): TextMotion => ({
  preset: "none",
  start_frame: 0,
  end_frame: 12,
  easing: "linear",
});
export const defaultMotion = (): Motion => ({
  version: 1,
  visual: {
    preset: "none",
    amount: 0.06,
    focus_x: 0.5,
    focus_y: 0.5,
    easing: "smoothstep",
    start_frame: 0,
    end_frame: null,
  },
  caption: defaultText(),
  callout: null,
});
export const defaultCallout = (): Callout => ({
  text: "Perhatikan bagian ini",
  x: 100,
  y: 200,
  width: 440,
  size: 36,
  target_x: 540,
  target_y: 600,
  entrance: defaultText(),
});
export function frameRange(
  value: FrameRange,
  duration: number,
): [number, number] {
  const last = Math.max(1, duration - 1);
  const start = Math.min(value.start_frame, last - 1);
  return [start, Math.max(start + 1, Math.min(value.end_frame ?? last, last))];
}
function progress(
  value: FrameRange & { easing: string },
  frame: number,
  duration: number,
) {
  const [start, end] = frameRange(value, duration);
  const p = Math.max(0, Math.min(1, (frame - start) / (end - start)));
  return value.easing === "smoothstep" ? p * p * (3 - 2 * p) : p;
}
export function evaluateVisual(
  value: VisualMotion,
  frame: number,
  duration: number,
  enabled = true,
) {
  if (!enabled || value.preset === "none") return { scale: 1, x: 0, y: 0 };
  const p = progress(value, frame, duration);
  const scale =
    1 +
    value.amount *
      (value.preset === "zoom_in"
        ? p
        : value.preset === "zoom_out"
          ? 1 - p
          : 1);
  let fx = value.focus_x,
    fy = value.focus_y;
  if (["pan_left", "pan_right"].includes(value.preset))
    fx = Math.max(
      0,
      Math.min(1, fx + (p - 0.5) * (value.preset === "pan_right" ? 1 : -1)),
    );
  if (["pan_up", "pan_down"].includes(value.preset))
    fy = Math.max(
      0,
      Math.min(1, fy + (p - 0.5) * (value.preset === "pan_down" ? 1 : -1)),
    );
  return { scale, x: -(scale - 1) * 1080 * fx, y: -(scale - 1) * 1920 * fy };
}
export function evaluateText(
  value: TextMotion,
  frame: number,
  duration: number,
  enabled = true,
) {
  const p =
    enabled && value.preset !== "none" ? progress(value, frame, duration) : 1;
  return {
    opacity: p,
    y: enabled && value.preset === "slide_up" ? 48 * (1 - p) : 0,
  };
}
export function sourceGeometry(
  width: number,
  height: number,
  fit: "fit" | "fill",
  scale: number,
  x: number,
  y: number,
) {
  const factor =
    (fit === "fit" ? Math.min : Math.max)(1080 / width, 1920 / height) * scale;
  const w = width * factor,
    h = height * factor;
  return {
    width: `${(w / 1080) * 100}%`,
    height: `${(h / 1920) * 100}%`,
    left: `${(((1080 - w) / 2 + x) / 1080) * 100}%`,
    top: `${(((1920 - h) / 2 + y) / 1920) * 100}%`,
  };
}
