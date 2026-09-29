import { useState, useRef } from "react";
import DailyIdeas from "./DailyIdeas";
import {
  Plus,
  ArrowRight,
  FolderOpen,
  Settings2,
  Film,
  Upload,
  Search,
  BookOpen,
  BarChart3,
} from "lucide-react";
import { Project, shortTime, totalFrames } from "@/lib/model";
import { request } from "@/lib/api";
import { Brand, Modal, Field, Status, Busy } from "./UI";

export default function Projects({
  projects,
  onOpen,
  onDraft,
  onSetup,
  onMemory,
  onPerformance,
  onResearch,
  onRefresh,
}: {
  projects: Project[];
  onOpen: (p: Project) => void;
  onDraft: (p: Project, ideaId: string) => void;
  onSetup: () => void;
  onMemory: () => void;
  onPerformance: () => void;
  onResearch: () => void;
  onRefresh: () => void;
}) {
  const [draftIdea, setDraftIdea] = useState<string | null>(null),
    [draftProject, setDraftProject] = useState("");
  const [create, setCreate] = useState(false),
    [search, setSearch] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const latest = projects[0];
  const upload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.files?.[0];
    if (!value) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.set("file", value);
      const p = await request<Project>("/import-project", "POST", form);
      onRefresh();
      onOpen(p);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  };
  return (
    <div className="projects-page">
      <header className="home-header">
        <Brand />
        <span className="subtle">Proyek dan rencana produksi</span>
        <div className="spacer" />
        <button onClick={onResearch}>
          <Search size={16} />
          Sumber riset
        </button>
        <button onClick={onPerformance}>
          <BarChart3 size={16} />
          Performa video
        </button>
        <button onClick={onMemory}>
          <BookOpen size={16} />
          Memori konten
        </button>
        <button onClick={onSetup}>
          <Settings2 size={16} />
          Setup & pengaturan
        </button>
        <button className="primary" onClick={() => setCreate(true)}>
          <Plus size={17} />
          Short baru
        </button>
      </header>
      <main className="home-main">
        {error && (
          <p role="alert" className="error-banner">
            {error}
          </p>
        )}
        {latest ? (
          <section className="continue-panel">
            <div className="project-cover">
              <Film size={42} />
              <span className="mono">{shortTime(totalFrames(latest))}</span>
            </div>
            <div>
              <div className="eyebrow">LANJUTKAN PROYEK TERAKHIR</div>
              <h1>{latest.name}</h1>
              <p>
                {latest.scenes.length} scene · {shortTime(totalFrames(latest))}{" "}
                · {new Date(latest.updated_at).toLocaleDateString("id-ID")}
              </p>
              <Status kind="lime-soft">
                {latest.scenes.length ? "Editing" : "Naskah"}
              </Status>
              <p className="subtle">
                {latest.scenes.some((s) => !s.media_id)
                  ? "Langkah berikutnya: lengkapi media scene"
                  : "Lanjutkan naskah dan tinjau video Anda."}
              </p>
              <button className="primary" onClick={() => onOpen(latest)}>
                Lanjutkan
                <ArrowRight size={16} />
              </button>
            </div>
          </section>
        ) : (
          <section className="empty-start">
            <div className="empty-symbol">
              <Film size={32} />
            </div>
            <h1>Short pertama dimulai dari satu ide.</h1>
            <p>
              Tulis naskah, susun scene, dan buat video vertikal.
              <br />
              Proyek dan media tersimpan di perangkat ini.
            </p>
            <button className="primary" onClick={() => setCreate(true)}>
              <Plus size={17} />
              Buat Short pertama
            </button>
            <span className="mono small">9:16 · 1080×1920 · 30 fps</span>
          </section>
        )}
        <DailyIdeas
          onMemory={onMemory}
          onResearch={onResearch}
          onSetup={onSetup}
          paused={create || busy || !!draftIdea}
          onDraft={(id) => {
            setDraftProject(
              projects.find((p) => p.language === "en")?.id || "",
            );
            setDraftIdea(id);
          }}
        />
        <div className="section-head">
          <h2>
            Semua proyek <span>{projects.length} proyek</span>
          </h2>
          <div className="search">
            <Search size={15} />
            <input
              aria-label="Cari proyek"
              placeholder="Cari proyek…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <button onClick={() => file.current?.click()} disabled={busy}>
            <Upload size={15} />
            {busy ? "Mengimpor…" : "Impor paket proyek"}
          </button>
          <input
            ref={file}
            type="file"
            accept=".zip"
            hidden
            onChange={upload}
          />
        </div>
        <div className="project-grid">
          {projects
            .filter((p) => p.name.toLowerCase().includes(search.toLowerCase()))
            .map((p) => (
              <button
                key={p.id}
                className="project-card"
                onClick={() => onOpen(p)}
              >
                <div className="card-cover">
                  <Film size={30} />
                  <span className="mono">{shortTime(totalFrames(p))}</span>
                </div>
                <div className="card-info">
                  <strong>{p.name}</strong>
                  <p className="subtle">
                    Diedit {new Date(p.updated_at).toLocaleDateString("id-ID")}
                  </p>
                  <Status kind={p.scenes.length ? "lime-soft" : "idle"}>
                    {p.scenes.length ? "Editing" : "Naskah"}
                  </Status>
                  <div className="card-next">
                    <FolderOpen size={14} />
                    {p.scenes.length
                      ? `${p.scenes.length} scene · buka editor`
                      : "Tulis naskah dan susun scene"}
                    <ArrowRight size={14} />
                  </div>
                </div>
              </button>
            ))}
        </div>
        <footer className="home-footer">
          <span className="status-dot" /> Penyimpanan lokal{" "}
          <span className="spacer" />
          Publikasi ke YouTube dilakukan manual.
        </footer>
      </main>
      {draftIdea && (
        <Modal
          title="Pilih proyek untuk draft"
          onClose={() => setDraftIdea(null)}
        >
          <div className="modal-body">
            <p>Proposal akan ditinjau di editor sebelum mengubah proyek.</p>
            <Field label="Proyek English">
              <select
                value={draftProject}
                onChange={(e) => setDraftProject(e.target.value)}
              >
                <option value="" disabled>
                  Pilih proyek
                </option>
                {projects
                  .filter((p) => p.language === "en")
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
              </select>
            </Field>
            {!projects.some((p) => p.language === "en") && (
              <p className="hint">
                Buat Short baru dengan bahasa English terlebih dahulu, lalu
                pilih ide ini.
              </p>
            )}
          </div>
          <div className="modal-footer">
            <button onClick={() => setDraftIdea(null)}>Batal</button>
            <button
              className="primary"
              disabled={!draftProject}
              onClick={() => {
                const project = projects.find((p) => p.id === draftProject);
                if (project) onDraft(project, draftIdea);
              }}
            >
              Buka review
            </button>
          </div>
        </Modal>
      )}
      {create && (
        <NewProject onClose={() => setCreate(false)} onCreated={onOpen} />
      )}
    </div>
  );
}

