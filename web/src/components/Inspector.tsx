import { ChevronRight, ArrowUp, ArrowDown } from "lucide-react";
import { Project, Scene } from "@/lib/model";
import { Field, Status } from "./UI";
import MotionControls from "./MotionControls";
export default function Inspector({
  project,
  scene,
  patch,
  change,
  tab,
  onClose,
}: {
  project: Project;
  scene: Scene | undefined;
  patch: (values: Partial<Scene>) => void;
  change: (fn: (p: Project) => Project) => void;
  tab: string;
  onClose: () => void;
}) {
  const style = project.caption_style;
  const caption = (values: Partial<typeof style>) =>
    change((p) => ({ ...p, caption_style: { ...p.caption_style, ...values } }));
  return (
    <aside className="inspector">
      <div className="panel-heading">
        INSPECTOR
        <button
          className="tiny icon"
          aria-label="Tutup inspector"
          onClick={onClose}
        >
          <ChevronRight size={14} />
        </button>
      </div>
      {scene ? (
        <div className="inspector-body">
          <div className="selection-summary">
            <span className="track-marker visual" />
            <div>
              <strong>
                {tab === "caption" ? "Caption" : "Klip visual"} — {scene.name}
              </strong>
              <p className="mono small subtle">
                {(scene.duration / 30).toFixed(2)} detik
              </p>
            </div>
          </div>
          {tab === "caption" || tab === "gaya" ? (
            <>
              <section>
                <h3>TEKS CAPTION</h3>
                <textarea
                  aria-label="Teks caption"
                  maxLength={400}
                  rows={4}
                  value={scene.caption}
                  onChange={(e) => patch({ caption: e.target.value })}
                />
                <p className="hint">
                  Caption per scene. Sesuaikan teks dengan narasi; timing
                  mengikuti durasi scene.
                </p>
              </section>
              <section>
                <h3>GAYA CAPTION</h3>
                <div className="caption-styles">
                  {(["putih", "lime", "bar"] as const).map((key) => (
                    <button
                      key={key}
                      className={style.preset === key ? "selected" : ""}
                      onClick={() => caption({ preset: key })}
                    >
                      <span className={"caption-example " + key}>
                        Satu ide. Satu Short.
                      </span>
                      <small>
                        {key === "putih"
                          ? "Tebal Putih"
                          : key === "lime"
                            ? "Blok Lime"
                            : "Bar Gelap"}
                      </small>
                    </button>
                  ))}
                </div>
                <Field label={`Ukuran · ${style.size} px`}>
                  <input
                    type="range"
                    min="24"
                    max="60"
                    value={style.size}
                    onChange={(e) => caption({ size: +e.target.value })}
                  />
                </Field>
                <Field label={`Posisi vertikal · ${style.position}%`}>
                  <input
                    type="range"
                    min="40"
                    max="90"
                    value={style.position}
                    onChange={(e) => caption({ position: +e.target.value })}
                  />
                </Field>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={style.enabled}
                    onChange={(e) => caption({ enabled: e.target.checked })}
                  />
                  Tampilkan caption
                </label>
                <p className="hint">
                  Maksimal dua baris. Caption terlalu panjang harus diperbaiki
                  sebelum ekspor.
                </p>
              </section>
            </>
          ) : (
            <>
              <section>
                <h3>BINGKAI</h3>
                <div className="segmented">
                  {(["fit", "fill"] as const).map((fit) => (
                    <button
                      key={fit}
                      className={scene.fit === fit ? "selected" : ""}
                      onClick={() => patch({ fit })}
                    >
                      {fit === "fit" ? "Fit" : "Fill"}
                    </button>
                  ))}
                </div>
                <Field label={`Skala · ${Math.round(scene.scale * 100)}%`}>
                  <input
                    type="range"
                    min="1"
                    max="2"
                    step="0.01"
                    value={scene.scale}
                    onChange={(e) => patch({ scale: +e.target.value })}
                  />
                </Field>
                <div className="two-col">
                  <Field label="Posisi X">
                    <input
                      type="number"
                      min="-1080"
                      max="1080"
                      value={scene.x}
                      onChange={(e) =>
                        patch({
                          x: Math.max(-1080, Math.min(1080, +e.target.value)),
                        })
                      }
                    />
                  </Field>
                  <Field label="Posisi Y">
                    <input
                      type="number"
                      min="-1920"
                      max="1920"
                      value={scene.y}
                      onChange={(e) =>
                        patch({
                          y: Math.max(-1920, Math.min(1920, +e.target.value)),
                        })
                      }
                    />
                  </Field>
                </div>
              </section>
              <section>
                <h3>DURASI & TRIM</h3>
                <Field label="Durasi scene (detik)">
                  <input
                    type="number"
                    min="0.3"
                    max="60"
                    step="0.1"
                    value={+(scene.duration / 30).toFixed(2)}
                    onChange={(e) =>
                      patch({
                        duration: Math.max(
                          9,
                          Math.min(1800, Math.round(+e.target.value * 30)),
                        ),
                      })
                    }
                  />
                </Field>
                <Field label="Mulai dari video (detik)">
                  <input
                    type="number"
                    min="0"
                    max="3600"
                    step="0.1"
                    value={+(scene.source_in / 30).toFixed(2)}
                    onChange={(e) =>
                      patch({
                        source_in: Math.max(
                          0,
                          Math.min(108000, Math.round(+e.target.value * 30)),
                        ),
                      })
                    }
                  />
                </Field>
                <div className="two-col">
                  <button
                    onClick={() =>
                      change((p) => {
                        const list = [...p.scenes],
                          i = list.findIndex((s) => s.id === scene.id);
                        if (i < 1) return p;
                        [list[i - 1], list[i]] = [list[i], list[i - 1]];
                        return { ...p, scenes: list };
                      })
                    }
                  >
                    <ArrowUp size={14} />
                    Naik
                  </button>
                  <button
                    onClick={() =>
                      change((p) => {
                        const list = [...p.scenes],
                          i = list.findIndex((s) => s.id === scene.id);
                        if (i >= list.length - 1) return p;
                        [list[i + 1], list[i]] = [list[i], list[i + 1]];
                        return { ...p, scenes: list };
                      })
                    }
                  >
                    <ArrowDown size={14} />
                    Turun
                  </button>
                </div>
              </section>
              <section>
                <h3>AUDIO</h3>
                <Field
                  label={`Audio klip · ${Math.round(scene.source_volume * 100)}%`}
                >
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step=".01"
                    value={scene.source_volume}
                    onChange={(e) => patch({ source_volume: +e.target.value })}
                  />
                </Field>
                <Field
                  label={`Narasi · ${Math.round(project.narration_volume * 100)}%`}
                >
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step=".01"
                    value={project.narration_volume}
                    onChange={(e) =>
                      change((p) => ({
                        ...p,
                        narration_volume: +e.target.value,
                      }))
                    }
                  />
                </Field>
                <Field
                  label={`Musik · ${Math.round(project.music_volume * 100)}%`}
                >
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step=".01"
                    value={project.music_volume}
                    onChange={(e) =>
                      change((p) => ({ ...p, music_volume: +e.target.value }))
                    }
                  />
                </Field>
              </section>
            </>
          )}
          <section>
            <Field label="Gerak seluruh proyek">
              <select
                value={project.motion_mode ?? "gentle"}
                onChange={(e) =>
                  change((p) => ({
                    ...p,
                    motion_mode: e.target.value as "gentle" | "none",
                  }))
                }
              >
                <option value="gentle">Preset gerak ringan</option>
                <option value="none">Tanpa gerak</option>
              </select>
            </Field>
            <MotionControls
              value={scene.motion}
              duration={scene.duration}
              onChange={(motion) => patch({ motion })}
            />
          </section>
        </div>
      ) : (
        <p className="panel-empty">
          Pilih atau tambahkan scene untuk mengedit.
        </p>
      )}
    </aside>
  );
}
