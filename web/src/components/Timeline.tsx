import { useRef, useState } from "react";
import {
  Minus,
  Plus,
  Scissors,
  Magnet,
  Trash2,
  Volume2,
  VolumeX,
} from "lucide-react";
import {
  Project,
  sceneRanges,
  totalFrames,
  shortTime,
  timecode,
} from "@/lib/model";
import { resolveTimelineSnap } from "@/vendor/opencut/resolve";
import type { SnapPoint } from "@/vendor/opencut/types";

export default function Timeline({
  project,
  selected,
  setSelected,
  frame,
  seek,
  change,
  onSplit,
  onDelete,
  tab,
  setTab,
  onDrop,
}: {
  project: Project;
  selected: string;
  setSelected: (id: string) => void;
  frame: number;
  seek: (n: number) => void;
  change: (fn: (p: Project) => Project) => void;
  onSplit: () => void;
  onDelete: () => void;
  tab: string;
  setTab: (t: string) => void;
  onDrop: (aid: string, sid: string) => void;
}) {
  const [zoom, setZoom] = useState(1),
    [snap, setSnap] = useState(true),
    [height, setHeight] = useState(248);
  const lane = useRef<HTMLDivElement>(null);
  const ranges = sceneRanges(project.scenes),
    total = Math.max(30, totalFrames(project));
  const points: SnapPoint[] = ranges.flatMap((s) => [
    { time: s.start, type: "element-start" },
    { time: s.end, type: "element-end" },
  ]);
  const seekAt = (event: React.PointerEvent) => {
    const rect = lane.current?.getBoundingClientRect();
    if (!rect) return;
    let target = Math.round(((event.clientX - rect.left) / rect.width) * total);
    if (snap)
      target = resolveTimelineSnap({
        targetTime: target,
        snapPoints: points,
        maxSnapDistance: 10,
      }).snappedTime;
    seek(Math.max(0, Math.min(total - 1, target)));
  };
  const tracks = [
    {
      key: "visual",
      name: "Visual",
      muted: project.scenes.every((s) => !s.source_volume),
      toggle: () =>
        change((p) => ({
          ...p,
          scenes: p.scenes.map((s) => ({
            ...s,
            source_volume: p.scenes.every((s) => !s.source_volume) ? 1 : 0,
          })),
        })),
    },
    {
      key: "narration",
      name: "Narasi",
      muted: !project.narration_volume,
      toggle: () =>
        change((p) => ({ ...p, narration_volume: p.narration_volume ? 0 : 1 })),
    },
    {
      key: "music",
      name: "Musik",
      muted: !project.music_volume,
      toggle: () =>
        change((p) => ({ ...p, music_volume: p.music_volume ? 0 : 0.15 })),
    },
    {
      key: "captions",
      name: "Caption",
      muted: !project.caption_style.enabled,
      toggle: () =>
        change((p) => ({
          ...p,
          caption_style: {
            ...p.caption_style,
            enabled: !p.caption_style.enabled,
          },
        })),
    },
  ];
  return (
    <section className="timeline" style={{ height }}>
      <div
        className="resize-handle"
        role="separator"
        aria-label="Tinggi timeline"
        onPointerDown={(e) => {
          const start = e.clientY,
            base = height;
          const move = (ev: PointerEvent) =>
            setHeight(Math.max(200, Math.min(400, base + start - ev.clientY)));
          const stop = () => {
            window.removeEventListener("pointermove", move);
            window.removeEventListener("pointerup", stop);
          };
          window.addEventListener("pointermove", move);
          window.addEventListener("pointerup", stop);
        }}
      />
      <div className="timeline-toolbar">
        <button
          className="tiny icon"
          aria-label="Perkecil timeline"
          onClick={() => setZoom(Math.max(1, zoom - 0.5))}
        >
          <Minus size={14} />
        </button>
        <span className="mono small">{zoom * 100}%</span>
        <button
          className="tiny icon"
          aria-label="Perbesar timeline"
          onClick={() => setZoom(Math.min(5, zoom + 0.5))}
        >
          <Plus size={14} />
        </button>
        <span className="divider" />
        <button className="tiny" onClick={onSplit}>
          <Scissors size={14} />
          Pisah
        </button>
        <button className="tiny" onClick={onDelete}>
          <Trash2 size={14} />
          Hapus
        </button>
        <button
          className={snap ? "tiny active" : "tiny"}
          onClick={() => setSnap(!snap)}
        >
          <Magnet size={14} />
          {snap ? "Snap aktif" : "Snap mati"}
        </button>
        <div className="spacer" />
        <span className="mono small">
          Playhead <b className="lime">{timecode(frame)}</b>
        </span>
      </div>
      <div className="timeline-body">
        <div className="track-labels">
          <div className="ruler-spacer" />
          {tracks.map((track) => (
            <div key={track.key} className={"track-label " + track.key}>
              <span className={"track-marker " + track.key} />
              {track.name}
              <button
                className="tiny icon"
                title={`${track.muted ? "Aktifkan" : "Bisukan"} ${track.name}`}
                aria-label={`${track.muted ? "Aktifkan" : "Bisukan"} ${track.name}`}
                onClick={track.toggle}
              >
                {track.muted ? <VolumeX size={12} /> : <Volume2 size={12} />}
              </button>
            </div>
          ))}
        </div>
        <div className="timeline-scroll">
          <div
            ref={lane}
            className="timeline-lanes"
            style={{ width: `${zoom * 100}%` }}
          >
            <div
              className="ruler"
              onPointerDown={(e) => {
                e.currentTarget.setPointerCapture(e.pointerId);
                seekAt(e);
              }}
              onPointerMove={(e) => {
                if (e.buttons) seekAt(e);
              }}
            >
              {Array.from({ length: Math.floor(total / 150) + 1 }, (_, i) => (
                <span key={i} style={{ left: `${((i * 150) / total) * 100}%` }}>
                  {shortTime(i * 150)}
                </span>
              ))}
            </div>
            <div className="track visual">
              {ranges.map((s) => (
                <button
                  key={s.id}
                  className={
                    "clip visual " +
                    (selected === s.id ? "selected " : "") +
                    (!s.media_id ? "missing" : "")
                  }
                  style={{
                    left: `${(s.start / total) * 100}%`,
                    width: `${(s.duration / total) * 100}%`,
                  }}
                  onClick={() => {
                    setSelected(s.id);
                    setTab("scene");
                  }}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    onDrop(e.dataTransfer.getData("text/plain"), s.id);
                  }}
                >
                  <strong>
                    {s.name} ·{" "}
                    {project.assets.find((a) => a.id === s.media_id)?.name ??
                      "Media belum dipilih"}
                  </strong>
                  <span className="mono">
                    {(s.duration / 30).toFixed(1)} dtk
                  </span>
                </button>
              ))}
            </div>
            <div className="track narration">
              {ranges.map((s) => {
                const a = project.assets.find((a) => a.id === s.audio_id);
                const audibleFrames = a
                  ? Math.max(0, Math.min(s.duration, a.frames - s.audio_in))
                  : s.duration;
                const peaks =
                  a?.peaks.slice(
                    Math.floor(
                      (s.audio_in / Math.max(1, a.frames)) * a.peaks.length,
                    ),
                    Math.ceil(
                      ((s.audio_in + audibleFrames) / Math.max(1, a.frames)) *
                        a.peaks.length,
                    ),
                  ) ?? [];
                const peakScale = Math.max(0.001, ...peaks);
                return (
                  <button
                    key={s.id}
                    className={"clip narration " + (!a ? "empty" : "")}
                    style={{
                      left: `${(s.start / total) * 100}%`,
                      width: `${(audibleFrames / total) * 100}%`,
                    }}
                    onClick={() => {
                      setSelected(s.id);
                      setTab("narasi");
                    }}
                  >
                    <span>{a ? s.name : "Impor / buat narasi"}</span>
                    {a && (
                      <div className="waveform">
                        {peaks.map((v, i) => (
                          <i
                            key={i}
                            style={{
                              height: `${Math.max(4, (v / peakScale) * 100)}%`,
                            }}
                          />
                        ))}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
            <div className="track music">
              {project.music_id ? (
                <button
                  className="clip music"
                  style={{ left: 0, width: "100%" }}
                  onClick={() => setTab("media")}
                >
                  {project.assets.find((a) => a.id === project.music_id)?.name}
                  <div className="waveform">
                    {project.assets
                      .find((a) => a.id === project.music_id)
                      ?.peaks.map((v, i) => (
                        <i
                          key={i}
                          style={{ height: `${Math.max(4, v * 100)}%` }}
                        />
                      ))}
                  </div>
                </button>
              ) : (
                <span className="lane-hint">
                  Pilih audio di Media untuk menambahkan musik
                </span>
              )}
            </div>
            <div className="track captions">
              {ranges.map((s) => (
                <button
                  key={s.id}
                  className={"clip captions " + (!s.caption ? "empty" : "")}
                  style={{
                    left: `${(s.start / total) * 100}%`,
                    width: `${(s.duration / total) * 100}%`,
                  }}
                  onClick={() => {
                    setSelected(s.id);
                    setTab("caption");
                  }}
                >
                  {s.caption || "Tulis caption"}
                </button>
              ))}
            </div>
            <div
              className="playhead"
              style={{ left: `${(frame / total) * 100}%` }}
            >
              <i />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
