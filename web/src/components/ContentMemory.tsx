import { useEffect, useState } from "react";
import { ArrowLeft, BookOpen, Plus, RefreshCw, Search } from "lucide-react";
import { request } from "@/lib/api";
import {
  type MemoryView,
  type MemoryReference,
  type ChannelProfile,
  type ReferenceUpdate,
  type IdeaFeedback,
  type MemoryContext,
  isActiveReference,
  memoryStatus,
  parseThemes,
} from "@/lib/contentMemory";
import { Brand, Field, Status, Busy, Modal } from "./UI";

const verdictLabels = {
  saved: "Disimpan",
  skipped: "Dilewati",
  used: "Dipakai",
};

export default function ContentMemory({ onBack }: { onBack: () => void }) {
  const [data, setData] = useState<MemoryView | null>(null);
  const [tab, setTab] = useState<"references" | "profile" | "search">(
    "references",
  );
  const [selected, setSelected] = useState("");
  const [adding, setAdding] = useState(false);
  const [forget, setForget] = useState<MemoryReference | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dirty, setDirty] = useState(false);
  const load = async () => {
    setBusy(true);
    setError("");
    try {
      setData(await request<MemoryView>("/memory"));
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    const controller = new AbortController();
    void request<MemoryView>("/memory", "GET", undefined, controller.signal)
      .then(setData)
      .catch((error) => {
        if (!controller.signal.aborted) setError(error.message);
      });
    return () => controller.abort();
  }, []);
  const mutate = async (path: string, method: string, values: object) => {
    if (!data) return false;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      setData(
        await request<MemoryView>("/memory" + path, method, {
          revision: data.catalog.revision,
          ...values,
        }),
      );
      setNotice("Memori tersimpan di perangkat ini.");
      return true;
    } catch (error) {
      setError((error as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  };
  const references = data?.catalog.references ?? [];
  const active = references.filter(isActiveReference).length;
  const current =
    references.find((ref) => ref.project_id === selected) ?? references[0];
  return (
    <div className="memory-page">
      <header className="home-header">
        <button onClick={onBack} disabled={busy || dirty}>
          <ArrowLeft size={15} />
          Kembali
        </button>
        <Brand />
        <div className="spacer" />
        <Status kind="ready">Tersimpan lokal</Status>
      </header>
      <main className="memory-main">
        <div className="section-head">
          <div>
            <div className="eyebrow">RIWAYAT PILIHAN ANDA</div>
            <h1>
              <BookOpen size={25} /> Memori konten
            </h1>
            <p className="subtle">
              Pilih karya yang boleh menjadi referensi. Ringkasan dan label ini
              menjadi dasar bantuan ide berikutnya.
            </p>
          </div>
          <div className="spacer" />
          <button onClick={() => void load()} disabled={busy || dirty}>
            <RefreshCw size={15} />
            Muat ulang
          </button>
        </div>
        <p className="memory-policy">
          {active} referensi aktif dari {references.length} pilihan · QA,
          duplikat, dan referensi yang dikecualikan tidak dipakai dalam
          pencarian konteks. Ekspor tidak otomatis berarti sudah dipublikasikan.
        </p>
        {error && (
          <p role="alert" className="error-banner">
            {error}
          </p>
        )}
        {notice && (
          <p role="status" className="memory-notice">
            {notice}
          </p>
        )}
        {dirty && (
          <p className="memory-policy">
            Ada perubahan belum disimpan. Simpan atau batalkan perubahan sebelum
            berpindah bagian.
          </p>
        )}
        <nav className="memory-tabs" aria-label="Bagian memori">
          <button
            className={tab === "references" ? "active" : ""}
            onClick={() => setTab("references")}
            disabled={busy || dirty}
          >
            Referensi proyek
          </button>
          <button
            className={tab === "profile" ? "active" : ""}
            onClick={() => setTab("profile")}
            disabled={busy || dirty}
          >
            Profil channel
          </button>
          <button
            className={tab === "search" ? "active" : ""}
            onClick={() => setTab("search")}
            disabled={busy || dirty}
          >
            Cari konteks
          </button>
        </nav>
        {!data && !error && <Busy text="Membuka memori lokal…" />}
        {data && tab === "profile" && (
          <ProfileForm
            key={data.catalog.revision}
            profile={data.catalog.profile}
            busy={busy}
            onDirty={setDirty}
            onSave={(profile) => mutate("/profile", "PUT", { profile })}
          />
        )}
        {data && tab === "search" && (
          <ContextSearch key={data.catalog.revision} />
        )}
        {data && tab === "references" && (
          <>
            <div className="section-head">
              <h2>Referensi yang dipilih</h2>
              <div className="spacer" />
              <button
                className="primary"
                onClick={() => setAdding(true)}
                disabled={busy || dirty}
              >
                <Plus size={15} />
                Pilih proyek
              </button>
            </div>
            {references.length === 0 ? (
              <section className="memory-empty">
                <BookOpen size={32} />
                <h2>Memori masih kosong</h2>
                <p>
                  Mulai dari beberapa proyek yang mewakili channel Anda. Tidak
                  ada proyek yang ditambahkan otomatis.
                </p>
                <button onClick={() => setAdding(true)}>
                  Pilih referensi pertama
                </button>
              </section>
            ) : (
              <div className="memory-columns">
                <aside className="memory-list" aria-label="Daftar referensi">
                  {references.map((ref) => (
                    <button
                      key={ref.project_id}
                      className={
                        current?.project_id === ref.project_id ? "selected" : ""
                      }
                      disabled={busy || dirty}
                      onClick={() => setSelected(ref.project_id)}
                    >
                      <strong>{ref.observed.name}</strong>
                      <span>
                        {ref.observed.language.toUpperCase()} ·{" "}
                        {memoryStatus(ref)}
                      </span>
                      <Status kind={isActiveReference(ref) ? "ready" : "warn"}>
                        {ref.missing
                          ? "Sumber tidak tersedia"
                          : ref.category === "qa"
                            ? "QA / uji"
                            : ref.category === "duplicate"
                              ? "Duplikat"
                              : ref.included
                                ? "Disertakan"
                                : "Dikecualikan"}
                      </Status>
                    </button>
                  ))}
                </aside>
                {current && (
                  <ReferenceForm
                    key={current.project_id + ":" + data.catalog.revision}
                    reference={current}
                    busy={busy}
                    onDirty={setDirty}
                    similar={
                      references.find(
                        (ref) =>
                          ref.project_id !== current.project_id &&
                          !!current.observed.fingerprint &&
                          ref.observed.fingerprint ===
                            current.observed.fingerprint,
                      )?.observed.name
                    }
                    onSave={(values) =>
                      mutate("/references/" + current.project_id, "PUT", values)
                    }
                    onForget={() => setForget(current)}
                    onFeedback={(values) =>
                      mutate(
                        "/references/" + current.project_id + "/feedback",
                        "POST",
                        values,
                      )
                    }
                    onRemoveFeedback={(id) =>
                      mutate(
                        "/references/" +
                          current.project_id +
                          "/feedback/" +
                          id +
                          "/forget",
                        "POST",
                        {},
                      )
                    }
                  />
                )}
              </div>
            )}
          </>
        )}
      </main>
      {adding && data && (
        <ChooseReferences
          projects={data.projects.filter(
            (p) => !references.some((ref) => ref.project_id === p.id),
          )}
          busy={busy}
          error={error}
          onClose={() => setAdding(false)}
          onAdd={async (ids) => {
            if (await mutate("/references", "POST", { project_ids: ids })) {
              setSelected(ids[0]);
              setAdding(false);
            }
          }}
        />
      )}
      {forget && (
        <Modal
          title="Hapus referensi dari memori?"
          onClose={() => {
            if (!busy) setForget(null);
          }}
        >
          <div className="modal-body">
            <p>
              <strong>{forget.observed.name}</strong> akan dikeluarkan dari
              memori bersama label dan catatan idenya.
            </p>
            <p>
              Proyek dan media tetap tersimpan. Anda bisa memilih proyek ini
              lagi sebagai referensi baru.
            </p>
            {error && (
              <p role="alert" className="error-banner">
                {error}
              </p>
            )}
          </div>
          <div className="modal-footer">
            <button disabled={busy} onClick={() => setForget(null)}>
              Batal
            </button>
            <button
              className="primary"
              disabled={busy}
              onClick={async () => {
                if (
                  await mutate(
                    "/references/" + forget.project_id + "/forget",
                    "POST",
                    {},
                  )
                ) {
                  setSelected("");
                  setForget(null);
                }
              }}
            >
              Hapus referensi
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function ChooseReferences({
  projects,
  busy,
  error,
  onClose,
  onAdd,
}: {
  projects: MemoryView["projects"];
  busy: boolean;
  error: string;
  onClose: () => void;
  onAdd: (ids: string[]) => Promise<void>;
}) {
  const [chosen, setChosen] = useState<string[]>([]),
    [search, setSearch] = useState("");
  return (
    <Modal
      title="Pilih proyek untuk memori"
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <div className="modal-body">
        <p>
          Pilih maksimal 30 proyek sekaligus. Nama QA/uji dan isi serupa akan
          dipisahkan terlebih dahulu; kategorinya bisa Anda koreksi.
        </p>
        {error && (
          <p role="alert" className="error-banner">
            {error}
          </p>
        )}
        <input
          aria-label="Cari proyek untuk memori"
          placeholder="Cari proyek…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="memory-choices">
          {projects
            .filter((p) => p.name.toLowerCase().includes(search.toLowerCase()))
            .map((p) => (
              <label key={p.id}>
                <input
                  type="checkbox"
                  checked={chosen.includes(p.id)}
                  disabled={
                    busy || (chosen.length >= 30 && !chosen.includes(p.id))
                  }
                  onChange={(e) =>
                    setChosen(
                      e.target.checked
                        ? [...chosen, p.id]
                        : chosen.filter((id) => id !== p.id),
                    )
                  }
                />
                <span>
                  <strong>{p.name}</strong>
                  <small>
                    {p.language.toUpperCase()}
                    {p.qa_hint ? " · kemungkinan proyek uji" : ""}
                  </small>
                </span>
              </label>
            ))}
          {!projects.length && (
            <p className="subtle">Belum ada proyek lain yang bisa dipilih.</p>
          )}
        </div>
      </div>
      <div className="modal-footer">
        <span className="subtle">{chosen.length} dipilih</span>
        <button disabled={busy} onClick={onClose}>
          Batal
        </button>
        <button
          className="primary"
          disabled={busy || !chosen.length}
          onClick={() => void onAdd(chosen)}
        >
          Tambahkan ke memori
        </button>
      </div>
    </Modal>
  );
}

function ProfileForm({
  profile,
  busy,
  onSave,
  onDirty,
}: {
  profile: ChannelProfile;
  busy: boolean;
  onSave: (value: ChannelProfile) => Promise<boolean>;
  onDirty: (value: boolean) => void;
}) {
  const [value, setValue] = useState(profile),
    [themes, setThemes] = useState(profile.themes.join(", "));
  const dirty =
    JSON.stringify(value) !== JSON.stringify(profile) ||
    themes !== profile.themes.join(", ");
  useEffect(() => {
    onDirty(dirty);
    return () => onDirty(false);
  }, [dirty, onDirty]);
  return (
    <form
      className="memory-card memory-profile"
      onSubmit={(event) => {
        event.preventDefault();
        void onSave({ ...value, themes: parseThemes(themes) });
      }}
    >
      <h2>Profil channel</h2>
      <p className="subtle">
        Diisi dan dikonfirmasi oleh Anda. Tidak mengambil data atau analytics
        dari akun YouTube.
      </p>
      <fieldset disabled={busy}>
        <Field label="Nama channel">
          <input
            maxLength={120}
            value={value.name}
            onChange={(e) => setValue({ ...value, name: e.target.value })}
          />
        </Field>
        <Field label="Fokus channel">
          <textarea
            rows={3}
            maxLength={500}
            value={value.description}
            onChange={(e) =>
              setValue({ ...value, description: e.target.value })
            }
          />
        </Field>
        <Field label="Audiens channel">
          <input
            maxLength={160}
            value={value.audience}
            onChange={(e) => setValue({ ...value, audience: e.target.value })}
          />
        </Field>
        <Field label="Bahasa channel">
          <select
            value={value.language}
            onChange={(e) =>
              setValue({
                ...value,
                language: e.target.value as ChannelProfile["language"],
              })
            }
          >
            <option value="en">English</option>
            <option value="id">Indonesia</option>
            <option value="mixed">Campuran</option>
          </select>
        </Field>
        <Field label="Tema channel — pisahkan dengan koma">
          <input
            value={themes}
            maxLength={970}
            onChange={(e) => setThemes(e.target.value)}
            placeholder="SwiftUI, produktivitas developer"
          />
        </Field>
        <button className="primary" type="submit">
          Simpan profil
        </button>
        {dirty && (
          <button
            type="button"
            onClick={() => {
              setValue(profile);
              setThemes(profile.themes.join(", "));
            }}
          >
            Batalkan perubahan
          </button>
        )}
      </fieldset>
    </form>
  );
}

function ReferenceForm({
  reference,
  similar,
  busy,
  onSave,
  onForget,
  onFeedback,
  onRemoveFeedback,
  onDirty,
}: {
  reference: MemoryReference;
  similar?: string;
  busy: boolean;
  onSave: (values: ReferenceUpdate) => Promise<boolean>;
  onForget: () => void;
  onFeedback: (
    values: Pick<IdeaFeedback, "idea" | "verdict" | "reason">,
  ) => Promise<boolean>;
  onRemoveFeedback: (id: string) => Promise<boolean>;
  onDirty: (value: boolean) => void;
}) {
  const [labels, setLabels] = useState(reference.confirmed),
    [themes, setThemes] = useState(reference.confirmed.themes.join(", "));
  const [included, setIncluded] = useState(reference.included),
    [category, setCategory] = useState(reference.category),
    [published, setPublished] = useState(reference.published);
  const observed = reference.observed;
  const [feedbackDirty, setFeedbackDirty] = useState(false);
  const labelDirty =
    JSON.stringify(labels) !== JSON.stringify(reference.confirmed) ||
    themes !== reference.confirmed.themes.join(", ") ||
    included !== reference.included ||
    category !== reference.category ||
    published !== reference.published;
  const dirty = labelDirty || feedbackDirty;
  useEffect(() => {
    onDirty(dirty);
    return () => onDirty(false);
  }, [dirty, onDirty]);
  return (
    <section className="memory-card">
      <div className="section-head">
        <h2>{observed.name}</h2>
        <div className="spacer" />
        <button disabled={busy || dirty} onClick={onForget}>
          Hapus referensi…
        </button>
      </div>
      {reference.missing && (
        <p className="error-banner">
          Sumber tidak tersedia. Referensi ini tidak dipakai dalam konteks;
          proyek mungkin telah dipindahkan atau rusak.
        </p>
      )}
      {similar && (
        <p className="memory-policy">
          Isi serupa dengan “{similar}”. Pencarian konteks hanya mengambil satu
          dari isi yang sama.
        </p>
      )}
      <div className="memory-facts">
        <strong>Dari proyek lokal</strong>
        <span>
          {observed.language.toUpperCase()} ·{" "}
          {(observed.duration_frames / 30).toFixed(1)} detik timeline · target{" "}
          {observed.target_seconds} detik · {observed.asset_ids.length} media
        </span>
        <span>
          Revisi sumber {observed.source_revision} ·{" "}
          {observed.exported_revision === null
            ? "Belum ada catatan ekspor lokal"
            : `Pernah diekspor pada revisi ${observed.exported_revision}${observed.exported_revision !== observed.source_revision ? " (versi sebelumnya)" : ""}`}
        </span>
        <details>
          <summary>Cuplikan naskah & ID media</summary>
          <p>{observed.excerpt || "Belum ada naskah."}</p>
          <p className="mono small">
            {observed.asset_ids.join(", ") || "Belum ada media."}
          </p>
        </details>
      </div>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void onSave({
            source_revision: observed.source_revision,
            included,
            category,
            published,
            confirmed: { ...labels, themes: parseThemes(themes) },
          });
        }}
      >
        <fieldset disabled={busy || feedbackDirty}>
          <h3>Konfirmasi Anda</h3>
          <div className="memory-form-grid">
            <Field label="Kategori referensi">
              <select
                value={category}
                onChange={(e) => {
                  const next = e.target.value as MemoryReference["category"];
                  setCategory(next);
                  if (next !== "content") setIncluded(false);
                }}
              >
                <option value="content">Konten channel</option>
                <option value="qa">QA / proyek uji</option>
                <option value="duplicate">Duplikat</option>
              </select>
            </Field>
            <Field label="Format konten">
              <input
                value={labels.format}
                maxLength={80}
                onChange={(e) =>
                  setLabels({ ...labels, format: e.target.value })
                }
                placeholder="Tutorial, demo, cerita…"
              />
            </Field>
          </div>
          <label className="check-field">
            <input
              type="checkbox"
              checked={included}
              disabled={category !== "content"}
              onChange={(e) => setIncluded(e.target.checked)}
            />
            Sertakan dalam konteks ide
          </label>
          <label className="check-field">
            <input
              type="checkbox"
              checked={published}
              onChange={(e) => setPublished(e.target.checked)}
            />
            Sudah saya publikasikan
          </label>
          <Field label="Tema — pisahkan dengan koma">
            <input
              value={themes}
              maxLength={970}
              onChange={(e) => setThemes(e.target.value)}
            />
          </Field>
          <div className="memory-form-grid">
            <Field label="Audiens">
              <input
                value={labels.audience}
                maxLength={160}
                onChange={(e) =>
                  setLabels({ ...labels, audience: e.target.value })
                }
              />
            </Field>
            <Field label="Seri">
              <input
                value={labels.series}
                maxLength={120}
                onChange={(e) =>
                  setLabels({ ...labels, series: e.target.value })
                }
              />
            </Field>
          </div>
          <Field label="Ringkasan Anda">
            <textarea
              rows={3}
              value={labels.summary}
              maxLength={700}
              onChange={(e) =>
                setLabels({ ...labels, summary: e.target.value })
              }
              placeholder="Jika kosong, konteks memakai cuplikan naskah dengan label sumber yang jelas."
            />
          </Field>
          <Field label="Hook pilihan Anda">
            <textarea
              rows={2}
              value={labels.hook}
              maxLength={240}
              onChange={(e) => setLabels({ ...labels, hook: e.target.value })}
              placeholder={observed.hook_excerpt || "Kalimat pembuka…"}
            />
          </Field>
          <button className="primary" type="submit">
            Simpan referensi
          </button>
          {labelDirty && (
            <button
              type="button"
              onClick={() => {
                setLabels(reference.confirmed);
                setThemes(reference.confirmed.themes.join(", "));
                setIncluded(reference.included);
                setCategory(reference.category);
                setPublished(reference.published);
              }}
            >
              Batalkan perubahan
            </button>
          )}
        </fieldset>
      </form>
      <p className="hint">
        {reference.suggested
          ? "Ada dugaan AI yang belum dikonfirmasi; pencarian tidak memakainya."
          : "Belum ada dugaan AI. Label di atas merupakan konfirmasi Anda; cuplikan berasal dari proyek."}
      </p>
      <FeedbackForm
        items={reference.feedback}
        busy={busy || labelDirty}
        onAdd={onFeedback}
        onRemove={onRemoveFeedback}
        onDirty={setFeedbackDirty}
      />
    </section>
  );
}

function FeedbackForm({
  items,
  busy,
  onAdd,
  onRemove,
  onDirty,
}: {
  items: IdeaFeedback[];
  busy: boolean;
  onAdd: (
    value: Pick<IdeaFeedback, "idea" | "verdict" | "reason">,
  ) => Promise<boolean>;
  onRemove: (id: string) => Promise<boolean>;
  onDirty: (value: boolean) => void;
}) {
  const [idea, setIdea] = useState(""),
    [verdict, setVerdict] = useState<IdeaFeedback["verdict"]>("saved"),
    [reason, setReason] = useState("");
  const dirty = !!idea || !!reason || verdict !== "saved";
  useEffect(() => {
    onDirty(dirty);
    return () => onDirty(false);
  }, [dirty, onDirty]);
  return (
    <section className="memory-feedback">
      <h3>Catatan ide</h3>
      <p className="subtle">
        Catat ide yang Anda simpan, lewati, atau pakai dari referensi ini. Ini
        bukan ukuran performa video.
      </p>
      {items.map((item) => (
        <article key={item.id}>
          <div>
            <strong>{item.idea}</strong>
            <p>
              {verdictLabels[item.verdict]}
              {item.reason && " · " + item.reason}
            </p>
          </div>
          <button
            disabled={busy || dirty}
            onClick={() => void onRemove(item.id)}
            aria-label={"Hapus catatan " + item.idea}
          >
            Hapus
          </button>
        </article>
      ))}
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          if (await onAdd({ idea, verdict, reason })) {
            setIdea("");
            setReason("");
          }
        }}
      >
        <fieldset disabled={busy}>
          <Field label="Ide terkait referensi">
            <input
              maxLength={400}
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
            />
          </Field>
          <div className="memory-form-grid">
            <Field label="Pilihan Anda">
              <select
                value={verdict}
                onChange={(e) =>
                  setVerdict(e.target.value as IdeaFeedback["verdict"])
                }
              >
                <option value="saved">Disimpan</option>
                <option value="skipped">Dilewati</option>
                <option value="used">Dipakai</option>
              </select>
            </Field>
            <Field label="Alasan (opsional)">
              <input
                maxLength={300}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </Field>
          </div>
          <button type="submit" disabled={!idea.trim() || items.length >= 20}>
            Simpan catatan ide
          </button>
          {dirty && (
            <button
              type="button"
              onClick={() => {
                setIdea("");
                setReason("");
                setVerdict("saved");
              }}
            >
              Batalkan catatan
            </button>
          )}
        </fieldset>
      </form>
    </section>
  );
}

function ContextSearch() {
  const [query, setQuery] = useState(""),
    [theme, setTheme] = useState(""),
    [series, setSeries] = useState("");
  const [language, setLanguage] = useState(""),
    [recent, setRecent] = useState("");
  const [context, setContext] = useState<MemoryContext | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <section className="memory-card">
      <h2>Cari konteks dari memori</h2>
      <p className="subtle">
        Lihat maksimal lima ringkasan yang relevan dan beragam. Pencarian ini
        berlangsung lokal; belum menjalankan AI atau membuat ide harian.
      </p>
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          setError("");
          setContext(null);
          try {
            setContext(
              await request<MemoryContext>("/memory/retrieve", "POST", {
                query,
                theme,
                series,
                language: language || null,
                recent_days: recent ? Number(recent) : null,
              }),
            );
          } catch (error) {
            setError((error as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <fieldset disabled={busy}>
          <Field label="Kata kunci">
            <input
              value={query}
              maxLength={200}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Contoh: State, animasi, tips developer"
            />
          </Field>
          <div className="memory-form-grid">
            <Field label="Utamakan tema">
              <input
                value={theme}
                maxLength={80}
                onChange={(e) => setTheme(e.target.value)}
              />
            </Field>
            <Field label="Utamakan seri">
              <input
                value={series}
                maxLength={120}
                onChange={(e) => setSeries(e.target.value)}
              />
            </Field>
            <Field label="Bahasa konteks">
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              >
                <option value="">Semua bahasa</option>
                <option value="en">English</option>
                <option value="id">Indonesia</option>
              </select>
            </Field>
            <Field label="Rentang riwayat">
              <select
                value={recent}
                onChange={(e) => setRecent(e.target.value)}
              >
                <option value="">Semua waktu</option>
                <option value="30">30 hari terakhir</option>
                <option value="90">90 hari terakhir</option>
                <option value="365">Setahun terakhir</option>
              </select>
            </Field>
          </div>
          <button className="primary" type="submit">
            <Search size={15} />
            {busy ? "Mencari…" : "Cari ringkasan"}
          </button>
        </fieldset>
      </form>
      {error && (
        <p role="alert" className="error-banner">
          {error}
        </p>
      )}
      {context && (
        <div className="memory-results">
          <p role="status">
            {context.references.length} referensi · konteks dibatasi 6.000
            karakter.
          </p>
          {!context.references.length && (
            <p>
              Belum ada referensi yang cocok dan aktif. Periksa pilihan proyek,
              bahasa, kategori, atau rentang riwayat.
            </p>
          )}
          {context.references.map((ref) => (
            <article key={ref.project_id}>
              <div className="section-head">
                <h3>{ref.name}</h3>
                <Status>{ref.language.toUpperCase()}</Status>
              </div>
              <p>{ref.summary || "Belum ada ringkasan."}</p>
              <p className="hint">
                {ref.summary_origin === "user"
                  ? "Ringkasan Anda"
                  : "Cuplikan naskah, bukan ringkasan AI"}{" "}
                · revisi sumber {ref.source_revision}
              </p>
              <p className="subtle">
                {[...ref.themes, ref.series].filter(Boolean).join(" · ") ||
                  "Belum diberi label"}
              </p>
              {ref.feedback.map((item) => (
                <p key={item.id} className="hint">
                  {verdictLabels[item.verdict]}: {item.idea}
                  {item.reason && " — " + item.reason}
                </p>
              ))}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
