import { useState } from "react";
import type { Asset, Scene } from "@/lib/model";
import { Field, Modal } from "./UI";

export default function SceneEditor({
  scene,
  assets,
  onSave,
  onClose,
}: {
  scene: Scene;
  assets: Asset[];
  onSave: (changes: Partial<Scene>) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState(scene.name);
  const [narration, setNarration] = useState(scene.narration);
  const [caption, setCaption] = useState(scene.caption);
  const [seconds, setSeconds] = useState((scene.duration / 30).toFixed(3));
  const [mediaId, setMediaId] = useState(scene.media_id ?? "");
  const duration = Math.round(Number(seconds) * 30);
  const valid =
    name.trim().length > 0 &&
    Number.isFinite(duration) &&
    duration >= 9 &&
    duration <= 1800;
  const staleVoice =
    scene.audio_id && narration !== (scene.audio_text || scene.narration);

  return (
    <Modal title={`Edit scene — ${scene.name}`} onClose={onClose}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!valid) return;
          const mediaChanged = mediaId !== (scene.media_id ?? "");
          const asset = assets.find((item) => item.id === mediaId);
          onSave({
            name: name.trim(),
            narration,
            caption,
            duration:
              mediaChanged && asset?.kind === "video"
                ? Math.max(9, Math.min(duration, asset.frames))
                : duration,
            media_id: mediaId || null,
            ...(mediaChanged ? { source_in: 0 } : {}),
          });
        }}
      >
        <div className="modal-body scene-edit-fields">
          <Field label="Nama scene">
            <input
              autoFocus
              required
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <Field label="Narasi">
            <textarea
              rows={3}
              maxLength={3000}
              value={narration}
              onChange={(e) => setNarration(e.target.value)}
            />
          </Field>
          {staleVoice && (
            <p className="hint warning" role="status">
              Naskah berubah. Buat ulang suara di panel Narasi setelah menyimpan.
            </p>
          )}
          <Field label="Teks layar / caption">
            <textarea
              rows={2}
              maxLength={400}
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
            />
          </Field>
          <Field label="Durasi scene (detik)">
            <input
              type="number"
              min={0.3}
              max={60}
              step="any"
              required
              value={seconds}
              onChange={(e) => setSeconds(e.target.value)}
            />
          </Field>
          <Field label="Media visual">
            <select value={mediaId} onChange={(e) => setMediaId(e.target.value)}>
              <option value="">Tanpa media</option>
              {assets
                .filter((asset) => asset.kind !== "audio")
                .map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.name}
                  </option>
                ))}
            </select>
          </Field>
          <p className="hint">
            Tambahkan file baru lewat panel Media. Teks yang menyatu di dalam
            gambar perlu diubah pada gambar sumber.
          </p>
        </div>
        <div className="modal-footer">
          <button type="button" onClick={onClose}>
            Batal
          </button>
          <button className="primary" type="submit" disabled={!valid}>
            Simpan perubahan
          </button>
        </div>
      </form>
    </Modal>
  );
}
