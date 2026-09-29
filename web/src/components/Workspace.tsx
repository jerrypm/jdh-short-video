import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Undo2,
  Redo2,
  Upload,
  Image as ImageIcon,
  Layers,
  Mic,
  Captions,
  SlidersHorizontal,
  Settings2,
  ChevronLeft,
  ChevronRight,
  Plus,
  Search,
  FileAudio,
  Film,
  CheckCircle2,
  AlertTriangle,
  Pencil,
  Trash2,
} from "lucide-react";
import {
  Project,
  Scene,
  Asset,
  Job,
  Capabilities,
  newScene,
  removeScene,
  sceneRanges,
  shortTime,
  splitScene,
  totalFrames,
} from "@/lib/model";
import { useProject } from "@/lib/useProject";
import { request, assetURL } from "@/lib/api";
import StoryboardReview from "./StoryboardReview";
import PacingReview from "./PacingReview";
import ScriptEditor from "./ScriptEditor";
import SceneEditor from "./SceneEditor";
import PreviewPlayer from "./PreviewPlayer";
import Timeline from "./Timeline";
import Inspector from "./Inspector";
import ExportPanel from "./ExportPanel";
import { Status, Field, Busy } from "./UI";

export default function Workspace({
  initial,
  initialIdeaId,
  onBack,
  onSetup,
}: {
  initial: Project;
  initialIdeaId?: string;
  onBack: () => void;
  onSetup: (p: Project) => void;
}) {
  const state = useProject(initial),
    { project, change, flush, adopt, undo, redo } = state;
  const [storyboardOpen, setStoryboardOpen] = useState(!!initialIdeaId);
  const [pacingOpen, setPacingOpen] = useState(false);
  const [editingSceneId, setEditingSceneId] = useState<string | null>(null);
  const [screen, setScreen] = useState(
      initial.scenes.length ? "editor" : "script",
    ),
    [tab, setTab] = useState("scene"),
    [selected, setSelected] = useState(initial.scenes[0]?.id ?? ""),
    [frame, setFrame] = useState(0),
    [playing, setPlaying] = useState(false),
    [left, setLeft] = useState(true),
    [right, setRight] = useState(true),
    [exporting, setExporting] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [search, setSearch] = useState(""),
    [caps, setCaps] = useState<Capabilities | null>(null),
    [job, setJob] = useState<Job | null>(null),
    [voice, setVoice] = useState("af_heart"),
    [speed, setSpeed] = useState(1);
  const upload = useRef<HTMLInputElement>(null);
  const scene =
    project.scenes.find((s) => s.id === selected) ?? project.scenes[0];
  const editingScene = project.scenes.find((s) => s.id === editingSceneId);
  const patch = (data: Partial<Scene>) => {
    if (scene)
      change((p) => ({
        ...p,
        scenes: p.scenes.map((s) =>
          s.id === scene.id ? { ...s, ...data } : s,
        ),
      }));
  };
  const seek = (n: number) => {
    setPlaying(false);
    setFrame(n);
  };
  useEffect(() => {
    void request<Capabilities>("/capabilities")
      .then(setCaps)
      .catch((e) => setError(e.message));
    if (window.innerWidth <= 1280) setLeft(false);
    if (window.innerWidth <= 720) setRight(false);
  }, []);
  useEffect(() => {
    if (frame >= totalFrames(project))
      setFrame(Math.max(0, totalFrames(project) - 1));
  }, [project.scenes]);
  const add = () => {
    const s = newScene(`Scene ${project.scenes.length + 1}`);
    change((p) => ({ ...p, scenes: [...p.scenes, s] }));
    setSelected(s.id);
    seek(totalFrames(project));
  };
  const split = () => {
    if (scene?.audio_id) {
      setError(
        "Pisah scene dengan narasi belum tersedia. Ubah durasi atau lepas narasi dahulu agar kata tidak terpotong.",
      );
      return;
    }
    change((p) => ({
      ...p,
      scenes: splitScene(p.scenes, scene?.id ?? "", frame),
    }));
  };
  const remove = (id: string) => {
    const result = removeScene(project.scenes, id);
    if (!result) return;
    change((p) => ({ ...p, scenes: result.scenes }));
    setSelected(result.selected);
    seek(result.frame);
  };
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (busy) return;
      if (
        (event.target as HTMLElement).closest(
          'input,textarea,select,[contenteditable="true"],dialog',
        )
      )
        return;
      if (event.code === "Space") {
        event.preventDefault();
        if (totalFrames(project)) setPlaying((p) => !p);
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        seek(
          Math.min(
            Math.max(0, totalFrames(project) - 1),
            frame + (event.shiftKey ? 30 : 1),
          ),
        );
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        seek(Math.max(0, frame - (event.shiftKey ? 30 : 1)));
      }
      if (event.key.toLowerCase() === "s" && !event.metaKey && !event.ctrlKey)
        split();
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") {
        event.preventDefault();
        event.shiftKey ? redo() : undo();
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [project, frame, scene, busy]);
  useEffect(() => {
    if (!job || !["running", "queued"].includes(job.status)) return;
    const timer = setInterval(
      () =>
        request<Job>(`/jobs/${job.id}`)
          .then(setJob)
          .catch((e) => setError(e.message)),
      800,
    );
    return () => clearInterval(timer);
  }, [job?.id, job?.status]);
  const attach = (aid: string, sid = scene?.id) => {
    const asset = project.assets.find((a) => a.id === aid);
    if (!asset || !sid) return;
    change((p) => ({
      ...p,
      scenes: p.scenes.map((s) =>
        s.id !== sid
          ? s
          : asset.kind === "audio"
            ? {
                ...s,
                audio_id: aid,
                audio_text: "",
                audio_in: 0,
                duration: Math.min(1800, Math.max(s.duration, asset.frames)),
              }
            : {
                ...s,
                media_id: aid,
                source_in: 0,
                duration:
                  asset.kind === "video"
                    ? Math.max(9, Math.min(s.duration, asset.frames))
                    : s.duration,
              },
      ),
    }));
  };
  const importFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    setBusy(true);
    setError("");
    setPlaying(false);
    try {
      await flush();
      for (const file of files) {
        const form = new FormData();
        form.set("file", file);
        const result = await request<{ asset: Asset; project: Project }>(
          `/projects/${project.id}/media`,
          "POST",
          form,
        );
        adopt(result.project);
      }
      setTab("media");
      setLeft(true);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  };
  const generateTTS = async () => {
    if (!scene) return;
    try {
      await flush();
      setJob(
        await request<Job>(`/projects/${project.id}/tts`, "POST", {
          scene_id: scene.id,
          voice,
          speed,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const applyTTS = async () => {
    if (!job?.result?.asset) return;
    setBusy(true);
    try {
      await flush();
      const current = await request<Project>(`/projects/${project.id}`);
      const applied = await request<Project>(
        `/projects/${project.id}/tts/${job.id}/apply`,
        "POST",
        { revision: current.revision },
      );
      adopt(applied, true);
      setJob(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const leave = async (action: () => void) => {
    setPlaying(false);
    try {
      await flush();
      action();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const tools = [
    { id: "media", name: "Media", icon: ImageIcon },
    { id: "scene", name: "Scene", icon: Layers },
    { id: "narasi", name: "Narasi", icon: Mic },
    { id: "caption", name: "Caption", icon: Captions },
    { id: "gaya", name: "Gaya", icon: SlidersHorizontal },
  ];
  return (
    <div className="workspace" inert={busy}>
      <header className="editor-header">
        <button onClick={() => void leave(onBack)}>
          <ArrowLeft size={14} />
          Proyek
        </button>
        <div className="document-name">
          <strong>{project.name}</strong>
          <span className="mono">9:16 · 1080×1920 · 30 fps</span>
        </div>
        <div className={"save-state " + (state.error ? "warning" : "")}>
          <span className="status-dot" />
          {state.status}
        </div>
        <div className="spacer" />
        <button
          className="text-button"
          onClick={() => {
            setPlaying(false);
            setScreen(screen === "editor" ? "script" : "editor");
          }}
        >
          {screen === "editor" ? "Naskah & scene" : "Editor"}
        </button>
        <button
          disabled={
            project.language !== "en" ||
            (!!job && ["queued", "running"].includes(job.status))
          }
          onClick={() => {
            setPlaying(false);
            setStoryboardOpen(true);
          }}
        >
          Draft dari ide
        </button>
        <button
          disabled={
            !project.scenes.length ||
            (!!job && ["queued", "running"].includes(job.status))
          }
          onClick={() => {
            setPlaying(false);
            setPacingOpen(true);
          }}
        >
          Timing & caption
        </button>
        <div className="undo-group">
          <button
            className="icon"
            aria-label="Urungkan"
            disabled={!state.canUndo}
            onClick={undo}
          >
            <Undo2 size={16} />
          </button>
          <button
            className="icon"
            aria-label="Ulangi"
            disabled={!state.canRedo}
            onClick={redo}
          >
            <Redo2 size={16} />
          </button>
        </div>
        <button
          className="primary"
          onClick={() => {
            setPlaying(false);
            setExporting(true);
          }}
        >
          <Upload size={16} />
          Ekspor
        </button>
      </header>
      {(error || state.error) && (
        <div role="alert" className="workspace-error">
          <AlertTriangle size={15} />
          {error || state.error}
          <button
            onClick={() => {
              setError("");
              if (state.error) void flush().catch(() => {});
            }}
          >
            {state.error ? "Coba simpan lagi" : "Tutup"}
          </button>
        </div>
      )}
      {screen === "script" ? (
        <ScriptEditor
          project={project}
          change={change}
          onEditor={() => {
            setSelected(project.scenes[0]?.id ?? "");
            setScreen("editor");
          }}
        />
      ) : (
        <>
          <div
            className={
              "editor-body " +
              (!left ? "left-closed " : "") +
              (!right ? "right-closed" : "")
            }
          >
            <nav className="tool-rail" aria-label="Alat editor">
              {tools.map((tool) => (
                <button
                  key={tool.id}
                  className={tab === tool.id && left ? "active" : ""}
                  onClick={() => {
                    setTab(tool.id);
                    setLeft(true);
                    if (tool.id === "caption" || tool.id === "gaya")
                      setRight(true);
                  }}
                >
                  <tool.icon size={19} />
                  <span>{tool.name}</span>
                </button>
              ))}
              <div className="spacer" />
              <button
                onClick={() =>
                  void leave(() => {
                    void request<Project>(`/projects/${project.id}`)
                      .then(onSetup)
                      .catch((e) => setError(e.message));
                  })
                }
              >
                <Settings2 size={18} />
                <span>Setup</span>
              </button>
            </nav>
            {left && (
              <aside className="left-panel">
                <div className="panel-heading">
                  {tab.toUpperCase()}
                  <span className="subtle small">
                    {tab === "scene" ? `${project.scenes.length} scene` : ""}
                  </span>
                  <button
                    className="tiny icon"
                    aria-label="Tutup panel kiri"
                    onClick={() => setLeft(false)}
                  >
                    <ChevronLeft size={14} />
                  </button>
                </div>
                <div className="left-content">
                  {tab === "scene" && (
                    <>
                      <div className="scene-list">
                        {sceneRanges(project.scenes).map((s, i) => (
                          <article
                            key={s.id}
                            className={
                              "scene-row " +
                              (scene?.id === s.id ? "selected" : "")
                            }
                            onDragOver={(e) => e.preventDefault()}
                            onDrop={(e) => {
                              e.preventDefault();
                              attach(
                                e.dataTransfer.getData("text/plain"),
                                s.id,
                              );
                            }}
                          >
                            <button
                              className="scene-select"
                              aria-label={`Pilih scene ${i + 1}: ${s.name}`}
                              aria-pressed={scene?.id === s.id}
                              onClick={() => {
                                setSelected(s.id);
                                seek(s.start);
                              }}
                            >
                              <div className="scene-heading">
                                <span className="scene-number">{i + 1}</span>
                                <strong>{s.name}</strong>
                                <span className="mono">
                                  {shortTime(s.start)}–{shortTime(s.end)}
                                </span>
                              </div>
                              <div
                                className={
                                  "scene-thumb " + (!s.media_id ? "missing" : "")
                                }
                              >
                                {s.media_id ? (
                                  project.assets.find((a) => a.id === s.media_id)
                                    ?.kind === "image" ? (
                                    <img
                                      src={assetURL(project, s.media_id)}
                                      alt=""
                                    />
                                  ) : (
                                    <Film size={18} />
                                  )
                                ) : (
                                  <ImageIcon size={17} />
                                )}
                                <span>
                                  {project.assets.find((a) => a.id === s.media_id)
                                    ?.name ?? "Seret media ke sini"}
                                </span>
                              </div>
                              <p>
                                {s.narration ||
                                  "Tambahkan narasi untuk scene ini."}
                              </p>
                              <Status
                                kind={
                                  !s.media_id
                                    ? "err"
                                    : s.audio_id &&
                                        s.audio_text &&
                                        s.audio_text !== s.narration
                                      ? "warn"
                                      : s.audio_id
                                        ? "ready"
                                        : "idle"
                                }
                              >
                                {!s.media_id
                                  ? "Media belum dipilih"
                                  : s.audio_id &&
                                      s.audio_text &&
                                      s.audio_text !== s.narration
                                    ? "Naskah berubah — perbarui narasi"
                                    : s.audio_id
                                      ? "Narasi siap"
                                      : "Tanpa narasi"}
                              </Status>
                            </button>
                            <div className="scene-row-actions">
                              <button
                                aria-label={`Edit scene ${i + 1}: ${s.name}`}
                                onClick={() => {
                                  setSelected(s.id);
                                  seek(s.start);
                                  setEditingSceneId(s.id);
                                }}
                              >
                                <Pencil size={13} /> Edit
                              </button>
                              <button
                                className="scene-delete"
                                aria-label={`Hapus scene ${i + 1}: ${s.name}`}
                                title="Hapus scene · bisa diurungkan"
                                onClick={() => remove(s.id)}
                              >
                                <Trash2 size={13} /> Hapus
                              </button>
                            </div>
                          </article>
                        ))}
                      </div>
                      <button className="add-scene" onClick={add}>
                        <Plus size={14} />
                        Tambah scene
                      </button>
                    </>
                  )}
                  {tab === "media" && (
                    <>
                      <button
                        className="primary full"
                        disabled={busy}
                        onClick={() => upload.current?.click()}
                      >
                        <Upload size={15} />
                        {busy ? "Mengimpor…" : "Impor media"}
                      </button>
                      <input
                        ref={upload}
                        type="file"
                        aria-label="Impor media lokal"
                        accept=".jpg,.jpeg,.png,.webp,.mp4,.mov,.m4v,.webm,.wav,.mp3,.m4a,.aac,.flac,.ogg"
                        multiple
                        hidden
                        onChange={importFiles}
                      />
                      <div className="search">
                        <Search size={14} />
                        <input
                          aria-label="Cari media"
                          placeholder="Cari media…"
                          value={search}
                          onChange={(e) => setSearch(e.target.value)}
                        />
                      </div>
                      <p className="hint">
                        Klik media untuk scene terpilih, atau seret ke scene.
                        File disalin ke proyek.
                      </p>
                      {project.assets
                        .filter((a) =>
                          a.name.toLowerCase().includes(search.toLowerCase()),
                        )
                        .map((asset) => (
                          <div
                            className="media-tile"
                            key={asset.id}
                            draggable
                            onDragStart={(e) =>
                              e.dataTransfer.setData("text/plain", asset.id)
                            }
                          >
                            <button
                              title={`Gunakan ${asset.name}`}
                              onClick={() => attach(asset.id)}
                            >
                              <div className="media-thumb">
                                {asset.kind === "image" ? (
                                  <img
                                    src={assetURL(project, asset.id)}
                                    alt=""
                                  />
                                ) : asset.kind === "video" ? (
                                  <Film size={24} />
                                ) : (
                                  <FileAudio size={24} />
                                )}
                              </div>
                              <strong>{asset.name}</strong>
                              <span className="mono small subtle">
                                {asset.kind === "image"
                                  ? `${asset.width}×${asset.height}`
                                  : shortTime(asset.frames)}
                              </span>
                            </button>
                            {asset.kind === "audio" && (
                              <button
                                className="tiny full"
                                onClick={() =>
                                  change((p) => ({ ...p, music_id: asset.id }))
                                }
                              >
                                Gunakan sebagai musik
                              </button>
                            )}
                          </div>
                        ))}
                      {project.music_id && (
                        <button
                          className="tiny full"
                          onClick={() =>
                            change((p) => ({ ...p, music_id: null }))
                          }
                        >
                          Lepas musik
                        </button>
                      )}
                    </>
                  )}
                  {tab === "narasi" && scene && (
                    <>
                      <Field label="Narasi scene">
                        <textarea
                          rows={6}
                          maxLength={3000}
                          value={scene.narration}
                          onChange={(e) => patch({ narration: e.target.value })}
                        />
                      </Field>
                      <Field label="Suara">
                        <select
                          value={voice}
                          onChange={(e) => setVoice(e.target.value)}
                        >
                          {(caps?.tts.voices.length
                            ? caps.tts.voices
                            : ["af_heart"]
                          ).map((v) => (
                            <option key={v}>{v}</option>
                          ))}
                        </select>
                      </Field>
                      <Field label={`Kecepatan · ${speed}×`}>
                        <input
                          type="range"
                          min=".5"
                          max="2"
                          step=".1"
                          value={speed}
                          onChange={(e) => setSpeed(+e.target.value)}
                        />
                      </Field>
                      <button
                        className="primary full"
                        disabled={
                          !caps?.tts.available ||
                          project.language !== "en" ||
                          !scene.narration.trim() ||
                          (!!job && ["queued", "running"].includes(job.status))
                        }
                        onClick={generateTTS}
                      >
                        Buat narasi scene
                      </button>
                      <p className="hint">
                        {caps?.tts.message}{" "}
                        {project.language === "id"
                          ? "Untuk Bahasa Indonesia, impor audio melalui Media."
                          : ""}
                      </p>
                      {scene.audio_id && (
                        <>
                          <audio
                            className="audio-control"
                            controls
                            src={assetURL(project, scene.audio_id)}
                          />
                          <button
                            className="tiny"
                            onClick={() =>
                              patch({
                                audio_id: null,
                                audio_text: "",
                                audio_in: 0,
                              })
                            }
                          >
                            Lepas narasi
                          </button>
                        </>
                      )}
                      {job && (
                        <div className="job-progress">
                          <progress value={job.progress} max={100} />
                          <p>{job.message}</p>
                          {["running", "queued"].includes(job.status) && (
                            <button
                              onClick={() =>
                                request<Job>(
                                  `/jobs/${job.id}/cancel`,
                                  "POST",
                                  {},
                                ).then(setJob)
                              }
                            >
                              Batal
                            </button>
                          )}
                          {job.status === "completed" && job.result?.asset && (
                            <>
                              <audio
                                className="audio-control"
                                controls
                                src={`/api/jobs/${job.id}/files/narration.wav`}
                              />
                              <p className="hint">
                                Durasi audio:{" "}
                                {(job.result.asset.frames / 30).toFixed(2)}{" "}
                                detik. Penerapan memperpanjang scene bila perlu.
                              </p>
                              <button className="primary" onClick={applyTTS}>
                                Terapkan narasi
                              </button>
                            </>
                          )}
                        </div>
                      )}
                    </>
                  )}
                  {(tab === "caption" || tab === "gaya") && (
                    <>
                      <h3>Caption yang terbaca</h3>
                      <p className="subtle">
                        Edit teks, ukuran, dan posisi di inspector kanan. Gaya
                        berlaku untuk seluruh proyek.
                      </p>
                      <div className="caption-summary">
                        <Captions size={30} />
                        <strong>
                          {project.caption_style.preset === "lime"
                            ? "Blok Lime"
                            : project.caption_style.preset === "bar"
                              ? "Bar Gelap"
                              : "Tebal Putih"}
                        </strong>
                        <span className="mono">
                          {project.caption_style.size} px ·{" "}
                          {project.caption_style.position}%
                        </span>
                      </div>
                      <p className="hint">
                        Preview dan ekspor menggunakan raster caption yang sama.
                      </p>
                      <button onClick={() => setRight(true)}>
                        Buka pengaturan caption
                        <ChevronRight size={14} />
                      </button>
                    </>
                  )}
                </div>
              </aside>
            )}
            <PreviewPlayer
              project={project}
              frame={frame}
              setFrame={setFrame}
              playing={playing}
              setPlaying={setPlaying}
            />
            {right ? (
              <Inspector
                project={project}
                scene={scene}
                patch={patch}
                change={change}
                tab={tab}
                onClose={() => setRight(false)}
              />
            ) : (
              <div className="inspector-rail">
                <button
                  className="icon"
                  aria-label="Buka inspector"
                  onClick={() => setRight(true)}
                >
                  <ChevronLeft size={16} />
                </button>
              </div>
            )}
          </div>
          <Timeline
            project={project}
            selected={scene?.id ?? ""}
            setSelected={setSelected}
            frame={frame}
            seek={seek}
            change={change}
            onSplit={split}
            onDelete={() => scene && remove(scene.id)}
            tab={tab}
            setTab={(value) => {
              setTab(value);
              setLeft(true);
            }}
            onDrop={attach}
          />
        </>
      )}
      {editingScene && (
        <SceneEditor
          key={editingScene.id}
          scene={editingScene}
          assets={project.assets}
          onClose={() => setEditingSceneId(null)}
          onSave={(changes) => {
            change((p) => ({
              ...p,
              scenes: p.scenes.map((s) =>
                s.id === editingScene.id ? { ...s, ...changes } : s,
              ),
            }));
            setEditingSceneId(null);
          }}
        />
      )}
      {pacingOpen && (
        <PacingReview
          projectId={project.id}
          current={() => state.current.current}
          flush={flush}
          onClose={() => setPacingOpen(false)}
          onApplied={(value) => {
            adopt(value, true);
            setPacingOpen(false);
            setFrame(0);
            setPlaying(false);
          }}
        />
      )}
      {storyboardOpen && (
        <StoryboardReview
          projectId={project.id}
          initialIdeaId={initialIdeaId}
          current={() => state.current.current}
          flush={flush}
          onClose={() => setStoryboardOpen(false)}
          onApplied={(value) => {
            adopt(value, true);
            setStoryboardOpen(false);
            setSelected(value.scenes[0]?.id || "");
            setFrame(0);
            setPlaying(false);
            setScreen("script");
          }}
        />
      )}
      {exporting && (
        <ExportPanel
          project={project}
          current={() => state.current.current}
          flush={flush}
          onApplied={(value) => {
            adopt(value, true);
            setFrame(0);
            setPlaying(false);
          }}
          onSettings={(settings) =>
            change((value) => ({ ...value, quality_settings: settings }))
          }
          onClose={() => setExporting(false)}
        />
      )}
    </div>
  );
}
