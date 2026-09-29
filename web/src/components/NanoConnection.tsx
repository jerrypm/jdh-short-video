import { useEffect, useState } from "react";
import { nanoProvider, type AIStatus } from "@/lib/ai";
import { request } from "@/lib/api";
import { Status } from "./UI";

export default function NanoConnection() {
  const [state, setState] = useState<AIStatus | null>(null);
  const [url, setURL] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const update = async () => {
      try {
        const result = await nanoProvider.status();
        if (!disposed) setState(result);
      } catch {
        if (!disposed) setState(null);
      }
      if (!disposed) timer = setTimeout(update, 2500);
    };
    void update();
    return () => { disposed = true; clearTimeout(timer); };
  }, []);
  const pair = async () => {
    setWorking(true); setError(""); setCopied(false);
    try {
      const result = await request<{ code: string }>("/ai/pair", "POST", {});
      setURL(location.origin + "/nano/#pair=" + encodeURIComponent(result.code));
    } catch (error) { setError((error as Error).message); }
    finally { setWorking(false); }
  };
  const disconnect = async () => {
    setWorking(true); setError("");
    try {
      setState(await request<AIStatus>("/ai/disconnect", "POST", {}));
      setURL("");
    } catch (error) { setError((error as Error).message); }
    finally { setWorking(false); }
  };
  const copy = async () => {
    try { await navigator.clipboard.writeText(url); setCopied(true); }
    catch { setError("Pilih tautan di bawah lalu tekan ⌘C untuk menyalinnya."); }
  };
  return <section className="nano-connection">
    <div className="section-head">
      <h2>Gemini Nano lokal</h2>
      <Status kind={state?.availability === "available" ? "ready" : "warn"}>
        {state?.busy ? "Memproses…" : state?.availability === "available" ? "Siap" : state?.connected ? "Perlu model" : "Belum terhubung"}
      </Status>
    </div>
    <p className="subtle">Hubungkan aplikasi dengan tab companion di Chrome personal Anda.
      Biarkan tab tetap terbuka selama memakai AI. Bantuan naskah tersedia untuk English.</p>
    <p>{state?.message || "Buat tautan untuk menghubungkan Chrome."}</p>
    {state?.availability === "downloading" && <p>Mengunduh model {Math.round(state.download_progress * 100)}%</p>}
    <div className="button-wrap">
      <button className="primary" disabled={working} onClick={pair}>Buat tautan companion</button>
      <button disabled={working || !state?.connected} onClick={disconnect}>Putuskan koneksi</button>
    </div>
    {url && <div className="nano-pair-link">
      <label htmlFor="nano-url">Salin tautan ini, lalu buka di Chrome</label>
      <div className="button-wrap">
        <input id="nano-url" readOnly value={url} onFocus={(event) => event.target.select()} />
        <button onClick={copy}>{copied ? "Tersalin" : "Salin tautan"}</button>
      </div>
      <p className="hint">Berlaku sekali selama 3 menit. Jika diminta, pilih “Siapkan model lokal” di Chrome.
        Setelah aplikasi dimulai ulang, buat tautan baru.</p>
    </div>}
    {error && <p role="alert" className="error-banner">{error}</p>}
    <p className="hint">Naskah diproses oleh model di perangkat ini. Tidak ada API key atau AI cloud.</p>
  </section>;
}
