import { useEffect, useRef, useState } from "react";
import { Bookmark, Sparkles, RefreshCw } from "lucide-react";
import {
  categoryLabel,
  ideaActivity,
  ideaRequest,
  localTimezone,
  type IdeaCard,
  type IdeaFeedback,
  type IdeaPreferences,
  type IdeaStatus,
} from "@/lib/dailyIdeas";
import { Field } from "./UI";
import { researchCardStale, type ResearchSource } from "@/lib/research";
import {
  metricLabels,
  metricText,
  metrics,
  type PerformanceEvidence,
} from "@/lib/performance";

export default function DailyIdeas({
  onMemory,
  onResearch,
  onSetup,
  onDraft,
  paused,
}: {
  onMemory: () => void;
  onResearch: () => void;
  onSetup: () => void;
  onDraft: (id: string) => void;
  paused: boolean;
}) {
  const [status, setStatus] = useState<IdeaStatus | null>(null);
  const [form, setForm] = useState<IdeaPreferences | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [settings, setSettings] = useState(false);
  const current = useRef<IdeaStatus | null>(null);
  const mounted = useRef(false);
  const working = useRef(false);
  const version = useRef(0);
  const pending = useRef<string | null>(null);
  const automatic = useRef(new Set<string>());
  const formDirty = useRef(false);
  function accept(next: IdeaStatus) {
    if (!mounted.current) return;
    current.current = next;
    setStatus(next);
    if (!formDirty.current) setForm(next.preferences);
  }
  async function generate(auto: boolean) {
    if (working.current) return;
    version.current += 1;
    working.current = true;
    setBusy(true);
    setError("");
    const id = crypto.randomUUID();
    pending.current = id;
    try {
      accept(
        await ideaRequest("/generate", "POST", {
          id,
          timezone: localTimezone(),
          automatic: auto,
        }),
      );
    } catch (e) {
      if (mounted.current) setError((e as Error).message);
      // An uncertain POST must not leave unobserved inference running.
      void ideaRequest(
        `/requests/${id}/cancel?timezone=${encodeURIComponent(localTimezone())}`,
        "POST",
        {},
      ).catch(() => undefined);
    } finally {
      pending.current = null;
      working.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  useEffect(() => {
    mounted.current = true;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        if (
          !working.current &&
          document.visibilityState === "visible" &&
          !paused
        ) {
          const snapshot = version.current;
          const next = await ideaRequest(
            `/status?timezone=${encodeURIComponent(localTimezone())}`,
          );
          if (disposed || working.current || version.current !== snapshot)
            return;
          accept(next);
          setError("");
          const key = `${next.date}/${next.timezone}/${next.settings_revision}`;
          if (
            next.auto_due &&
            next.can_generate &&
            !formDirty.current &&
            !automatic.current.has(key)
          ) {
            automatic.current.add(key);
            await generate(true);
          }
        }
      } catch (e) {
        if (!disposed) {
          setError((e as Error).message);
          // Do not display references that the catalogue could no longer validate.
          current.current = null;
          setStatus(null);
        }
      } finally {
        if (!disposed) timer = setTimeout(() => void poll(), 2500);
      }
    }
    const visibility = () => {
      void ideaActivity(paused || document.visibilityState !== "visible").catch(
        () => undefined,
      );
    };
    visibility();
    document.addEventListener("visibilitychange", visibility);
    void poll();
    return () => {
      disposed = true;
      mounted.current = false;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", visibility);
      void ideaActivity(true).catch(() => undefined);
      const id = pending.current || current.current?.active_id;
      if (id)
        void ideaRequest(
          `/requests/${id}/cancel?timezone=${encodeURIComponent(localTimezone())}`,
          "POST",
          {},
        ).catch(() => undefined);
    };
    // Polling deliberately reads current state from refs and has one loop per visible home instance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paused]);

  async function change(path: string, method: string, body?: unknown) {
    if (working.current) return;
    version.current += 1;
    working.current = true;
    setBusy(true);
    setError("");
    try {
      accept(await ideaRequest(path, method, body));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      working.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  function edit(patch: Partial<IdeaPreferences>) {
    formDirty.current = true;
    setForm((value) => (value ? { ...value, ...patch } : value));
  }
  async function savePreferences(event: React.FormEvent) {
    event.preventDefault();
    if (!status || !form || working.current) return;
    version.current += 1;
    working.current = true;
    setBusy(true);
    setError("");
    try {
      const next = await ideaRequest("/preferences", "PUT", {
        timezone: localTimezone(),
        revision: status.settings_revision,
        preferences: form,
      });
      formDirty.current = false;
      accept(next);
      setSettings(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      working.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  const feedback = (
    card: IdeaCard,
    verdict: "saved" | "skipped" | "none",
    reason: string,
  ) =>
    change(`/cards/${card.id}/feedback`, "PUT", {
      timezone: localTimezone(),
      verdict,
      reason,
    });
  const saved =
    status?.feedback.filter(
      (f) =>
        f.verdict === "saved" &&
        f.source_mode === status.preferences.source_mode,
    ) || [];
  return (
    <section className="daily-ideas" aria-labelledby="daily-ideas-title">
      <div className="ideas-heading">
        <div>
          <div className="eyebrow">
            <Sparkles size={14} /> GEMINI NANO · LOKAL
          </div>
          <h2 id="daily-ideas-title">Ide hari ini</h2>
          <p className="subtle">
            {status
              ? `${status.date} · ${status.timezone} · ${status.preferences.source_mode === "research" ? "Referensi riset · Manual" : status.preferences.mode === "daily" ? "Riwayat · Otomatis harian" : "Riwayat · Manual"}`
              : "Memuat ide tersimpan…"}
          </p>
        </div>
        <div className="ideas-actions">
          <button onClick={() => setSettings(!settings)} disabled={!status}>
            {settings ? "Tutup preferensi" : "Preferensi ide"}
            {formDirty.current ? " *" : ""}
          </button>
          {status?.active_id ? (
            <button
              onClick={() =>
                void change(
                  `/requests/${status.active_id}/cancel?timezone=${encodeURIComponent(localTimezone())}`,
                  "POST",
                  {},
                )
              }
              disabled={busy}
            >
              Batal
            </button>
          ) : (
            <button
              className="primary"
              disabled={
                busy || !status?.can_generate || formDirty.current || paused
              }
              onClick={() => void generate(false)}
            >
              <RefreshCw size={15} />
              {status?.retry_after
                ? `Tunggu ${status.retry_after} dtk`
                : "Ide baru"}
            </button>
          )}
        </div>
      </div>
      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
      {status && (
        <p className="hint" role="status">
          {status.active_id
            ? "Nano sedang menyusun tiga ide di perangkat ini…"
            : status.message}
        </p>
      )}
      {(settings || status?.onboarding) && form && (
        <form className="idea-preferences" onSubmit={savePreferences}>
          <Field label="Dasar ide">
            <select
              value={form.source_mode}
              onChange={(e) =>
                edit({
                  source_mode: e.target.value as IdeaPreferences["source_mode"],
                })
              }
            >
              <option value="history">Riwayat video & performa</option>
              <option value="research">Referensi riset · sumber pilihan</option>
            </select>
          </Field>
          <Field label="Mode">
            <select
              disabled={form.source_mode === "research"}
              value={form.source_mode === "research" ? "manual" : form.mode}
              onChange={(e) =>
                edit({ mode: e.target.value as IdeaPreferences["mode"] })
              }
            >
              <option value="daily">
                Harian — maksimal sekali per hari saat beranda dibuka
              </option>
              <option value="manual">
                Manual — hanya lewat tombol Ide baru
              </option>
            </select>
          </Field>
          <Field label="Bahasa ide">
            <select
              value={form.language}
              onChange={(e) =>
                edit({
                  language: e.target.value as IdeaPreferences["language"],
                })
              }
            >
              <option value="en">English · Nano lokal</option>
              <option value="id">Indonesia · panduan manual</option>
            </select>
          </Field>
          <Field label="Topik channel">
            <input
              maxLength={240}
              placeholder="Contoh: tutorial SwiftUI untuk pemula"
              value={form.topic}
              onChange={(e) => edit({ topic: e.target.value })}
            />
          </Field>
          <Field label="Audiens (opsional)">
            <input
              maxLength={160}
              value={form.audience}
              onChange={(e) => edit({ audience: e.target.value })}
            />
          </Field>
          <div className="ideas-actions">
            <button className="primary" disabled={busy}>
              Simpan preferensi
            </button>
            <button
              type="button"
              onClick={() => {
                formDirty.current = false;
                setForm(status?.preferences || null);
                setSettings(false);
              }}
            >
              Batalkan perubahan
            </button>
          </div>
        </form>
      )}
      {status?.batch ? (
        <>
          <p className="hint">
            {status.stale
              ? "Ide tersimpan dari konteks sebelumnya"
              : "Usulan Gemini Nano lokal"}{" "}
            · {new Date(status.batch.created_at).toLocaleString("id-ID")} (
            {status.batch.timezone}) · {status.batch.language.toUpperCase()}.
            Tinjau sebelum digunakan.
          </p>
          <div className="idea-grid">
            {status.batch.cards.map((card) => (
              <IdeaTile
                key={card.id}
                card={card}
                names={status.source_names}
                evidence={status.performance_evidence}
                researchEvidence={status.research_evidence}
                feedback={status.feedback.find((f) => f.card.id === card.id)}
                busy={busy}
                onFeedback={feedback}
                onDraft={onDraft}
              />
            ))}
          </div>
        </>
      ) : (
        !status?.active_id &&
        status && (
          <div className="idea-guide">
            <strong>Panduan manual · bukan hasil AI</strong>
            <p>
              {status.preferences.source_mode === "research"
                ? "Tambahkan catatan sumber, periksa tanggal dan konflik, lalu klik Ide baru setelah Nano terhubung. Sumber tidak diambil otomatis."
                : status.source_count
                  ? "Pilih satu video referensi, lanjutkan pertanyaan yang belum terjawab, jelaskan dari sudut lain, atau coba contoh yang lebih singkat."
                  : "Mulai dari satu masalah audiens. Rencanakan satu seri baru, satu cara menjelaskan yang berbeda, dan satu eksperimen sederhana."}
            </p>
            <span className="hint">
              Ide tidak mengasumsikan tren atau performa YouTube.
            </span>
          </div>
        )
      )}
      {saved.length > 0 && status && (
        <details className="saved-ideas">
          <summary>
            <Bookmark size={15} /> Ide tersimpan ({saved.length}/30)
          </summary>
          <div className="idea-grid">
            {saved.map((entry) => (
              <IdeaTile
                key={entry.card.id}
                card={entry.card}
                names={status.source_names}
                evidence={status.performance_evidence}
                researchEvidence={status.research_evidence}
                feedback={entry}
                busy={busy}
                onFeedback={feedback}
                onDraft={onDraft}
              />
            ))}
          </div>
        </details>
      )}
      <div className="ideas-links">
        <button onClick={onMemory}>Pilih referensi di Memori</button>
        <button onClick={onResearch}>Kelola sumber riset</button>
        <button onClick={onSetup}>Hubungkan Nano di Setup</button>
        <span className="hint">
          Cache dibuka lebih dulu; pembuatan ide menunggu editor dan render
          selesai.
        </span>
      </div>
    </section>
  );
}

function IdeaTile({
  card,
  names,
  evidence,
  researchEvidence,
  feedback,
  busy,
  onFeedback,
  onDraft,
}: {
  card: IdeaCard;
  onDraft: (id: string) => void;
  names: Record<string, string>;
  evidence: Record<string, PerformanceEvidence>;
  researchEvidence: Record<string, ResearchSource>;
  feedback?: IdeaFeedback;
  busy: boolean;
  onFeedback: (
    card: IdeaCard,
    verdict: "saved" | "skipped" | "none",
    reason: string,
  ) => Promise<void>;
}) {
  const [reason, setReason] = useState(feedback?.reason || "");
  useEffect(() => {
    setReason(feedback?.reason || "");
  }, [feedback?.reason]);
  return (
    <article
      className={`idea-card ${feedback?.verdict === "skipped" ? "idea-skipped" : ""}`}
    >
      <div className="eyebrow">
        {categoryLabel(card)} <span>{card.estimated_seconds} dtk</span>
      </div>
      <h3>{card.title}</h3>
      <blockquote>{card.hook}</blockquote>
      <p>{card.concept}</p>
      <dl>
        <dt>Alasan</dt>
        <dd>{card.reason}</dd>
        <dt>Perbedaannya</dt>
        <dd>{card.difference}</dd>
        <dt>Kebutuhan media</dt>
        <dd>{card.media_needs.join(" · ")}</dd>
        <dt>Referensi</dt>
        <dd>
          {card.source_project_ids.length
            ? card.source_project_ids
                .map((id) => names[id] || "Referensi proyek")
                .join(" · ")
            : card.research_claims?.length
              ? "Referensi riset pilihan; lihat data sumber di bawah."
              : "Preferensi channel; belum memakai video sebelumnya."}
        </dd>
      </dl>
      {feedback?.performance_stale ? (
        <p className="hint">
          Data performa berubah. Buat ide baru sebelum menyusun draft dari
          rekomendasi ini.
        </p>
      ) : (
        (card.performance_ids || []).map((id) => {
          const row = evidence[id];
          return row ? (
            <details key={id} className="idea-evidence">
              <summary>
                Data pendukung · {names[row.project_id] || "Referensi"}
              </summary>
              <p>
                {row.period_start} – {row.period_end} · {row.report_timezone}
                <br />
                Umur awal {row.start_age_days} hari · periode {row.period_days}{" "}
                hari
                <br />
                {row.definition === "custom"
                  ? row.definition_note
                  : "YouTube · engaged views v1"}
                <br />
                Sumber: {row.source}
                <br />
                Diambil: {row.captured_at}
              </p>
              <dl className="performance-metrics">
                {metrics.map((key) => (
                  <div key={key}>
                    <dt>{metricLabels[key]}</dt>
                    <dd>{metricText(row[key])}</dd>
                  </div>
                ))}
              </dl>
              <p className="hint">
                Input diperiksa pengguna. Alasan ide adalah hipotesis, bukan
                bukti sebab-akibat.
              </p>
            </details>
          ) : (
            <p key={id} className="hint">
              Bukti performa tidak lagi tersedia pada konteks aktif.
            </p>
          );
        })
      )}
      {(card.research_claims || []).map((claim, index) => {
        const source = researchEvidence[claim.source_id];
        return (
          <details className="idea-evidence research-evidence" key={index}>
            <summary>
              Dasar riset · {source?.title || "Sumber tidak tersedia"}
            </summary>
            <p>{claim.claim}</p>
            <blockquote>{claim.quote}</blockquote>
            <p className="hint">
              Cuplikan catatan{" "}
              {source?.kind === "summary" ? "ringkasan pengguna" : "sumber"};
              kecocokan teks diperiksa, kebenaran klaim tetap perlu ditinjau.
            </p>
            {source && (
              <>
                <p className="hint">
                  Publikasi {source.published_on || "tidak diketahui"} · akses{" "}
                  {source.accessed_on}
                </p>
                {source.url && (
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    Buka sumber
                  </a>
                )}
                {source.caution && <p className="hint">{source.caution}</p>}
              </>
            )}
          </details>
        );
      })}
      {(feedback?.research_stale ||
        researchCardStale(card.research_claims, researchEvidence)) && (
        <p className="hint">
          Sumber riset berubah, kedaluwarsa, atau tidak tersedia. Buat ide baru
          sebelum menyusun draft.
        </p>
      )}
      <label className="idea-reason">
        Alasan simpan/lewati (opsional)
        <input
          maxLength={300}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </label>
      <div className="ideas-actions">
        <button
          disabled={
            busy ||
            feedback?.performance_stale ||
            feedback?.research_stale ||
            researchCardStale(card.research_claims, researchEvidence)
          }
          onClick={() => onDraft(card.id)}
        >
          Susun draft
        </button>
        <button
          disabled={busy}
          className={feedback?.verdict === "saved" ? "primary" : ""}
          onClick={() => void onFeedback(card, "saved", reason)}
        >
          <Bookmark size={14} />
          {feedback?.verdict === "saved" ? "Tersimpan" : "Simpan"}
        </button>
        <button
          disabled={busy}
          onClick={() => void onFeedback(card, "skipped", reason)}
        >
          {feedback?.verdict === "skipped" ? "Dilewati" : "Lewati"}
        </button>
        {feedback && (
          <button
            disabled={busy}
            onClick={() => void onFeedback(card, "none", "")}
          >
            Urungkan
          </button>
        )}
      </div>
    </article>
  );
}
