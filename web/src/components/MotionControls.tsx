import {
  defaultMotion,
  defaultCallout,
  frameRange,
  visualPresets,
  textPresets,
  type FrameRange,
  type Motion,
  type TextMotion,
} from "@/lib/motion";
import { Field } from "./UI";

function RangeControls({
  value,
  duration,
  onChange,
}: {
  value: FrameRange;
  duration: number;
  onChange: (value: FrameRange) => void;
}) {
  const range = frameRange(value, duration);
  return (
    <>
      <div className="two-col">
        <Field label="Mulai (frame)">
          <input
            type="number"
            min={0}
            max={duration - 2}
            value={value.start_frame}
            onChange={(e) => {
              const start = Math.max(
                0,
                Math.min(duration - 2, Math.round(+e.target.value)),
              );
              onChange({
                start_frame: start,
                end_frame:
                  value.end_frame === null
                    ? null
                    : Math.max(start + 1, value.end_frame),
              });
            }}
          />
        </Field>
        <Field label="Akhir (kosong = akhir scene)">
          <input
            type="number"
            min={1}
            max={duration - 1}
            value={value.end_frame ?? ""}
            onChange={(e) =>
              onChange({
                ...value,
                end_frame:
                  e.target.value === ""
                    ? null
                    : Math.max(
                        value.start_frame + 1,
                        Math.min(duration - 1, Math.round(+e.target.value)),
                      ),
              })
            }
          />
        </Field>
      </div>
      <p className="hint">
        Rentang efektif {range[0]}–{range[1]} frame; menyesuaikan jika scene
        dipendekkan.
      </p>
    </>
  );
}
function TextControls({
  value,
  duration,
  onChange,
  label,
}: {
  value: TextMotion;
  duration: number;
  onChange: (value: TextMotion) => void;
  label: string;
}) {
  return (
    <>
      <Field label={label}>
        <select
          value={value.preset}
          onChange={(e) =>
            onChange({
              ...value,
              preset: e.target.value as TextMotion["preset"],
            })
          }
        >
          {Object.entries(textPresets).map(([key, name]) => (
            <option key={key} value={key}>
              {name}
            </option>
          ))}
        </select>
      </Field>
      {value.preset !== "none" && (
        <RangeControls
          value={value}
          duration={duration}
          onChange={(range) => onChange({ ...value, ...range })}
        />
      )}
    </>
  );
}
export default function MotionControls({
  value,
  duration,
  onChange,
}: {
  value?: Motion;
  duration: number;
  onChange: (value: Motion) => void;
}) {
  const motion = value ?? defaultMotion(),
    visual = motion.visual,
    callout = motion.callout;
  return (
    <details className="motion-controls">
      <summary>Animasi & callout</summary>
      <Field label="Gerak visual">
        <select
          value={visual.preset}
          onChange={(e) =>
            onChange({
              ...motion,
              visual: {
                ...visual,
                preset: e.target.value as typeof visual.preset,
              },
            })
          }
        >
          {Object.entries(visualPresets).map(([key, name]) => (
            <option key={key} value={key}>
              {name}
            </option>
          ))}
        </select>
      </Field>
      {visual.preset !== "none" && (
        <>
          <Field
            label={`Intensitas ringan · ${Math.round(visual.amount * 100)}%`}
          >
            <input
              type="range"
              min={0}
              max={0.12}
              step={0.01}
              value={visual.amount}
              onChange={(e) =>
                onChange({
                  ...motion,
                  visual: { ...visual, amount: +e.target.value },
                })
              }
            />
          </Field>
          <div className="two-col">
            {(["focus_x", "focus_y"] as const).map((key) => (
              <Field
                key={key}
                label={`Fokus ${key === "focus_x" ? "X" : "Y"} · ${Math.round(visual[key] * 100)}%`}
              >
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={visual[key]}
                  onChange={(e) =>
                    onChange({
                      ...motion,
                      visual: { ...visual, [key]: +e.target.value },
                    })
                  }
                />
              </Field>
            ))}
          </div>
          <Field label="Kurva gerak">
            <select
              value={visual.easing}
              onChange={(e) =>
                onChange({
                  ...motion,
                  visual: {
                    ...visual,
                    easing: e.target.value as typeof visual.easing,
                  },
                })
              }
            >
              <option value="smoothstep">Lembut</option>
              <option value="linear">Linear</option>
            </select>
          </Field>
          <RangeControls
            value={visual}
            duration={duration}
            onChange={(range) =>
              onChange({ ...motion, visual: { ...visual, ...range } })
            }
          />
          <p className="hint">
            Gerak diterapkan pada bingkai visual, termasuk area kosong pada Fit.
            Periksa posisi subjek di awal dan akhir.
          </p>
        </>
      )}
      <TextControls
        label="Animasi caption"
        value={motion.caption}
        duration={duration}
        onChange={(caption) => onChange({ ...motion, caption })}
      />
      <label className="check">
        <input
          type="checkbox"
          checked={!!callout}
          onChange={(e) =>
            onChange({
              ...motion,
              callout: e.target.checked ? defaultCallout() : null,
            })
          }
        />
        Tampilkan callout
      </label>
      {callout && (
        <>
          <Field label="Teks callout">
            <textarea
              rows={2}
              maxLength={120}
              value={callout.text}
              onChange={(e) =>
                onChange({
                  ...motion,
                  callout: { ...callout, text: e.target.value },
                })
              }
            />
          </Field>
          <div className="two-col">
            {(
              [
                ["x", "Kotak X", 65, 1015 - callout.width],
                ["y", "Kotak Y", 135, callout.entrance.preset === "slide_up" ? 1400 : 1450],
                ["width", "Lebar kotak", 160, Math.min(800, 1015 - callout.x)],
                ["size", "Ukuran teks", 24, 48],
                ["target_x", "Titik tujuan X", 65, 1015],
                ["target_y", "Titik tujuan Y", 135, callout.entrance.preset === "slide_up" ? 1564 : 1612],
              ] as const
            ).map(([key, label, min, max]) => (
              <Field key={key} label={label}>
                <input
                  type="number"
                  min={min}
                  max={max}
                  value={callout[key]}
                  onChange={(e) =>
                    onChange({
                      ...motion,
                      callout: {
                        ...callout,
                        [key]: Math.max(
                          min,
                          Math.min(max, Math.round(+e.target.value)),
                        ),
                      },
                    })
                  }
                />
              </Field>
            ))}
          </div>
          <TextControls
            label="Animasi callout"
            value={callout.entrance}
            duration={duration}
            onChange={(entrance) =>
              onChange({
                ...motion,
                callout: {
                  ...callout,
                  y: Math.min(callout.y, entrance.preset === "slide_up" ? 1400 : 1450),
                  target_y: Math.min(callout.target_y, entrance.preset === "slide_up" ? 1564 : 1612),
                  entrance,
                },
              })
            }
          />
          <p className="hint">
            Koordinat kanvas 1080×1920. Kotak dan titik tujuan berada di area
            aman yang ditandai.
          </p>
        </>
      )}
    </details>
  );
}
