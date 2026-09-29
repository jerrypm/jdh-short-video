import { useEffect, useState } from "react";
import { ArrowLeft, BarChart3, RefreshCw } from "lucide-react";
import { Brand, Field, Modal } from "./UI";
import { request } from "@/lib/api";
import {
  emptyMeasurement,
  measurementOnly,
  metricLabels,
  metricText,
  metrics,
  numericMetric,
  performanceRequest,
  type ImportReview,
  type Measurement,
  type PerformanceRecord,
  type PerformanceView,
} from "@/lib/performance";

const actionLabels = {
  add: "Baru",
  duplicate: "Duplikat · dilewati",
  conflict: "Konflik · belum bisa disimpan",
  replace: "Ganti angka tersimpan",
};
const definitionLabel = (row: {
  definition: string;
  definition_note: string;
}) =>
  row.definition === "custom"
    ? `Khusus: ${row.definition_note}`
    : "YouTube · engaged views v1";

export default function Performance({ onBack }: { onBack: () => void }) {
  const [data, setData] = useState<PerformanceView | null>(null);
  const [form, setForm] = useState<Measurement>(emptyMeasurement);
  const [mode, setMode] = useState<"manual" | "csv">("manual");
  const [rows, setRows] = useState<Measurement[]>([]);
  const [csvName, setCsvName] = useState("");
  const [replace, setReplace] = useState(false);
  const [review, setReview] = useState<ImportReview | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [excluding, setExcluding] = useState<PerformanceRecord | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [page, setPage] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    // Abort on navigation so a late response cannot replace the new screen's state.
    void request<PerformanceView>(
      "/performance",
      "GET",
      undefined,
      controller.signal,
    )
      .then(setData)
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, []);
  async function work(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const names = Object.fromEntries(
    data?.projects.map((p) => [p.id, p.name]) || [],
  );
  const projectOptions = (
    <>
      <option value="">Pilih proyek…</option>
      {data?.projects.map((p) => (
        <option key={p.id} value={p.id}>
          {p.name}
        </option>
      ))}
    </>
  );
  const edit = (patch: Partial<Measurement>) =>
    setForm((old) => ({ ...old, ...patch }));
  async function preview() {
    if (!data) return;
    setConfirmed(false);
    setReview(
      await performanceRequest<ImportReview>("/preview", "POST", {
        revision: data.revision,
        rows: mode === "csv" ? rows : [form],
        origin: mode,
        replace_conflicts: replace,
      }),
    );
  }
  async function include(
    row: PerformanceRecord,
    included: boolean,
    explanation = "",
  ) {
    if (!data) return;
    setData(
      await performanceRequest<PerformanceView>(`/${row.id}/inclusion`, "PUT", {
        revision: data.revision,
        included,
        reason: explanation,
      }),
    );
    setExcluding(null);
    setNotice(
      included
        ? "Video kembali disertakan dalam ringkasan."
        : "Seluruh pengukuran video ini dikecualikan dari ringkasan dan konteks ide.",
    );
  }
  const ordered = [...(data?.records || [])].reverse();
  return (
    <div className="memory-page performance-page">
      <header className="home-header">
        <Brand />
        <div className="spacer" />
        <button onClick={onBack} disabled={busy}>
          <ArrowLeft size={16} />
          Beranda
        </button>
      </header>
      <main className="memory-main">
        <div className="section-head">
          <div>
            <div className="eyebrow">DATA VIDEO · TERSIMPAN LOKAL</div>
            <h1>
              <BarChart3 size={24} />
              Performa video
            </h1>
            <p className="subtle">
              Impor laporan atau catat angka yang sudah Anda periksa.
            </p>
          </div>
          <button
            disabled={busy}
            onClick={() =>
              void work(async () => {
                setReview(null);
                setData(await performanceRequest<PerformanceView>());
              })
            }
          >
            <RefreshCw size={16} />
            Muat ulang
          </button>
        </div>
        {error && (
          <p role="alert" className="error-banner">
            {error}
          </p>
        )}
        {notice && (
          <p role="status" className="success-banner">
            {notice}
          </p>
        )}
        <p className="hint">
          Kosong (—) berarti tidak tersedia; 0 berarti nol. Angka berasal dari
          input Anda, belum diautentikasi oleh YouTube. Hanya proyek referensi
          yang dipilih di Memori konten dapat memberi konteks ke Gemini Nano
          lokal.
        </p>
        <section className="memory-card">
          <h2>Tambah pengukuran</h2>
          <div className="ideas-actions">
            <button
              aria-pressed={mode === "manual"}
              className={mode === "manual" ? "active" : ""}
              disabled={busy}
              onClick={() => setMode("manual")}
            >
              Input manual
            </button>
            <button
              aria-pressed={mode === "csv"}
              className={mode === "csv" ? "active" : ""}
              disabled={busy}
              onClick={() => setMode("csv")}
            >
              Impor CSV
            </button>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void work(preview);
            }}
          >
            <fieldset disabled={busy || !data}>
              {mode === "manual" ? (
                <>
                  <div className="performance-form">
                    <Field label="Proyek">
                      <select
                        required
                        value={form.project_id}
                        onChange={(e) => edit({ project_id: e.target.value })}
                      >
                        {projectOptions}
                      </select>
                    </Field>
                    <Field label="YouTube video ID (11 karakter)">
                      <input
                        required
                        pattern="[A-Za-z0-9_-]{11}"
                        maxLength={11}
                        placeholder="Contoh: aB3dE6gH9_k"
                        value={form.video_id}
                        onChange={(e) => edit({ video_id: e.target.value })}
                      />
                    </Field>
                    <Field label="Tanggal publikasi">
                      <input
                        type="date"
                        required
                        value={form.published_on}
                        onChange={(e) => edit({ published_on: e.target.value })}
                      />
                    </Field>
                    <Field label="Periode mulai (inklusif)">
                      <input
                        type="date"
                        required
                        value={form.period_start}
                        onChange={(e) => edit({ period_start: e.target.value })}
                      />
                    </Field>
                    <Field label="Periode akhir (inklusif)">
                      <input
                        type="date"
                        required
                        value={form.period_end}
                        onChange={(e) => edit({ period_end: e.target.value })}
                      />
                    </Field>
                    <Field label="Zona waktu laporan · periksa sumber">
                      <input
                        required
                        maxLength={80}
                        value={form.report_timezone}
                        onChange={(e) =>
                          edit({ report_timezone: e.target.value })
                        }
                      />
                    </Field>
                    <Field label="Sumber laporan">
                      <input
                        required
                        maxLength={120}
                        placeholder="Contoh: YouTube Studio, ekspor 28 Sep"
                        value={form.source}
                        onChange={(e) => edit({ source: e.target.value })}
                      />
                    </Field>
                    <Field label="Waktu data diambil · ISO dengan offset">
                      <input
                        required
                        maxLength={40}
                        value={form.captured_at}
                        onChange={(e) => edit({ captured_at: e.target.value })}
                      />
                    </Field>
                    <Field label="Definisi metrik">
                      <select
                        value={form.definition}
                        onChange={(e) =>
                          edit({
                            definition: e.target
                              .value as Measurement["definition"],
                          })
                        }
                      >
                        <option value="youtube_engaged_views_v1">
                          YouTube · engaged views v1
                        </option>
                        <option value="custom">
                          Definisi khusus / laporan lain
                        </option>
                      </select>
                    </Field>
                    {form.definition === "custom" && (
                      <Field label="Jelaskan definisi dan batasan laporan">
                        <input
                          required
                          maxLength={120}
                          value={form.definition_note}
                          onChange={(e) =>
                            edit({ definition_note: e.target.value })
                          }
                        />
                      </Field>
                    )}
                  </div>
                  <p className="hint">
                    Engaged views bukan total Views. Durasi dalam detik;
                    persentase boleh lebih dari 100%. Hanya isi metrik yang
                    tersedia pada laporan video Anda.
                  </p>
                  <div className="performance-form metrics-form">
                    {metrics.map((key) => (
                      <Field key={key} label={metricLabels[key]}>
                        <input
                          type="number"
                          min="0"
                          max={
                            key === "average_view_percentage"
                              ? 10000
                              : key === "average_view_duration_seconds"
                                ? 86400
                                : 1e12
                          }
                          step={key.startsWith("average") ? "any" : "1"}
                          placeholder="Tidak tersedia"
                          value={form[key] ?? ""}
                          onChange={(e) => {
                            try {
                              edit({ [key]: numericMetric(e.target.value) });
                            } catch (error) {
                              setError((error as Error).message);
                            }
                          }}
                        />
                      </Field>
                    ))}
                  </div>
                </>
              ) : (
                <div className="performance-csv">
                  <p>
                    Gunakan kolom template, UTF-8, pemisah koma, desimal titik,
                    tanpa pemisah ribuan atau tanda %. Kolom project_id boleh
                    kosong lalu dipetakan di sini. Ekspor Studio dengan header
                    berbeda perlu disesuaikan dahulu.
                  </p>
                  <a
                    className="text-link"
                    href="/api/performance/template"
                    download="jdh-performance-template.csv"
                  >
                    Unduh template CSV
                  </a>
                  <Field label="Pilih CSV · maksimal 40 KB / 100 baris">
                    <input
                      type="file"
                      accept=".csv,text/csv"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        e.target.value = "";
                        if (!file) return;
                        setRows([]);
                        setCsvName("");
                        void work(async () => {
                          if (file.size > 40000)
                            throw new Error("CSV maksimal 40 KB.");
                          const parsed = await performanceRequest<{
                            rows: Measurement[];
                          }>("/parse", "POST", { csv: await file.text() });
                          setRows(parsed.rows);
                          setCsvName(file.name);
                        });
                      }}
                    />
                  </Field>
                  {rows.length > 0 && (
                    <>
                      <p>
                        {csvName} · {rows.length} pengukuran. Periksa pemetaan
                        setiap video.
                      </p>
                      <div className="performance-table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Video / periode</th>
                              <th>Proyek tujuan</th>
                              <th>Data</th>
                            </tr>
                          </thead>
                          <tbody>
                            {rows.map((row, index) => (
                              <tr key={index}>
                                <td>
                                  {row.video_id}
                                  <small>
                                    {row.period_start} – {row.period_end}
                                  </small>
                                </td>
                                <td>
                                  <select
                                    aria-label={`Proyek baris ${index + 1}`}
                                    required
                                    value={row.project_id}
                                    onChange={(e) =>
                                      setRows((old) =>
                                        old.map((r, i) =>
                                          i === index
                                            ? {
                                                ...r,
                                                project_id: e.target.value,
                                              }
                                            : r,
                                        ),
                                      )
                                    }
                                  >
                                    {projectOptions}
                                  </select>
                                </td>
                                <td>
                                  <MeasurementDetails row={row} />
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </div>
              )}
              <label className="check-field">
                <input
                  type="checkbox"
                  checked={replace}
                  onChange={(e) => setReplace(e.target.checked)}
                />
                Izinkan koreksi angka untuk video, periode, dan definisi yang
                sama (tetap ditinjau dahulu).
              </label>
              <button
                className="primary"
                disabled={busy || !data || (mode === "csv" && !rows.length)}
              >
                Pratinjau {mode === "csv" ? "impor" : "pengukuran"}
              </button>
            </fieldset>
          </form>
        </section>
        {data && (
          <>
            <section className="memory-card performance-section">
              <h2>Ringkasan yang bisa dibandingkan</h2>
              <p className="hint">
                {data.notice} Satu snapshot terbaru per video; periode yang
                tumpang tindih tidak dijumlahkan. Median merangkum video, bukan
                rata-rata seluruh penonton.
              </p>
              {!data.cohorts.length ? (
                <p>Belum ada pengukuran aktif.</p>
              ) : (
                <div className="performance-cohorts">
                  {data.cohorts.map((cohort, index) => (
                    <article key={index}>
                      <strong>
                        {cohort.video_count} video · jendela{" "}
                        {cohort.period_days} hari
                      </strong>
                      <p>
                        Mulai umur {cohort.start_age_days} hari ·{" "}
                        {cohort.report_timezone}
                        <br />
                        {definitionLabel(cohort)}
                      </p>
                      {cohort.video_count < 5 && (
                        <p className="hint">
                          Sampel kecil: belum menyimpulkan pola.
                        </p>
                      )}
                      <dl className="performance-metrics">
                        {metrics.map((key) => (
                          <div key={key}>
                            <dt>{metricLabels[key]}</dt>
                            <dd>
                              {metricText(cohort.medians[key])}{" "}
                              <small>
                                (n={cohort.metric_counts[key]}
                                {cohort.metric_counts[key] < 5
                                  ? "; butuh 5"
                                  : ""}
                                )
                              </small>
                            </dd>
                          </div>
                        ))}
                      </dl>
                    </article>
                  ))}
                </div>
              )}
            </section>
            <section className="memory-card performance-section">
              <h2>Riwayat pengukuran · {data.records.length}</h2>
              <p className="hint">
                Pengecualian berlaku untuk semua periode video tersebut,
                termasuk impor berikutnya. Koreksi hanya mengganti snapshot yang
                sama; periode berbeda tetap tersimpan.
              </p>
              {!ordered.length ? (
                <p>Tambahkan data pertama melalui formulir atau CSV.</p>
              ) : (
                <>
                  <div className="performance-table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Video / proyek</th>
                          <th>Periode & sumber</th>
                          <th>Metrik</th>
                          <th>Pemakaian</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ordered.slice(page * 25, page * 25 + 25).map((row) => (
                          <tr key={row.id}>
                            <td>
                              <strong>
                                {names[row.project_id] ||
                                  "Proyek tidak tersedia"}
                              </strong>
                              <small>{row.video_id}</small>
                              <small>Publikasi {row.published_on}</small>
                            </td>
                            <td>
                              {row.period_start} – {row.period_end}
                              <small>
                                {row.report_timezone} · {definitionLabel(row)}
                              </small>
                              <small>{row.source}</small>
                              <small>Diambil {row.captured_at}</small>
                              <small>
                                Disimpan {row.imported_at} · {row.origin}
                              </small>
                            </td>
                            <td>
                              <MetricList row={row} />
                            </td>
                            <td>
                              <p>
                                {!row.included
                                  ? `Dikecualikan: ${row.exclusion_reason}`
                                  : !names[row.project_id]
                                    ? "Proyek tidak tersedia"
                                    : !data.latest_ids.includes(row.id)
                                      ? "Snapshot lama"
                                      : data.ai_project_ids.includes(
                                            row.project_id,
                                          )
                                        ? "Layak konteks Nano lokal*"
                                        : "Belum dipilih di Memori"}
                              </p>
                              <div className="ideas-actions">
                                <button
                                  disabled={busy}
                                  onClick={() => {
                                    setForm(measurementOnly(row));
                                    setMode("manual");
                                    setReplace(true);
                                    document
                                      .querySelector(".performance-page")
                                      ?.scrollTo({
                                        top: 0,
                                        behavior: "smooth",
                                      });
                                  }}
                                >
                                  Koreksi
                                </button>
                                <button
                                  disabled={busy}
                                  onClick={() => {
                                    if (row.included) {
                                      setExcluding(row);
                                      setReason("");
                                    } else void work(() => include(row, true));
                                  }}
                                >
                                  {row.included
                                    ? "Kecualikan video"
                                    : "Sertakan video"}
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="ideas-actions">
                    <button disabled={!page} onClick={() => setPage(page - 1)}>
                      Sebelumnya
                    </button>
                    <span>
                      Halaman {page + 1} / {Math.ceil(ordered.length / 25)}
                    </span>
                    <button
                      disabled={(page + 1) * 25 >= ordered.length}
                      onClick={() => setPage(page + 1)}
                    >
                      Berikutnya
                    </button>
                  </div>
                </>
              )}
              <p className="hint">
                *Konteks ide memakai maksimal 5 snapshot dari referensi yang
                cocok dengan bahasa dan batas konteks. Perubahan data
                membatalkan ide yang sedang dibuat; ide tersimpan diberi tanda
                perlu diperbarui.
              </p>
            </section>
          </>
        )}
      </main>
      {review && (
        <Modal
          title="Tinjau pengukuran sebelum disimpan"
          wide
          onClose={() => {
            if (!busy) setReview(null);
          }}
        >
          <div className="performance-review">
            {error && (
              <p role="alert" className="error-banner">
                {error}
              </p>
            )}
            {review.actions.map((action) => (
              <article key={action.id}>
                <h3>
                  {actionLabels[action.action]} · {names[action.row.project_id]}
                </h3>
                <MeasurementDetails row={action.row} />
                {action.previous && action.action !== "duplicate" && (
                  <details>
                    <summary>Angka sebelumnya</summary>
                    <MeasurementDetails row={action.previous} />
                  </details>
                )}
              </article>
            ))}
            <p className="hint">
              Duplikat tidak mengubah angka, sumber, atau waktu pengambilan
              sebelumnya. Konflik harus diselesaikan sebelum seluruh impor dapat
              disimpan.
            </p>
            <label className="check-field">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
                disabled={busy}
              />
              Saya sudah memeriksa pemetaan, periode, definisi, dan angka; data
              aktif boleh digunakan sebagai konteks ide lokal.
            </label>
          </div>
          <div className="ideas-actions">
            <button disabled={busy} onClick={() => setReview(null)}>
              Kembali
            </button>
            <button
              className="primary"
              disabled={busy || !review.can_apply || !confirmed}
              onClick={() =>
                void work(async () => {
                  setData(
                    await performanceRequest<PerformanceView>(
                      "/apply",
                      "POST",
                      { review_id: review.review_id, reviewed: true },
                    ),
                  );
                  setReview(null);
                  setNotice(
                    "Pengukuran tersimpan. Duplikat dilewati; konteks ide memakai data terbaru yang disertakan.",
                  );
                })
              }
            >
              {busy ? "Menyimpan…" : "Simpan pengukuran"}
            </button>
          </div>
        </Modal>
      )}
      {excluding && (
        <Modal
          title={`Kecualikan video ${excluding.video_id}`}
          onClose={() => {
            if (!busy) setExcluding(null);
          }}
        >
          <div className="performance-exclusion">
            <p>
              Semua periode video ini tetap tersimpan, tetapi tidak dipakai
              dalam ringkasan dan rekomendasi ide.
            </p>
            {error && (
              <p role="alert" className="error-banner">
                {error}
              </p>
            )}
            <Field label="Alasan pengecualian">
              <input
                autoFocus
                maxLength={240}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Contoh: kampanye berbayar, trafik tidak sebanding"
              />
            </Field>
            <button
              className="primary"
              disabled={busy || !reason.trim()}
              onClick={() => void work(() => include(excluding, false, reason))}
            >
              Kecualikan video
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

export function MetricList({
  row,
}: {
  row: Pick<Measurement, keyof typeof metricLabels>;
}) {
  return (
    <dl className="performance-metrics">
      {metrics.map((key) => (
        <div key={key}>
          <dt>{metricLabels[key]}</dt>
          <dd>{metricText(row[key])}</dd>
        </div>
      ))}
    </dl>
  );
}
function MeasurementDetails({ row }: { row: Measurement }) {
  return (
    <div className="performance-details">
      <p>
        {row.video_id} · publikasi {row.published_on}
        <br />
        {row.period_start} – {row.period_end} · {row.report_timezone}
        <br />
        {definitionLabel(row)}
        <br />
        Sumber: {row.source} · diambil {row.captured_at}
      </p>
      <MetricList row={row} />
    </div>
  );
}
