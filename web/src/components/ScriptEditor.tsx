import { useState, useRef, useEffect } from "react";
import { ArrowRight, Plus, Sparkles, Scissors, Trash2 } from "lucide-react";
import { Project, Scene, buildScenes, newScene } from "@/lib/model";
import {
  availability,
  nanoProvider,
  proposalFingerprint,
  applyScriptSuggestion,
  type AIOperation,
} from "@/lib/ai";
import { Field, Status, Modal, Busy } from "./UI";
export default function ScriptEditor({
  project,
  change,
  onEditor,
}: {
  project: Project;
  change: (fn: (p: Project) => Project) => void;
  onEditor: () => void;
}) {
  const [ai, setAI] = useState("unavailable"),
    [suggestions, setSuggestions] = useState<string[]>([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [replace, setReplace] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const base = useRef("");
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const update = async () => {
      const value = await availability();
      if (!disposed) {
        setAI(value);
        timer = setTimeout(update, 2500);
      }
    };
    void update();
    return () => {
      disposed = true;
      mounted.current = false;
      clearTimeout(timer);
      abort.current?.abort();
    };
  }, []);
  const generate = async (action: AIOperation) => {
    setBusy(true);
    setError("");
    setSuggestions([]);
    base.current = proposalFingerprint(project);
    abort.current = new AbortController();
    try {
      const result = await nanoProvider.generate(
        action,
        project.script,
        abort.current.signal,
      );
      if (mounted.current) setSuggestions(result);
    } catch (e) {
      if (mounted.current && (e as Error).name !== "AbortError")
        setError((e as Error).message);
    } finally {
      if (mounted.current) setBusy(false);
    }
  };
  const split = () => {
    change((p) => ({ ...p, scenes: buildScenes(p.script, p.target) }));
    setReplace(false);
  };
  const patch = (id: string, data: Partial<Scene>) =>
    change((p) => ({
      ...p,
      scenes: p.scenes.map((s) => (s.id === id ? { ...s, ...data } : s)),
    }));
  return (
    <main className="script-page">
      <div className="section-head">
        <div>
          <h1>Naskah & scene</h1>
          <p className="subtle">
            Satu pesan yang jelas, lalu susun menjadi cerita visual.
          </p>
        </div>
        <div className="spacer" />
        <button
          className="primary"
          disabled={!project.scenes.length}
          onClick={onEditor}
        >
          Buka editor
          <ArrowRight size={16} />
        </button>
      </div>
      <div className="script-columns">
        <section className="script-writing">
          <Field label="Bahasa proyek">
            <select
              value={project.language}
              onChange={(e) =>
                change((p) => ({
                  ...p,
                  language: e.target.value as Project["language"],
                }))
              }
            >
              <option value="en">English · AI & Kokoro</option>
              <option value="id">Indonesia · manual & impor audio</option>
            </select>
          </Field>
          <div className="section-head">
            <h2>Naskah utama</h2>
            <span className="mono small subtle">
              {project.script.trim()
                ? project.script.trim().split(/\s+/).length
                : 0}{" "}
              kata
            </span>
          </div>
          <textarea
            className="main-script"
            aria-label="Naskah utama"
            maxLength={12000}
            placeholder="Tulis satu pesan yang jelas. Pisahkan paragraf untuk setiap scene."
            value={project.script}
            onChange={(e) => change((p) => ({ ...p, script: e.target.value }))}
          />
          <p className="hint">
            Durasi awal merupakan perkiraan dari proporsi kata. Audio impor atau
            hasil TTS memakai durasi yang terukur.
          </p>
          <div className="script-actions">
            <button
              className="primary"
              disabled={!project.script.trim()}
              onClick={() =>
                project.scenes.length ? setReplace(true) : split()
              }
            >
              <Scissors size={15} />
              Pecah naskah jadi scene
            </button>
            <button
              onClick={() =>
                change((p) => ({
                  ...p,
                  scenes: [
                    ...p.scenes,
                    newScene(`Scene ${p.scenes.length + 1}`),
                  ],
                }))
              }
            >
              <Plus size={15} />
              Scene kosong
            </button>
          </div>
          <div className="ai-assist">
            <h3>
              <Sparkles size={17} />
              Bantuan AI lokal
              <Status kind={ai === "available" ? "ready" : "warn"}>
                {ai === "available" ? "Siap" : "Hubungkan dari Setup"}
              </Status>
            </h3>
            <p className="subtle">
              {project.language === "id"
                ? "Bantuan AI diuji untuk English. Naskah Indonesia tetap bisa ditulis manual."
                : "Gemini Nano lokal melalui companion Chrome. Hasil selalu ditinjau sebelum diterapkan."}
            </p>
            <div className="button-wrap">
              <button
                disabled={
                  project.language !== "en" ||
                  ai !== "available" ||
                  busy ||
                  !project.script.trim()
                }
                onClick={() => generate("hooks")}
              >
                Buat 3 hook
              </button>
              <button
                disabled={
                  project.language !== "en" ||
                  ai !== "available" ||
                  busy ||
                  !project.script.trim()
                }
                onClick={() => generate("draft")}
              >
                Buat draf naskah
              </button>
            </div>
            {busy && (
              <p>
                <Busy text="Memproses di perangkat… Anda dapat membatalkan kapan saja." />
                <button onClick={() => abort.current?.abort()}>Batal</button>
              </p>
            )}
            {error && (
              <p role="alert" className="error-banner">
                {error}
              </p>
            )}
          </div>
          <Field label="Referensi — belum diverifikasi">
            <input
              value={project.reference}
              maxLength={2000}
              onChange={(e) =>
                change((p) => ({ ...p, reference: e.target.value }))
              }
            />
          </Field>
          <Field label="Catatan referensi">
            <textarea
              rows={3}
              maxLength={5000}
              value={project.reference_notes}
              onChange={(e) =>
                change((p) => ({ ...p, reference_notes: e.target.value }))
              }
              placeholder="Pacing, framing, caption, dan hal yang ingin Anda coba."
            />
          </Field>
        </section>
        <section className="storyboard">
          <div className="section-head">
            <h2>Storyboard</h2>
            <span className="mono small">{project.scenes.length} scene</span>
          </div>
          {project.scenes.length === 0 ? (
            <div className="storyboard-empty">
              <Scissors size={28} />
              <h3>Susun cerita Anda</h3>
              <p>
                Tulis naskah di kiri, lalu pecah menjadi scene.
                <br />
                Anda juga bisa mulai dengan scene kosong.
              </p>
            </div>
          ) : (
            project.scenes.map((scene, i) => (
              <article className="script-scene" key={scene.id}>
                <div className="scene-heading">
                  <span className="scene-number">{i + 1}</span>
                  <input
                    aria-label={`Nama scene ${i + 1}`}
                    maxLength={120}
                    value={scene.name}
                    onChange={(e) => patch(scene.id, { name: e.target.value })}
                  />
                  <span className="mono small">
                    {(scene.duration / 30).toFixed(1)} dtk
                  </span>
                  <button
                    className="tiny icon"
                    title="Hapus scene"
                    onClick={() =>
                      change((p) => ({
                        ...p,
                        scenes: p.scenes.filter((s) => s.id !== scene.id),
                      }))
                    }
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
                <Field label="Narasi">
                  <textarea
                    rows={3}
                    maxLength={3000}
                    value={scene.narration}
                    onChange={(e) =>
                      patch(scene.id, { narration: e.target.value })
                    }
                  />
                </Field>
                <Field label="Teks layar / caption">
                  <input
                    maxLength={400}
                    placeholder="Frasa pendek yang mendukung narasi"
                    value={scene.caption}
                    onChange={(e) =>
                      patch(scene.id, { caption: e.target.value })
                    }
                  />
                </Field>
                {scene.planning && (
                  <details className="hint">
                    <summary>Catatan proposal lokal yang diterapkan</summary>
                    <p>Visual: {scene.planning.visual_need}</p>
                    <p>Framing statis: {scene.planning.motion_intent}</p>
                    <p>
                      Perkiraan awal:{" "}
                      {(scene.planning.estimated_frames / 30).toFixed(1)} detik.
                      Perubahan manual setelah apply belum dianalisis ulang.
                    </p>
                  </details>
                )}
                <Status kind={scene.media_id ? "ready" : "warn"}>
                  {scene.media_id ? "Media dipilih" : "Media belum dipilih"}
                </Status>
              </article>
            ))
          )}
        </section>
      </div>
      {replace && (
        <Modal title="Ganti susunan scene?" onClose={() => setReplace(false)}>
          <div className="modal-body">
            <p>
              Scene saat ini akan diganti dari naskah utama. Media tetap
              tersimpan di bin. Perubahan bisa diurungkan.
            </p>
          </div>
          <div className="modal-footer">
            <button onClick={() => setReplace(false)}>Batal</button>
            <button className="primary" onClick={split}>
              Ganti scene
            </button>
          </div>
        </Modal>
      )}
      {suggestions.length > 0 && (
        <Modal title="Tinjau saran AI" onClose={() => setSuggestions([])}>
          <div className="modal-body">
            <p className="subtle">
              Naskah belum berubah. Pilih saran untuk mengganti naskah utama;
              scene yang ada tetap utuh.
            </p>
            {proposalFingerprint(project) !== base.current && (
              <p role="alert" className="error-banner">
                Proyek berubah sejak saran dibuat. Tutup dialog dan buat saran
                baru.
              </p>
            )}
            {error && (
              <p role="alert" className="error-banner">
                {error}
              </p>
            )}
            {suggestions.map((text, i) => (
              <article className="suggestion" key={i}>
                <p>{text}</p>
                <button
                  className="primary"
                  disabled={proposalFingerprint(project) !== base.current}
                  onClick={() => {
                    try {
                      change((p) =>
                        applyScriptSuggestion(p, base.current, text),
                      );
                      setSuggestions([]);
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  Terapkan ke naskah
                </button>
              </article>
            ))}
          </div>
        </Modal>
      )}
    </main>
  );
}
