import { useEffect, useRef, useState } from "react";
import { request } from "@/lib/api";
import type { Project } from "@/lib/model";
import { assertSavedSnapshot, assertUnchanged } from "@/lib/storyboard";
import {
  seconds,
  type PacingEdit,
  type PacingProposal,
  type PacingSummary,
} from "@/lib/pacing";
import { Modal, Field, Busy } from "./UI";

export default function PacingReview({
  projectId,
  current,
  flush,
  onApplied,
  onClose,
}: {
  projectId: string;
  current: () => Project;
  flush: () => Promise<void>;
  onApplied: (project: Project) => void;
  onClose: () => void;
}) {
  const [proposal, setProposal] = useState<PacingProposal | null>(null);
  const [edits, setEdits] = useState<PacingEdit[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [summary, setSummary] = useState<PacingSummary | null>(null);
  const [working, setWorking] = useState("");
  const [error, setError] = useState("");
  const mounted = useRef(false),
    lock = useRef(false),
    base = useRef(""),
    reviewed = useRef("");
  const abort = useRef<AbortController | null>(null);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      abort.current?.abort();
    };
  }, []);
  function invalidate() {
    setSummary(null);
    reviewed.current = "";
  }
  function patch(id: string, value: Partial<PacingEdit>) {
    invalidate();
    setEdits((items) =>
      items.map((item) =>
        item.scene_id === id ? { ...item, ...value } : item,
      ),
    );
  }
  function selection() {
    return { edits: edits.filter((item) => selected.includes(item.scene_id)) };
  }
  async function run(
    phase: string,
    action: (signal: AbortSignal) => Promise<void>,
  ) {
    if (lock.current) return;
    lock.current = true;
    setWorking(phase);
    setError("");
    const controller = new AbortController();
    abort.current = controller;
    try {
      await action(controller.signal);
    } catch (e) {
      if (mounted.current && (e as Error).name !== "AbortError")
        setError((e as Error).message);
    } finally {
      lock.current = false;
      if (mounted.current) setWorking("");
    }
  }
  function analyze() {
    void run("Mengukur audio lokal…", async (signal) => {
      invalidate();
      setProposal(null);
      await flush();
      base.current = JSON.stringify(current());
      const saved = await request<Project>(
        `/projects/${projectId}`,
        "GET",
        undefined,
        signal,
      );
      assertUnchanged(current(), base.current);
      assertSavedSnapshot(current(), saved);
      const result = await request<PacingProposal>(
        `/pacing/${projectId}/analyze`,
        "POST",
        { revision: saved.revision },
        signal,
      );
      assertUnchanged(current(), base.current);
      if (!mounted.current) return;
      setProposal(result);
      setEdits(
        result.rows.map((row) => ({
          scene_id: row.scene_id,
          duration: row.duration,
          caption: row.caption.text,
        })),
      );
      setSelected(
        result.rows
          .filter((row) => !row.errors.length)
          .map((row) => row.scene_id),
      );
    });
  }
  function validate() {
    void run("Memeriksa perubahan…", async (signal) => {
      invalidate();
      assertUnchanged(current(), base.current);
      const data = selection();
      const result = await request<PacingSummary>(
        `/pacing/${projectId}/${proposal!.id}/preview`,
        "POST",
        data,
        signal,
      );
      if (mounted.current) {
        reviewed.current = JSON.stringify(data);
        setSummary(result);
      }
    });
  }
  function apply() {
    void run("Menerapkan…", async (signal) => {
      const data = selection();
      if (!summary || reviewed.current !== JSON.stringify(data))
        throw new Error("Periksa ulang perubahan sebelum menerapkan.");
      assertUnchanged(current(), base.current);
      await flush();
      assertUnchanged(current(), base.current);
      const result = await request<Project>(
        `/pacing/${projectId}/${proposal!.id}/apply`,
        "POST",
        data,
        signal,
      );
      if (mounted.current) onApplied(result);
    });
  }
  return (
    <Modal
      title="Timing & caption"
      wide
      onClose={() => {
        if (working !== "Menerapkan…") onClose();
      }}
    >
      <div className="modal-body storyboard-review">
        <p>
          Ukur narasi dari file audio lokal, rapikan baris caption, lalu tinjau
          perubahan. Semua jeda di dalam audio tetap utuh.
        </p>
        <p className="muted">
          Caption mengikuti batas scene. Deteksi jeda bukan timestamp kata;
          suara pelan dapat terbaca sebagai jeda.
        </p>
        <button disabled={!!working} onClick={analyze}>
          {proposal ? "Analisis ulang" : "Analisis timing"}
        </button>
        {working && <Busy text={working} />}
        {error && (
          <p role="alert" className="warning">
            {error}
          </p>
        )}
        {proposal && (
          <>
            {!proposal.caption_enabled && (
              <p className="warning">
                Caption sedang dinonaktifkan. Aktifkan di Gaya untuk
                menampilkannya pada preview dan ekspor.
              </p>
            )}
            <fieldset disabled={!!working} className="pacing-fields">
              {proposal.rows.map((row) => {
                const edit = edits.find(
                  (item) => item.scene_id === row.scene_id,
                )!;
                return (
                  <article className="storyboard-scene" key={row.scene_id}>
                    <label className="storyboard-select">
                      <input
                        type="checkbox"
                        checked={selected.includes(row.scene_id)}
                        disabled={!!row.errors.length}
                        onChange={(e) => {
                          invalidate();
                          setSelected((items) =>
                            e.target.checked
                              ? [...items, row.scene_id]
                              : items.filter((id) => id !== row.scene_id),
                          );
                        }}
                      />
                      {row.name}
                    </label>
                    <p>
                      Scene saat ini {seconds(row.old_duration)} dtk
                      {row.audio
                        ? ` · Audio tersisa ${row.audio.seconds.toFixed(3)} dtk · Ruang setelah audio ${seconds(row.extra_gap_frames || 0)} dtk`
                        : " · Belum ada durasi narasi terukur"}
                    </p>
                    {row.audio && (
                      <details>
                        <summary>
                          {row.audio.silences.length} jeda terdeteksi · tetap
                          dipertahankan
                        </summary>
                        <p className="muted">
                          Posisi relatif terhadap audio setelah trim yang sudah
                          ada; ambang −40 dBFS, minimal 0,25 dtk.
                        </p>
                        {row.audio.silences.map((gap, i) => (
                          <p key={i}>
                            {gap.start_seconds.toFixed(2)}–
                            {gap.end_seconds.toFixed(2)} dtk (
                            {
                              (
                                {
                                  leading: "awal",
                                  internal: "tengah",
                                  trailing: "akhir",
                                  entire: "seluruh audio",
                                } as Record<string, string>
                              )[gap.kind]
                            }
                            )
                          </p>
                        ))}
                      </details>
                    )}
                    {[...row.errors, ...row.warnings].map((message) => (
                      <p className="warning" key={message}>
                        {message}
                      </p>
                    ))}
                    <div className="storyboard-columns">
                      <div>
                        <Field
                          label={`Durasi baru (frame, 30 fps) · ${seconds(edit.duration)} dtk`}
                        >
                          <input
                            type="number"
                            min={9}
                            max={1800}
                            step={1}
                            value={edit.duration}
                            onChange={(e) =>
                              patch(row.scene_id, {
                                duration: Math.min(
                                  1800,
                                  Math.max(
                                    9,
                                    Math.round(Number(e.target.value) || 9),
                                  ),
                                ),
                              })
                            }
                          />
                        </Field>
                        {row.audio && (
                          <button
                            disabled={
                              row.minimum_frames > 1800 || !!row.errors.length
                            }
                            onClick={() =>
                              patch(row.scene_id, {
                                duration: row.minimum_frames,
                              })
                            }
                          >
                            Pas dengan seluruh audio
                          </button>
                        )}
                        <p className="muted">
                          {row.audio
                            ? "Durasi awal mempertahankan ruang jeda Anda. Tombol di atas hanya mengurangi ruang setelah file berakhir."
                            : "Atur durasi manual sementara; analisis ulang setelah menambahkan file narasi."}
                        </p>
                      </div>
                      <div>
                        <Field label="Caption · boleh diperbaiki manual">
                          <textarea
                            rows={3}
                            maxLength={400}
                            value={edit.caption}
                            onChange={(e) =>
                              patch(row.scene_id, { caption: e.target.value })
                            }
                          />
                        </Field>
                        <p className="muted">
                          Maksimal dua baris. Enter mempertahankan pemisahan
                          baris pilihan Anda.
                        </p>
                        {[...row.caption.errors, ...row.caption.warnings].map(
                          (message) => (
                            <p className="muted" key={message}>
                              Hasil awal: {message}
                            </p>
                          ),
                        )}
                      </div>
                    </div>
                  </article>
                );
              })}
            </fieldset>
            <button disabled={!!working || !selected.length} onClick={validate}>
              Periksa perubahan
            </button>
            {summary && (
              <div className="storyboard-summary" aria-live="polite">
                <strong>
                  {summary.scenes.length} scene dipilih ·{" "}
                  {seconds(summary.old_frames)} →{" "}
                  {seconds(summary.total_frames)} dtk
                </strong>
                {summary.exceeds_target && (
                  <p className="warning">
                    Durasi melampaui target proyek; audio tetap dipertahankan.
                  </p>
                )}
                {summary.scenes.map((scene) => (
                  <div key={scene.scene_id}>
                    <p>
                      {scene.name}: {seconds(scene.old_duration)} →{" "}
                      {seconds(scene.duration)} dtk ·{" "}
                      {scene.caption.characters_per_second} karakter/detik
                    </p>
                    <p className="pacing-caption">
                      {scene.caption.text || "Tanpa caption"}
                    </p>
                    {[...scene.warnings, ...scene.caption.warnings].map(
                      (message) => (
                        <p className="warning" key={message}>
                          {message}
                        </p>
                      ),
                    )}
                  </div>
                ))}
                <p className="muted">
                  20 karakter/detik adalah panduan praktis, bukan jaminan
                  keterbacaan. Periksa preview setelah menerapkan; perubahan
                  bisa di-Undo.
                </p>
                <button
                  className="primary"
                  disabled={!!working}
                  onClick={apply}
                >
                  Terapkan perubahan
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}
