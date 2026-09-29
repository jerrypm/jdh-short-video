import { useEffect, useRef, useState } from "react";
import { request } from "@/lib/api";
import { timecode, type Project } from "@/lib/model";
import { assertSavedSnapshot, assertUnchanged } from "@/lib/storyboard";
import {
  defaultQualitySettings,
  delay,
  editorialRequest,
  initialSelection,
  type Editorial,
  type QualityJob,
  type QualityReport,
  type QualitySelection,
  type QualitySettings,
} from "@/lib/quality";
import { Field, Busy } from "./UI";

// Keep incomplete keystrokes local so typing 65 does not clamp the first 6 to 40.
function QualityNumber({
  value,
  min,
  max,
  step = 1,
  disabled,
  onEditing,
  onCommit,
}: {
  value: number;
  min: number;
  max: number;
  step?: number;
  disabled?: boolean;
  onEditing: () => void;
  onCommit: (value: number) => void;
}) {
  const [text, setText] = useState(String(value));
  useEffect(() => setText(String(value)), [value]);
  function commit() {
    const parsed = text.trim() ? Number(text) : NaN;
    const next = Number.isFinite(parsed)
      ? Math.max(min, Math.min(max, step === 1 ? Math.round(parsed) : parsed))
      : value;
    setText(String(next));
    if (next !== value) onCommit(next);
  }
  return (
    <input
      type="number"
      min={min}
      max={max}
      step={step}
      disabled={disabled}
      value={text}
      onChange={(event) => {
        setText(event.target.value);
        onEditing();
      }}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.currentTarget.blur();
      }}
    />
  );
}