function NewProject({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (p: Project) => void;
}) {
  const [name, setName] = useState(""),
    [script, setScript] = useState(""),
    [target, setTarget] = useState(30),
    [language, setLanguage] = useState("id"),
    [reference, setReference] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      onCreated(
        await request<Project>("/projects", "POST", {
          name,
          script,
          target,
          language,
          reference,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Short baru" onClose={onClose}>
      <form onSubmit={submit}>
        <div className="modal-body">
          <p className="subtle">
            Mulai dari ide, naskah, atau footage yang sudah Anda miliki.
          </p>
          <Field label="Nama proyek">
            <input
              required
              autoFocus
              maxLength={120}
              placeholder="Satu ide. Satu Short."
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <Field label="Topik atau naskah">
            <textarea
              rows={5}
              maxLength={12000}
              value={script}
              onChange={(e) => setScript(e.target.value)}
              placeholder="Apa yang ingin Anda ceritakan?"
            />
          </Field>
          <Field label="Bahasa konten">
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            >
              <option value="id">
                Bahasa Indonesia — naskah manual & narasi impor
              </option>
              <option value="en">English — AI & Kokoro jika tersedia</option>
            </select>
          </Field>
          <Field label="Target durasi">
            <div className="segmented">
              {[15, 30, 45, 60].map((n) => (
                <button
                  key={n}
                  type="button"
                  className={n === target ? "selected" : ""}
                  onClick={() => setTarget(n)}
                >
                  {n} detik
                </button>
              ))}
            </div>
          </Field>
          <p className="hint">Preset produk, bukan batas maksimal YouTube.</p>
          <Field label="Referensi (opsional)">
            <input
              maxLength={2000}
              placeholder="URL atau catatan referensi"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
            />
          </Field>
          <p className="hint">
            Referensi disimpan sebagai catatan. Video belum dianalisis.
          </p>
          {error && (
            <p role="alert" className="error-banner">
              {error}
            </p>
          )}
        </div>
        <div className="modal-footer">
          <span className="mono subtle">9:16 · 1080×1920 · 30 fps</span>
          <div className="spacer" />
          <button type="button" onClick={onClose}>
            Batal
          </button>
          <button className="primary" disabled={busy || !name.trim()}>
            {busy ? <Busy text="Membuat…" /> : "Buat proyek"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
