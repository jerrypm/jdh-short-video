import { useEffect, useState } from "react";
import { Download, Film } from "lucide-react";
import { Project, Job, shortTime, totalFrames } from "@/lib/model";
import { request } from "@/lib/api";
import { Modal, Field, Busy, Status } from "./UI";
import QualityPanel from "./QualityPanel";
import type { QualityReport, QualitySettings } from "@/lib/quality";
export default function ExportPanel({
  project,
  flush,
  current,
  onApplied,
  onSettings,
  onClose,
}: {
  project: Project;
  flush: () => Promise<void>;
  current: () => Project;
  onApplied: (project: Project) => void;
  onSettings: (settings: QualitySettings) => void;
  onClose: () => void;
}) {
  const [report, setReport] = useState<QualityReport | null>(null),
    [dirty, setDirty] = useState(false),
    [qualityBusy, setQualityBusy] = useState(false),
    [preset, setPreset] = useState("draft"),
    [reviewed, setReviewed] = useState(false),
    [job, setJob] = useState<Job | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    const stored = sessionStorage.getItem(`jdh-job-${project.id}`);
    if (stored)
      request<Job>(`/jobs/${stored}`)
        .then(setJob)
        .catch(() => sessionStorage.removeItem(`jdh-job-${project.id}`));
  }, []);
  useEffect(() => {
    if (!job || !["running", "queued"].includes(job.status)) return;
    const timer = setInterval(
      () =>
        request<Job>(`/jobs/${job.id}`)
          .then(setJob)
          .catch((e) => setError(e.message)),
      700,
    );
    return () => clearInterval(timer);
  }, [job?.id, job?.status]);
  const start = async () => {
    setBusy(true);
    setError("");
    try {
      await flush();
      const result = await request<Job>(
        `/projects/${project.id}/render`,
        "POST",
        { preset, check_id: report?.id },
      );
      sessionStorage.setItem(`jdh-job-${project.id}`, result.id);
      setJob(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const running = job && ["running", "queued"].includes(job.status);
  return (
    <Modal title="Tinjau & ekspor" onClose={onClose} wide>
      <div className="export-body">
        <section>
          <div className="export-summary">
            <Film size={28} />
            <div>
              <h3>{project.name}</h3>
              <p className="mono subtle">
                {project.scenes.length} scene ·{" "}
                {shortTime(totalFrames(project))} · 30 fps
              </p>
            </div>
          </div>
          <Field label="Preset ekspor">
            <select
              disabled={!!running || qualityBusy}
              value={preset}
              onChange={(e) => {
                setPreset(e.target.value);
                setReport(null);
                setReviewed(false);
              }}
            >
              <option value="draft">Draft · 360×640 · H.264 / AAC</option>
              <option value="final">Final · 1080×1920 · H.264 / AAC</option>
            </select>
          </Field>
          <p className="hint">
            Paket unggah ZIP berisi MP4, caption bila ada, judul/deskripsi, dan
            laporan. Unggah ke YouTube dilakukan manual.
          </p>
          <fieldset className="pacing-fields" disabled={!!running}>
            <QualityPanel
              project={project}
              current={current}
              flush={flush}
              preset={preset}
              report={report}
              onReport={(value) => {
                setReport(value);
                setReviewed(false);
              }}
              onApplied={onApplied}
              onSettings={onSettings}
              onDirty={(value) => {
                setDirty(value);
                setReviewed(false);
              }}
              onBusy={setQualityBusy}
            />
          </fieldset>
          <label className="check review-check">
            <input
              type="checkbox"
              checked={reviewed}
              onChange={(e) => setReviewed(e.target.checked)}
            />
            Saya sudah meninjau naskah, media, dan preview.
          </label>
          {job && (
            <div className={"job-progress " + job.status}>
              <div>
                <strong>
                  {job.status === "completed"
                    ? "Ekspor selesai"
                    : job.status === "failed"
                      ? "Ekspor gagal"
                      : job.status === "cancelled"
                        ? "Ekspor dibatalkan"
                        : "Merender di perangkat Anda"}
                </strong>
                <span className="mono">{job.progress}%</span>
              </div>
              <progress value={job.progress} max={100} />
              <p className="small">{job.message}</p>
              {running && (
                <button
                  onClick={() =>
                    request<Job>(`/jobs/${job.id}/cancel`, "POST", {})
                      .then(setJob)
                      .catch((e) => setError(e.message))
                  }
                >
                  Batalkan ekspor
                </button>
              )}
            </div>
          )}
          {error && (
            <p className="error-banner" role="alert">
              {error}
            </p>
          )}
        </section>
        <section className="export-preview">
          {job?.status === "completed" ? (
            <>
              <p className="small subtle">
                Output tersimpan · {job.result?.width}×{job.result?.height} ·
                revisi {job.result?.revision}
              </p>
              {job.result?.verification && (
                <p className="success-line">
                  File terverifikasi: probe + decode lengkap,{" "}
                  {job.result.verification.frames} frame · puncak sampel audio{" "}
                  {job.result.verification.audio.peak_dbfs ?? "sunyi"} dBFS.
                </p>
              )}
              <video
                controls
                playsInline
                preload="metadata"
                aria-label="Hasil video ekspor"
                onError={() =>
                  setError(
                    "Browser tidak dapat memutar hasil ini. Unduh MP4 untuk memeriksanya di pemutar video.",
                  )
                }
                src={`/api/jobs/${job.id}/files/${job.files.find((f) => f.endsWith(".mp4"))}`}
              />
              <div className="download-list">
                {job.files.map((file) => (
                  <a
                    key={file}
                    href={`/api/jobs/${job.id}/files/${file}`}
                    download={file}
                  >
                    <Download size={14} />
                    {file}
                  </a>
                ))}
              </div>
            </>
          ) : (
            <div className="export-empty">
              <Film size={38} />
              <p>Hasil render akan tampil di sini.</p>
              <span className="subtle small">
                Periksa video sebelum mengunggahnya.
              </span>
            </div>
          )}
        </section>
      </div>
      <div className="modal-footer">
        <Status kind="ready">FFmpeg · lokal</Status>
        <div className="spacer" />
        <button onClick={onClose}>Kembali ke editor</button>
        <button
          className="primary"
          disabled={
            !!running ||
            busy ||
            qualityBusy ||
            dirty ||
            !reviewed ||
            report === null ||
            report.findings.some((f) => f.severity === "error")
          }
          onClick={start}
        >
          {busy ? (
            <Busy text="Menyiapkan…" />
          ) : job?.status === "failed" ? (
            "Coba lagi"
          ) : (
            "Mulai ekspor"
          )}
        </button>
      </div>
    </Modal>
  );
}
