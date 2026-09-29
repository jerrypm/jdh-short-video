import { useEffect, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  HardDrive,
  Mic,
  MonitorPlay,
  RefreshCw,
} from "lucide-react";
import type { Capabilities } from "@/lib/model";
import { request } from "@/lib/api";
import { Brand, Status } from "./UI";
import NanoConnection from "./NanoConnection";
export default function Setup({ onBack }: { onBack: () => void }) {
  const [caps, setCaps] = useState<Capabilities | null>(null),
    [error, setError] = useState("");
  const check = async () => {
    try {
      setCaps(await request<Capabilities>("/capabilities"));
    } catch (e) {
      setError((e as Error).message);
    }
  };
  useEffect(() => {
    void check();
  }, []);
  return (
    <div className="setup-page">
      <header className="home-header">
        <button onClick={onBack}>
          <ArrowLeft size={15} />
          Kembali
        </button>
        <Brand />
      </header>
      <main className="setup-main">
        <h1>Setup & pengaturan lokal</h1>
        <p className="subtle">
          Periksa kesiapan perangkat sebelum membuat video.
        </p>
        <div className="section-head">
          <h2>Kesiapan komponen</h2>
          <button onClick={check}>
            <RefreshCw size={15} />
            Periksa sekarang
          </button>
        </div>
        {error && <p className="error-banner">{error}</p>}
        <NanoConnection />
        {[
          {
            icon: Mic,
            title: "Narasi lokal",
            status: !!caps?.tts.available,
            description: caps?.tts.message ?? "Memeriksa…",
            note: "Kokoro English. Untuk Indonesia, impor rekaman narasi milik Anda.",
          },
          {
            icon: MonitorPlay,
            title: "Renderer video",
            status: !!caps?.ffmpeg && !!caps?.ffprobe,
            description: "FFmpeg + ffprobe · lokal",
            note: "H.264/AAC · draft 360×640 · final 1080×1920. Hasil diperiksa sebelum unduhan tersedia.",
          },
          {
            icon: HardDrive,
            title: "Penyimpanan proyek",
            status: !!caps,
            description: caps?.storage ?? "Memeriksa…",
            note: caps
              ? `${(caps.free_bytes / 1024 ** 3).toFixed(1)} GB tersedia. Proyek, media, dan ekspor disimpan di direktori ini.`
              : "",
          },
        ].map((item) => (
          <section className="capability" key={item.title}>
            <item.icon size={23} />
            <div>
              <h3>{item.title}</h3>
              <p className="mono small">{item.description}</p>
              <p className="subtle">{item.note}</p>
            </div>
            <Status kind={item.status ? "ready" : "warn"}>
              {item.status ? (
                <>
                  <CheckCircle2 size={12} />
                  Siap
                </>
              ) : (
                "Perlu setup"
              )}
            </Status>
          </section>
        ))}
        <p className="setup-note">
          Tidak ada API key, login, telemetry, atau unggah media. Dependency dan
          model memerlukan unduhan awal. AI/TTS belum tersedia tetap
          memungkinkan editing manual.
        </p>
        <a
          href="https://developer.chrome.com/docs/ai/prompt-api"
          target="_blank"
          rel="noreferrer"
        >
          Dokumentasi resmi Chrome Prompt API ↗
        </a>
      </main>
    </div>
  );
}