export default function QualityPanel({
  project,
  current,
  flush,
  preset,
  report,
  onReport,
  onApplied,
  onSettings,
  onDirty,
  onBusy,
}: {
  project: Project;
  current: () => Project;
  flush: () => Promise<void>;
  preset: string;
  report: QualityReport | null;
  onReport: (value: QualityReport | null) => void;
  onApplied: (project: Project) => void;
  onSettings: (settings: QualitySettings) => void;
  onDirty: (dirty: boolean) => void;
  onBusy: (busy: boolean) => void;
}) {
  const [selection, setSelection] = useState<QualitySelection>(() =>
    initialSelection(project),
  );
  const [editorial, setEditorial] = useState<Editorial | null>(null);
  const [summary, setSummary] = useState<{ frames: number } | null>(null);
  const [working, setWorking] = useState("");
  const [error, setError] = useState("");
  const [dirty, setDirty] = useState(false);
  const controller = useRef<AbortController | null>(null),
    base = useRef(""),
    reviewed = useRef(""),
    pendingJob = useRef(""),
    lock = useRef(false),
    mounted = useRef(true);
  const settings = project.quality_settings ?? defaultQualitySettings();
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      controller.current?.abort();
    };
  }, []);
  useEffect(() => {
    setSummary(null);
    reviewed.current = "";
  }, [report?.id, preset]);
  function invalidateDraft() {
    setSummary(null);
    reviewed.current = "";
    setDirty(true);
    onDirty(true);
  }
  function patch(value: Partial<QualitySelection>) {
    setSelection((old) => ({ ...old, ...value }));
    invalidateDraft();
  }
  async function run(
    label: string,
    action: (signal: AbortSignal) => Promise<void>,
  ) {
    if (lock.current) return;
    lock.current = true;
    setWorking(label);
    onBusy(true);
    setError("");
    const abort = new AbortController();
    controller.current = abort;
    try {
      await action(abort.signal);
    } catch (e) {
      if (mounted.current && (e as Error).name !== "AbortError")
        setError((e as Error).message);
    } finally {
      if (pendingJob.current) {
        await request(
          `/jobs/${pendingJob.current}/cancel`,
          "POST",
          {},
          AbortSignal.timeout(3000),
        ).catch(() => undefined);
        pendingJob.current = "";
      }
      lock.current = false;
      if (mounted.current) {
        setWorking("");
        onBusy(false);
      }
    }
  }
  function analyze() {
    void run("Memeriksa media, audio dan caption…", async (signal) => {
      onReport(null);
      setEditorial(null);
      setSummary(null);
      reviewed.current = "";
      await flush();
      base.current = JSON.stringify(current());
      const saved = await request<Project>(
        `/projects/${project.id}`,
        "GET",
        undefined,
        signal,
      );
      assertUnchanged(current(), base.current);
      assertSavedSnapshot(current(), saved);
      let job = await request<QualityJob>(
        `/quality/${project.id}/checks`,
        "POST",
        { revision: saved.revision, preset },
        signal,
      );
      pendingJob.current = job.id;
      while (["queued", "running"].includes(job.status)) {
        await delay(signal);
        job = await request<QualityJob>(
          `/jobs/${job.id}`,
          "GET",
          undefined,
          signal,
        );
      }
      pendingJob.current = "";
      signal.throwIfAborted();
      if (job.status !== "completed" || !job.result)
        throw new Error(job.message);
      assertUnchanged(current(), base.current);
      onReport(job.result);
      // Preserve pending manual metadata edits when only the export preset changes.
      if (!dirty) setSelection(initialSelection(saved));
    });
  }
  function review() {
    void run("Memeriksa usulan perubahan…", async (signal) => {
      setSummary(null);
      reviewed.current = "";
      assertUnchanged(current(), base.current);
      const result = await request<{ frames: number }>(
        `/quality/${project.id}/${report!.id}/preview`,
        "POST",
        selection,
        signal,
      );
      assertUnchanged(current(), base.current);
      signal.throwIfAborted();
      reviewed.current = JSON.stringify(selection);
      setSummary(result);
    });
  }
  function apply() {
    void run("Menyimpan perubahan yang ditinjau…", async (signal) => {
      assertUnchanged(current(), base.current);
      if (!summary || reviewed.current !== JSON.stringify(selection))
        throw new Error("Periksa kembali usulan setelah edit.");
      const saved = await request<Project>(
        `/quality/${project.id}/${report!.id}/apply`,
        "POST",
        selection,
        signal,
      );
      assertUnchanged(current(), base.current);
      onApplied(saved);
      onReport(null);
      setSummary(null);
      setEditorial(null);
      setDirty(false);
      onDirty(false);
      setSelection(initialSelection(saved));
    });
  }
  function nanoReview() {
    void run("Meminta saran Nano lokal…", async (signal) => {
      assertUnchanged(current(), base.current);
      setEditorial(null);
      const result = await editorialRequest(
        project.id,
        report!.id,
        crypto.randomUUID(),
        signal,
      );
      assertUnchanged(current(), base.current);
      signal.throwIfAborted();
      setEditorial(result);
    });
  }
  return (
    <div className="quality-panel">
      <h3>Pemeriksaan terukur</h3>
      <p className="hint">
        Media, durasi, level sampel audio dan batas teks. Ambang berikut adalah
        pengaturan produk, bukan aturan YouTube.
      </p>
      <details>
        <summary>Ambang pemeriksaan</summary>
        <div className="two-col">
          {(
            [
              ["long_silence_seconds", "Jeda panjang (detik)", 0.5, 10, 0.5],
              ["silence_dbfs", "Ambang sunyi (dBFS)", -60, -20, 1],
              ["peak_warning_dbfs", "Peringatan puncak (dBFS)", -6, 0, 0.1],
              ["caption_cps", "Caption (karakter/detik)", 5, 40, 1],
            ] as const
          ).map(([key, label, min, max, step]) => (
            <Field key={key} label={label}>
              <QualityNumber
                min={min}
                max={max}
                step={step}
                disabled={!!working || dirty}
                value={settings[key]}
                onEditing={() => {
                  onReport(null);
                  setEditorial(null);
                  setSummary(null);
                }}
                onCommit={(value) =>
                  onSettings({
                    ...settings,
                    [key]: value,
                  })
                }
              />
            </Field>
          ))}
        </div>
      </details>
      <button disabled={!!working} onClick={analyze}>
        {report ? "Periksa ulang" : "Periksa Shorts"}
      </button>
      {working && (
        <div className="quality-working">
          <Busy text={working} />
          <button onClick={() => controller.current?.abort()}>
            Batalkan proses
          </button>
        </div>
      )}
      {report && (
        <>
          <p className="small subtle">
            Revisi {report.base_revision} · {report.output.width}×
            {report.output.height} · {report.output.seconds.toFixed(2)} dtk · 30
            fps (rencana output)
          </p>
          {!report.findings.length && (
            <p className="success-line">
              Tidak ditemukan masalah pada pemeriksaan ini.
            </p>
          )}
          <div className="quality-findings">
            {report.findings.map((finding, index) => (
              <article
                key={index}
                className={"quality-finding " + finding.severity}
              >
                <strong>
                  {finding.severity === "error"
                    ? "Perlu diperbaiki"
                    : finding.severity === "warning"
                      ? "Perlu ditinjau"
                      : "Catatan"}{" "}
                  ·{" "}
                  {finding.scene_id
                    ? report.rows.find((r) => r.scene_id === finding.scene_id)
                        ?.name
                    : "Proyek"}
                </strong>
                <span className="mono small">
                  {timecode(finding.start_frame)} –{" "}
                  {timecode(finding.end_frame)}
                </span>
                <p>{finding.message}</p>
              </article>
            ))}
          </div>
          <details>
            <summary>Batas pemeriksaan</summary>
            {report.limitations.map((text) => (
              <p key={text} className="hint">
                {text}
              </p>
            ))}
          </details>
          <h3>Saran editorial · Gemini Nano lokal</h3>
          <p className="hint">
            Masukan AI berdasarkan naskah dan deskripsi visual pengguna. Tidak
            melihat frame atau mendengar audio. Saran ini bukan kesalahan
            teknis.
          </p>
          <button
            disabled={!!working || project.language !== "en"}
            onClick={nanoReview}
          >
            Minta saran Nano lokal
          </button>
          {project.language !== "en" && (
            <p className="hint">
              Review Nano tersedia untuk English; metadata manual tetap bisa
              diedit.
            </p>
          )}
          {editorial && (
            <div className="editorial-result">
              <strong>{editorial.title}</strong>
              <p>{editorial.description}</p>
              <button
                disabled={!!working}
                onClick={() =>
                  patch({
                    upload: {
                      title: editorial.title,
                      description: editorial.description,
                    },
                  })
                }
              >
                Gunakan sebagai usulan metadata
              </button>
              {editorial.notes.map((note, index) => (
                <article key={index} className="quality-finding">
                  <strong>Saran · {note.category}</strong>
                  <span className="mono small">
                    {timecode(note.start_frame)} – {timecode(note.end_frame)}
                  </span>
                  <p>{note.suggestion}</p>
                  <p className="subtle">Alasan: {note.reason}</p>
                </article>
              ))}
            </div>
          )}
        </>
      )}
      <h3>Metadata unggah</h3>
      <fieldset disabled={!!working} className="pacing-fields">
        <Field label="Judul video">
          <input
            value={selection.upload.title}
            maxLength={100}
            onChange={(e) =>
              patch({ upload: { ...selection.upload, title: e.target.value } })
            }
          />
        </Field>
        <Field label="Deskripsi video">
          <textarea
            value={selection.upload.description}
            rows={4}
            maxLength={5000}
            onChange={(e) =>
              patch({
                upload: { ...selection.upload, description: e.target.value },
              })
            }
          />
        </Field>
        {report && (
          <details>
            <summary>Usulkan perbaikan teknis</summary>
            <div className="two-col">
              <Field label="Posisi caption (%)">
                <QualityNumber
                  min={40}
                  max={90}
                  value={selection.caption_position}
                  onEditing={invalidateDraft}
                  onCommit={(value) =>
                    patch({
                      caption_position: value,
                    })
                  }
                />
              </Field>
              <Field label="Volume narasi (%)">
                <QualityNumber
                  min={0}
                  max={100}
                  value={Math.round(selection.narration_volume * 100)}
                  onEditing={invalidateDraft}
                  onCommit={(value) =>
                    patch({
                      narration_volume: value / 100,
                    })
                  }
                />
              </Field>
              <Field label="Volume musik (%)">
                <QualityNumber
                  min={0}
                  max={100}
                  value={Math.round(selection.music_volume * 100)}
                  onEditing={invalidateDraft}
                  onCommit={(value) =>
                    patch({
                      music_volume: value / 100,
                    })
                  }
                />
              </Field>
            </div>
            <p className="hint">
              Gain lebih rendah tidak memulihkan audio yang sudah terdistorsi.
              Perubahan caption tidak mengubah naskah/audio.
            </p>
            {report.rows.map((row) => {
              const edit = selection.scenes.find(
                (s) => s.scene_id === row.scene_id,
              );
              const change = (value: Partial<NonNullable<typeof edit>>) =>
                patch({
                  scenes: selection.scenes.map((s) =>
                    s.scene_id === row.scene_id ? { ...s, ...value } : s,
                  ),
                });
              return (
                <article key={row.scene_id} className="quality-finding">
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={!!edit}
                      onChange={(e) =>
                        patch({
                          scenes: e.target.checked
                            ? [
                                ...selection.scenes,
                                {
                                  scene_id: row.scene_id,
                                  duration: row.suggested_duration,
                                  caption: row.suggested_caption,
                                },
                              ]
                            : selection.scenes.filter(
                                (s) => s.scene_id !== row.scene_id,
                              ),
                        })
                      }
                    />
                    Ubah {row.name}
                  </label>
                  {edit && (
                    <>
                      <Field label={`Durasi ${row.name} (frame)`}>
                        <QualityNumber
                          min={9}
                          max={1800}
                          value={edit.duration}
                          onEditing={invalidateDraft}
                          onCommit={(value) =>
                            change({
                              duration: value,
                            })
                          }
                        />
                      </Field>
                      <Field label={`Caption ${row.name}`}>
                        <textarea
                          value={edit.caption}
                          maxLength={400}
                          rows={2}
                          onChange={(e) => change({ caption: e.target.value })}
                        />
                      </Field>
                      <p className="hint">
                        Minimum audio terukur: {row.minimum_frames} frame. Semua
                        ucapan harus dipertahankan.
                      </p>
                    </>
                  )}
                </article>
              );
            })}
          </details>
        )}
      </fieldset>
      {dirty && (
        <>
          <p className="hint">
            Usulan belum disimpan. Periksa perubahan lalu terapkan sebelum
            mengekspor.
          </p>
          <div className="quality-actions">
            <button disabled={!!working || !report} onClick={review}>
              Tinjau perubahan
            </button>
            <button
              disabled={!!working}
              onClick={() => {
                setSelection(initialSelection(current()));
                setDirty(false);
                onDirty(false);
                setSummary(null);
                reviewed.current = "";
              }}
            >
              Batalkan usulan
            </button>
          </div>
        </>
      )}
      {summary && (
        <div className="quality-summary">
          <strong>Perubahan siap ditinjau</strong>
          <p>
            Judul: {project.upload?.title || project.name} →{" "}
            {selection.upload.title || project.name}
          </p>
          <p>
            Deskripsi: {project.upload?.description || "(kosong)"} →{" "}
            {selection.upload.description || "(kosong)"}
          </p>
          <p>
            Caption: {project.caption_style.position}% →{" "}
            {selection.caption_position}%; narasi:{" "}
            {Math.round(project.narration_volume * 100)}% →{" "}
            {Math.round(selection.narration_volume * 100)}%; musik:{" "}
            {Math.round(project.music_volume * 100)}% →{" "}
            {Math.round(selection.music_volume * 100)}%.
          </p>
          {selection.scenes.map((edit) => (
            <p key={edit.scene_id}>
              {report?.rows.find((r) => r.scene_id === edit.scene_id)?.name}:{" "}
              {report?.rows.find((r) => r.scene_id === edit.scene_id)?.duration}{" "}
              → {edit.duration} frame; caption:{" "}
              {project.scenes.find((scene) => scene.id === edit.scene_id)
                ?.caption || "(kosong)"}{" "}
              → {edit.caption || "(kosong)"}
            </p>
          ))}
          <p>
            Total baru {timecode(summary.frames)}. Pemeriksaan harus diulang
            setelah diterapkan. Undo tersedia di editor.
          </p>
          <button disabled={!!working} className="primary" onClick={apply}>
            Terapkan perubahan yang ditinjau
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
    </div>
  );
}
