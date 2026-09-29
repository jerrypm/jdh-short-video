import { useEffect, useRef, useState } from "react";
import { nanoProvider, type AIStatus } from "@/lib/ai";
import { request } from "@/lib/api";
import type { Project } from "@/lib/model";
import {
  assertUnchanged,
  assertSavedSnapshot,
  generateStoryboard,
  storyboardRequest,
  type Draft,
  type DraftScene,
  type IdeaOption,
  type PlanSummary,
  type Proposal,
  type Selection,
} from "@/lib/storyboard";
import { Modal, Field, Busy } from "./UI";
import MotionControls from "./MotionControls";

export default function StoryboardReview({
  projectId,
  initialIdeaId,
  current,
  flush,
  onApplied,
  onClose,
}: {
  projectId: string;
  initialIdeaId?: string;
  current: () => Project;
  flush: () => Promise<void>;
  onApplied: (project: Project) => void;
  onClose: () => void;
}) {
  const [ideas, setIdeas] = useState<IdeaOption[]>([]),
    [ideaId, setIdeaId] = useState(initialIdeaId || "");
  const [provider, setProvider] = useState<AIStatus | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null),
    [draft, setDraft] = useState<Draft | null>(null);
  const [selected, setSelected] = useState<number[]>([]),
    [mode, setMode] = useState<"append" | "replace">("append");
  const [summary, setSummary] = useState<PlanSummary | null>(null),
    [confirmed, setConfirmed] = useState(false);
  const [working, setWorking] = useState<
      "" | "generate" | "validate" | "apply"
    >(""),
    [error, setError] = useState("");
  const abort = useRef<AbortController | null>(null),
    mounted = useRef(false),
    base = useRef("");
  const requestId = useRef<string | null>(null),
    applied = useRef(false),
    lock = useRef(false);
  const reviewed = useRef("");
  useEffect(() => {
    mounted.current = true;
    Promise.all([
      storyboardRequest<IdeaOption[]>("/ideas"),
      nanoProvider.status(),
    ])
      .then(([items, status]) => {
        if (!mounted.current) return;
        const english = items.filter((item) => item.language === "en");
        setIdeas(english);
        setProvider(status);
        setIdeaId((value) =>
          english.some((item) => item.card.id === value)
            ? value
            : english[english.length - 1]?.card.id || "",
        );
      })
      .catch((e) => {
        if (mounted.current) setError(e.message);
      });
    return () => {
      mounted.current = false;
      abort.current?.abort();
      if (requestId.current && !applied.current)
        void storyboardRequest(
          `/${projectId}/requests/${requestId.current}/cancel`,
          "POST",
          {},
        ).catch(() => undefined);
    };
  }, [projectId]);
  function invalidate() {
    setSummary(null);
    setConfirmed(false);
    reviewed.current = "";
  }
  function patch(index: number, values: Partial<DraftScene>) {
    invalidate();
    setDraft((value) =>
      value
        ? {
            ...value,
            scenes: value.scenes.map((scene, i) =>
              i === index ? { ...scene, ...values } : scene,
            ),
          }
        : null,
    );
  }
  async function generate() {
    if (lock.current) return;
    lock.current = true;
    setWorking("generate");
    setError("");
    invalidate();
    setDraft(null);
    setProposal(null);
    const controller = new AbortController();
    abort.current = controller;
    try {
      if (requestId.current)
        await storyboardRequest(
          `/${projectId}/requests/${requestId.current}/cancel`,
          "POST",
          {},
        );
      await flush();
      base.current = JSON.stringify(current());
      const saved = await request<Project>(
        `/projects/${projectId}`,
        "GET",
        undefined,
        controller.signal,
      );
      assertUnchanged(current(), base.current);
      assertSavedSnapshot(current(), saved);
      controller.signal.throwIfAborted();
      const id = crypto.randomUUID();
      requestId.current = id;
      const value = await generateStoryboard(
        saved,
        ideaId,
        id,
        controller.signal,
      );
      if (mounted.current) {
        setProposal(value);
        setDraft(value.draft);
        setSelected(value.draft!.scenes.map((_, i) => i));
      }
    } catch (e) {
      if (mounted.current && (e as Error).name !== "AbortError")
        setError((e as Error).message);
    } finally {
      lock.current = false;
      if (mounted.current) setWorking("");
    }
  }
  function selection(): Selection {
    if (!draft || !proposal) throw new Error("Buat proposal dahulu.");
    return { draft, selected, mode };
  }
  async function validate() {
    if (lock.current || !proposal) return;
    lock.current = true;
    setWorking("validate");
    setError("");
    invalidate();
    try {
      assertUnchanged(current(), base.current);
      const data = selection();
      const result = await storyboardRequest<PlanSummary>(
        `/${projectId}/requests/${proposal.id}/preview`,
        "POST",
        data,
      );
      if (mounted.current) {
        reviewed.current = JSON.stringify(data);
        setSummary(result);
      }
    } catch (e) {
      if (mounted.current) setError((e as Error).message);
    } finally {
      lock.current = false;
      if (mounted.current) setWorking("");
    }
  }
  async function apply() {
    if (lock.current || !proposal || !confirmed || !summary) return;
    lock.current = true;
    setWorking("apply");
    setError("");
    try {
      assertUnchanged(current(), base.current);
      const data = selection();
      if (reviewed.current !== JSON.stringify(data))
        throw new Error("Proposal berubah; periksa ulang sebelum menerapkan.");
      await flush();
      assertUnchanged(current(), base.current);
      const result = await storyboardRequest<Project>(
        `/${projectId}/requests/${proposal.id}/apply`,
        "POST",
        data,
      );
      applied.current = true;
      onApplied(result);
    } catch (e) {
      if (mounted.current) setError((e as Error).message);
    } finally {
      lock.current = false;
      if (mounted.current) setWorking("");
    }
  }
  return (
    <Modal
      title="Review naskah & storyboard"
      wide
      onClose={() => {
        if (working !== "apply") onClose();
      }}
    >
      <div className="modal-body storyboard-review">
        <p className="subtle">
          Gemini Nano lokal · English · proposal 30 fps. Review fakta dan media
          sebelum menerapkan; naskah proyek belum berubah.
        </p>
        {error && (
          <p role="alert" className="error-banner">
            {error}
          </p>
        )}
        <div className="storyboard-controls" inert={!!working}>
          <Field label="Ide terpilih">
            <select
              value={ideaId}
              onChange={(e) => {
                setIdeaId(e.target.value);
                setDraft(null);
                setProposal(null);
                invalidate();
              }}
            >
              <option value="" disabled>
                Pilih ide dari beranda
              </option>
              {ideas.map(({ card }) => (
                <option key={card.id} value={card.id}>
                  {card.title}
                </option>
              ))}
            </select>
          </Field>
          <button
            className="primary"
            disabled={
              !ideaId ||
              current().language !== "en" ||
              provider?.availability !== "available"
            }
            onClick={() => void generate()}
          >
            Susun proposal
          </button>
          <button
            onClick={() =>
              void nanoProvider
                .status()
                .then(setProvider)
                .catch((e) => setError(e.message))
            }
          >
            Periksa Nano
          </button>
        </div>
        {!ideas.length && (
          <p className="hint">
            Buat atau simpan ide English di beranda terlebih dahulu.
          </p>
        )}
        {provider?.availability !== "available" && (
          <p className="hint">
            Hubungkan dan siapkan companion Chrome melalui Setup. Tidak ada
            fallback cloud.
          </p>
        )}
        {working === "generate" && (
          <p className="ideas-actions">
            <Busy text="Nano sedang menyusun proposal…" />
            <button onClick={() => abort.current?.abort()}>
              Batalkan generation
            </button>
          </p>
        )}
        {draft && proposal && (
          <div inert={!!working}>
            <p className="hint">
              Proposal untuk revisi proyek {proposal.base_revision}; berlaku
              maksimal 15 menit. Efek tersedia: visual statis dan cut. Durasi
              tanpa audio masih perkiraan.
            </p>
            <Field label="Hook (harus membuka narasi scene pertama)">
              <input
                maxLength={240}
                value={draft.hook}
                onChange={(e) => {
                  invalidate();
                  setDraft({ ...draft, hook: e.target.value });
                }}
              />
            </Field>
            <details className="storyboard-sources">
              <summary>Sumber konteks ({proposal.sources.length})</summary>
              {proposal.sources.length ? (
                proposal.sources.map((source) => (
                  <p key={source.project_id}>
                    <strong>{source.name}</strong> · revisi{" "}
                    {source.source_revision}
                    <br />
                    {source.summary}
                    <br />
                    <span className="hint">
                      {source.summary_origin === "user"
                        ? "Ringkasan pengguna"
                        : "Cuplikan proyek"}{" "}
                      · {source.project_id}
                    </span>
                  </p>
                ))
              ) : (
                <p>
                  Preferensi dan ide pengguna; belum ada sumber video
                  sebelumnya.
                </p>
              )}
            </details>
            {draft.scenes.map((scene, index) => (
              <article className="storyboard-scene" key={index}>
                <label className="storyboard-select">
                  <input
                    type="checkbox"
                    checked={selected.includes(index)}
                    onChange={(e) => {
                      invalidate();
                      setSelected((value) =>
                        e.target.checked
                          ? [...value, index]
                          : value.filter((i) => i !== index),
                      );
                    }}
                  />{" "}
                  Terapkan scene {index + 1}
                </label>
                <Field label="Nama scene">
                  <input
                    value={scene.name}
                    maxLength={120}
                    onChange={(e) => patch(index, { name: e.target.value })}
                  />
                </Field>
                <Field label="Narasi">
                  <textarea
                    rows={3}
                    maxLength={1500}
                    value={scene.narration}
                    onChange={(e) =>
                      patch(index, { narration: e.target.value })
                    }
                  />
                </Field>
                <Field label="Caption singkat">
                  <input
                    maxLength={240}
                    value={scene.caption}
                    onChange={(e) => patch(index, { caption: e.target.value })}
                  />
                </Field>
                <div className="storyboard-columns">
                  <Field label="Perkiraan durasi (frame, 30 fps)">
                    <input
                      type="number"
                      min={9}
                      max={1800}
                      step={1}
                      value={scene.estimated_frames}
                      onChange={(e) =>
                        patch(index, {
                          estimated_frames: Number(e.target.value),
                        })
                      }
                    />
                  </Field>
                  <Field label="Visual proyek">
                    <select
                      value={scene.media_id || ""}
                      onChange={(e) =>
                        patch(index, {
                          media_id: e.target.value || null,
                          media_status: e.target.value
                            ? "available"
                            : "missing",
                        })
                      }
                    >
                      <option value="">
                        Belum tersedia — perlu ditambahkan
                      </option>
                      {proposal.assets
                        .filter((a) => a.kind !== "audio")
                        .map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.name}
                          </option>
                        ))}
                    </select>
                  </Field>
                </div>
                <Field label="Visual yang diperlukan">
                  <input
                    maxLength={240}
                    value={scene.visual_need}
                    onChange={(e) =>
                      patch(index, { visual_need: e.target.value })
                    }
                  />
                </Field>
                <MotionControls
                  value={scene.motion}
                  duration={scene.estimated_frames}
                  onChange={(motion) => patch(index, { motion })}
                />
                <Field label="Maksud framing dan gerak">
                  <input
                    maxLength={200}
                    value={scene.motion_intent}
                    onChange={(e) =>
                      patch(index, { motion_intent: e.target.value })
                    }
                  />
                </Field>
                <p className="hint">
                  {scene.audio_id
                    ? `Audio: ${proposal.assets.find((a) => a.id === scene.audio_id)?.name}. Durasi terukur menjadi batas minimum.`
                    : "Audio belum dipasang; buat narasi setelah naskah diterapkan."}
                </p>
                {scene.audio_id && (
                  <button onClick={() => patch(index, { audio_id: null })}>
                    Lepaskan audio jika narasi diubah
                  </button>
                )}
                <p className="hint">
                  Sumber scene:{" "}
                  {scene.source_project_ids
                    .map(
                      (id) =>
                        proposal.sources.find((s) => s.project_id === id)
                          ?.name || id,
                    )
                    .join(" · ") || "Usulan kreatif tanpa sumber video"}
                </p>
              </article>
            ))}
            <Field label="Cara menerapkan">
              <select
                value={mode}
                onChange={(e) => {
                  invalidate();
                  setMode(e.target.value as "append" | "replace");
                }}
              >
                <option value="append">
                  Tambahkan scene terpilih dan narasi ke akhir proyek
                </option>
                <option value="replace">
                  Ganti seluruh scene dan naskah dengan pilihan ini
                </option>
              </select>
            </Field>
            <button disabled={!selected.length} onClick={() => void validate()}>
              Periksa perubahan ({selected.length} scene)
            </button>
          </div>
        )}
        {summary && (
          <div className="storyboard-summary" aria-live="polite">
            <strong>
              {summary.added_scenes} scene diterapkan · {summary.removed_scenes}{" "}
              scene lama diganti
            </strong>
            <p>
              Durasi: {(summary.old_frames / 30).toFixed(1)} →{" "}
              {(summary.total_frames / 30).toFixed(1)} detik ·{" "}
              {summary.missing_media} visual belum tersedia.
            </p>
            {summary.plan.map((scene) => (
              <p className="hint" key={scene.index}>
                Scene {scene.index + 1}: {scene.frames} frame (
                {(scene.frames / 30).toFixed(1)} dtk) ·{" "}
                {scene.duration_origin === "measured_audio"
                  ? "minimal durasi audio terukur"
                  : "perkiraan"}
              </p>
            ))}
            {summary.exceeds_target && (
              <p className="hint">
                Durasi melebihi target proyek; audio tetap dipertahankan utuh.
              </p>
            )}
            {summary.removed_scenes > 0 && (
              <p className="hint">
                Scene dan kaitan audio lama diganti. File media tetap tersimpan;
                Undo mengembalikan perubahan.
              </p>
            )}
            <label className="storyboard-select">
              <input
                type="checkbox"
                checked={confirmed}
                disabled={!!working}
                onChange={(e) => setConfirmed(e.target.checked)}
              />
              Saya sudah meninjau fakta, sumber, kebutuhan media, dan perubahan
              ini.
            </label>
          </div>
        )}
      </div>
      <div className="modal-footer">
        <span className="hint">Hasil AI perlu review · dapat di-Undo</span>
        <div className="spacer" />
        <button disabled={working === "apply"} onClick={onClose}>
          Tutup
        </button>
        <button
          className="primary"
          disabled={!summary || !confirmed || !!working}
          onClick={() => void apply()}
        >
          {working === "apply"
            ? "Menerapkan…"
            : working === "validate"
              ? "Memeriksa…"
              : "Terapkan pilihan"}
        </button>
      </div>
    </Modal>
  );
}
