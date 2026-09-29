import { useEffect, useState } from "react";
import { ArrowLeft, BookOpen, Plus, RefreshCw } from "lucide-react";
import { Brand, Field, Modal } from "./UI";
import { request } from "@/lib/api";
import {
  emptySource,
  researchRequest,
  sourceOnly,
  sourceStatus,
  type SourceInput,
  type ResearchSource,
  type ResearchView,
} from "@/lib/research";

type PageDraft = {
  title: string;
  url: string;
  published_on: string;
  accessed_on: string;
  text: string;
  notice: string;
};
export default function Research({ onBack }: { onBack: () => void }) {
  const [data, setData] = useState<ResearchView | null>(null);
  const [form, setForm] = useState<SourceInput>(emptySource);
  const [editing, setEditing] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pageDraft, setPageDraft] = useState<PageDraft | null>(null);
  const [removing, setRemoving] = useState<ResearchSource | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void request<ResearchView>("/research", "GET", undefined, controller.signal)
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
  function edit(patch: Partial<SourceInput>) {
    setForm((old) => ({ ...old, ...patch }));
    setReviewed(false);
  }
  function reset() {
    setEditing("");
    setForm(emptySource());
    setReviewed(false);
    setPageDraft(null);
  }
  const names = Object.fromEntries(
    data?.sources.map((s) => [s.id, s.title]) || [],
  );
  return (
    <div className="memory-page research-page">
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
            <div className="eyebrow">REFERENSI RISET · NANO LOKAL</div>
            <h1>
              <BookOpen size={24} />
              Sumber riset
            </h1>
            <p className="subtle">
              Catat bukti sebelum menjadikannya ide video.
            </p>
          </div>
          <button
            disabled={busy}
            onClick={() =>
              void work(async () => {
                setData(await researchRequest<ResearchView>());
                setNotice(
                  "Pustaka dimuat ulang; periksa lagi sebelum menyimpan formulir.",
                );
                setReviewed(false);
              })
            }
          >
            <RefreshCw size={16} />
            Muat ulang
          </button>
        </div>
        <p className="hint">
          Pilih “Referensi riset” pada preferensi Ide hari ini untuk mode ini.
          Catatan tersimpan bisa dibaca offline; pengambilan URL hanya berjalan
          saat Anda memintanya. Satu artikel bukan bukti tren.
        </p>
        {error && (
          <p className="error-banner" role="alert">
            {error}
          </p>
        )}
        {notice && (
          <p className="success-banner" role="status">
            {notice}
          </p>
        )}
        <section className="memory-card">
          <div className="section-head">
            <h2>{editing ? "Tinjau dan perbarui sumber" : "Tambah sumber"}</h2>
            {editing && (
              <button disabled={busy} onClick={reset}>
                <Plus size={15} />
                Catatan baru
              </button>
            )}
          </div>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (!data || !reviewed) return;
              void work(async () => {
                setData(
                  await researchRequest<ResearchView>("/sources", "POST", {
                    revision: data.revision,
                    id: editing,
                    source: form,
                    reviewed: true,
                  }),
                );
                reset();
                setNotice(
                  "Sumber tersimpan setelah ditinjau. Ide riset lama perlu dibuat ulang jika data berubah.",
                );
              });
            }}
          >
            <fieldset disabled={busy || !data}>
              <Field label="URL publik HTTPS (opsional untuk catatan manual)">
                <input
                  type="url"
                  maxLength={2000}
                  placeholder="https://…"
                  value={form.url}
                  onChange={(e) => edit({ url: e.target.value })}
                />
              </Field>
              <button
                type="button"
                disabled={busy || !form.url.trim()}
                onClick={() =>
                  void work(async () => {
                    setPageDraft(null);
                    setPageDraft(
                      await researchRequest<PageDraft>("/fetch", "POST", {
                        url: form.url,
                      }),
                    );
                  })
                }
              >
                Ambil cuplikan URL
              </button>
              <p className="hint">
                Tombol ini menghubungi situs tersebut tanpa cookie, login, atau
                tab browser. Maksimal 256 KB / 10 detik; alamat privat, file,
                media dan halaman login tidak diterobos. Formulir tetap utuh
                jika gagal.
              </p>
              <div className="performance-form research-form">
                <Field label="Judul sumber">
                  <input
                    required
                    maxLength={160}
                    value={form.title}
                    onChange={(e) => edit({ title: e.target.value })}
                  />
                </Field>
                <Field label="Tanggal publikasi (kosong jika tidak diketahui)">
                  <input
                    type="date"
                    value={form.published_on}
                    onChange={(e) => edit({ published_on: e.target.value })}
                  />
                </Field>
                <Field label="Tanggal akses / peninjauan">
                  <input
                    type="date"
                    required
                    value={form.accessed_on}
                    onChange={(e) => edit({ accessed_on: e.target.value })}
                  />
                </Field>
                <Field label="Jenis catatan">
                  <select
                    value={form.kind}
                    onChange={(e) =>
                      edit({ kind: e.target.value as SourceInput["kind"] })
                    }
                  >
                    <option value="summary">Ringkasan pengguna</option>
                    <option value="excerpt">Cuplikan sumber</option>
                  </select>
                </Field>
                <Field label="Bertentangan dengan sumber">
                  <select
                    value={form.conflict_with}
                    onChange={(e) => edit({ conflict_with: e.target.value })}
                  >
                    <option value="">Tidak ada konflik yang dicatat</option>
                    {data?.sources
                      .filter((s) => s.id !== editing)
                      .map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.title}
                        </option>
                      ))}
                  </select>
                </Field>
              </div>
              <Field label="Ringkasan / cuplikan yang sudah Anda periksa (20–1.200 karakter)">
                <textarea
                  required
                  minLength={20}
                  maxLength={1200}
                  rows={6}
                  value={form.text}
                  onChange={(e) => edit({ text: e.target.value })}
                />
              </Field>
              <Field label="Batasan atau penjelasan konflik">
                <textarea
                  maxLength={240}
                  required={!!form.conflict_with}
                  rows={2}
                  placeholder="Contoh: versi produk berbeda; belum ada konfirmasi dari sumber utama."
                  value={form.caution}
                  onChange={(e) => edit({ caution: e.target.value })}
                />
              </Field>
              <label className="check-field">
                <input
                  type="checkbox"
                  checked={form.included}
                  onChange={(e) => edit({ included: e.target.checked })}
                />
                Sertakan sebagai konteks ide riset jika masih layak.
              </label>
              <p className="hint">
                Sumber dengan tanggal akses atau publikasi lebih dari 30 hari
                tetap tersimpan tetapi tidak dipakai untuk ide terkini. Konflik
                mengecualikan kedua sumber sampai ditinjau; isi yang sama tidak
                dihitung sebagai sumber tambahan.
              </p>
              <label className="check-field">
                <input
                  type="checkbox"
                  checked={reviewed}
                  onChange={(e) => setReviewed(e.target.checked)}
                />
                Saya sudah memeriksa judul, tanggal, isi, serta batasan sumber
                ini.
              </label>
              <button className="primary" disabled={busy || !data || !reviewed}>
                {busy
                  ? "Memproses…"
                  : editing
                    ? "Simpan perubahan sumber"
                    : "Simpan sumber"}
              </button>
            </fieldset>
          </form>
        </section>
        <section className="memory-card performance-section">
          <h2>Pustaka sumber · {data?.sources.length || 0}</h2>
          <p className="hint">
            {data?.eligible_count || 0} sumber layak · maksimal 3 catatan
            terbaru, masing-masing 700 karakter awal per permintaan ide.
            Inferensi tetap dilakukan oleh Gemini Nano lokal; pengambilan
            halaman bukan verifikasi fakta otomatis.
          </p>
          {!data?.sources.length ? (
            <p>
              Belum ada sumber. Catatan manual dapat ditambahkan tanpa koneksi
              internet.
            </p>
          ) : (
            <div className="research-library">
              {[...data.sources].reverse().map((source) => (
                <article key={source.id}>
                  <div className="eyebrow">{sourceStatus[source.status]}</div>
                  <h3>{source.title}</h3>
                  {source.url ? (
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noreferrer noopener"
                    >
                      {source.url}
                    </a>
                  ) : (
                    <p className="hint">Catatan manual · tanpa URL</p>
                  )}
                  <p className="hint">
                    Publikasi:{" "}
                    {source.published_on ||
                      "tidak diketahui; keterkinian belum terverifikasi"}{" "}
                    · akses {source.accessed_on}
                  </p>
                  <p className="research-source-text">{source.text}</p>
                  {source.caution && (
                    <p className="hint">Batasan: {source.caution}</p>
                  )}
                  {source.conflict_with && (
                    <p className="hint">
                      Konflik dengan: {names[source.conflict_with]}
                    </p>
                  )}
                  {source.duplicate_of && (
                    <p className="hint">
                      Isi sama dengan: {names[source.duplicate_of]}
                    </p>
                  )}
                  <div className="ideas-actions">
                    <button
                      disabled={busy}
                      onClick={() => {
                        setEditing(source.id);
                        setForm(sourceOnly(source));
                        setReviewed(false);
                        document
                          .querySelector(".research-page")
                          ?.scrollTo({ top: 0, behavior: "smooth" });
                      }}
                    >
                      Edit sumber
                    </button>
                    <button disabled={busy} onClick={() => setRemoving(source)}>
                      Hapus sumber
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
      {pageDraft && (
        <Modal
          title="Cuplikan halaman · belum disimpan"
          wide
          onClose={() => setPageDraft(null)}
        >
          <div className="performance-exclusion">
            <p className="hint">{pageDraft.notice}</p>
            <h3>{pageDraft.title || "Judul belum terbaca"}</h3>
            <p className="hint">
              {pageDraft.url}
              <br />
              Publikasi dari metadata:{" "}
              {pageDraft.published_on || "tidak tersedia"} · akses{" "}
              {pageDraft.accessed_on}
            </p>
            <p className="research-source-text">{pageDraft.text}</p>
            <button
              className="primary"
              onClick={() => {
                edit({
                  url: pageDraft.url,
                  title: pageDraft.title || form.title,
                  published_on: /^\d{4}-\d{2}-\d{2}$/.test(
                    pageDraft.published_on,
                  )
                    ? pageDraft.published_on
                    : "",
                  accessed_on: pageDraft.accessed_on,
                  text: pageDraft.text,
                  kind: "excerpt",
                });
                setPageDraft(null);
              }}
            >
              Pakai di formulir untuk ditinjau
            </button>
          </div>
        </Modal>
      )}
      {removing && (
        <Modal
          title="Hapus catatan sumber?"
          onClose={() => {
            if (!busy) setRemoving(null);
          }}
        >
          <div className="performance-exclusion">
            <p>{removing.title}</p>
            <p className="hint">
              Catatan ini dihapus dari pustaka lokal. Ide tersimpan tetap ada
              dengan tanda perlu diperbarui. Pasangan konflik yang tersisa harus
              ditinjau kembali.
            </p>
            {error && (
              <p className="error-banner" role="alert">
                {error}
              </p>
            )}
            <button
              disabled={busy}
              onClick={() =>
                void work(async () => {
                  setData(
                    await researchRequest<ResearchView>(
                      `/sources/${removing.id}/remove`,
                      "POST",
                      { revision: data?.revision },
                    ),
                  );
                  if (editing === removing.id) reset();
                  setRemoving(null);
                  setNotice("Sumber dihapus dari pustaka lokal.");
                })
              }
            >
              Hapus catatan ini
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
