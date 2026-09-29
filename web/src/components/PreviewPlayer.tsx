import { useEffect, useRef, useState } from "react";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  ImagePlus,
  Scan,
} from "lucide-react";
import { Project, sceneRanges, totalFrames, timecode } from "@/lib/model";
import { assetURL } from "@/lib/api";
import { usePreviewMedia } from "@/lib/usePreviewMedia";
import { defaultMotion, evaluateVisual, sourceGeometry } from "@/lib/motion";
import SceneOverlays from "./SceneOverlays";

function AudioTrack({
  url,
  time,
  playing,
  volume,
  loop = false,
  onError,
}: {
  url: string;
  time: number;
  playing: boolean;
  volume: number;
  loop?: boolean;
  onError: (message: string) => void;
}) {
  const ref = useRef<HTMLAudioElement>(null);
  usePreviewMedia(ref, url, { time, playing, volume, loop }, onError);
  return <audio ref={ref} src={url} preload="auto" />;
}
export default function PreviewPlayer({
  project,
  frame,
  setFrame,
  playing,
  setPlaying,
}: {
  project: Project;
  frame: number;
  setFrame: (n: number) => void;
  playing: boolean;
  setPlaying: (v: boolean) => void;
}) {
  const total = totalFrames(project);
  const ranges = sceneRanges(project.scenes);
  const scene =
    ranges.find((s) => frame >= s.start && frame < s.end) ?? ranges.at(-1);
  const nextScene = ranges[ranges.findIndex((s) => s.id === scene?.id) + 1];
  const asset = project.assets.find((a) => a.id === scene?.media_id);
  const [safe, setSafe] = useState(true),
    [mediaError, setMediaError] = useState("");
  const video = useRef<HTMLVideoElement>(null);
  const mediaFailed = (message: string) => {
    setMediaError(message);
    setPlaying(false);
  };
  const offset = scene ? Math.max(0, frame - scene.start) : 0;
  usePreviewMedia(
    video,
    `${scene?.id}:${asset?.id}:${scene?.source_in}`,
    {
      time: ((scene?.source_in ?? 0) + offset) / 30,
      playing,
      volume: scene?.source_volume ?? 0,
    },
    mediaFailed,
  );
  useEffect(() => {
    if (playing) setMediaError("");
  }, [playing]);
  const motionEnabled = project.motion_mode !== "none";
  const visual = evaluateVisual(
    scene?.motion?.visual ?? defaultMotion().visual,
    offset,
    scene?.duration ?? 9,
    motionEnabled,
  );
  const geometry =
    asset && scene
      ? sourceGeometry(
          asset.width,
          asset.height,
          scene.fit,
          scene.scale,
          scene.x,
          scene.y,
        )
      : undefined;
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    const start = performance.now(),
      base = frame;
    const tick = (now: number) => {
      const next = base + Math.floor(((now - start) / 1000) * 30);
      if (next >= total) {
        setFrame(Math.max(0, total - 1));
        setPlaying(false);
        return;
      }
      setFrame(next);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, total]); // clock owns frames until paused
  const music = project.assets.find((a) => a.id === project.music_id);
  return (
    <section className="preview">
      <div className="preview-head">
        <span>
          Pratinjau{" "}
          <span className="subtle">· {scene?.name ?? "Belum ada scene"}</span>
        </span>
        <div className="spacer" />
        <button
          className={safe ? "tiny active" : "tiny"}
          onClick={() => setSafe(!safe)}
        >
          <Scan size={13} />
          Area aman
        </button>
        <span className="mono small">Zoom Fit</span>
      </div>
      <div className="stage">
        <div className="portrait">
          <div className="visual-frame">
            <div
              className="visual-base"
              style={{
                transform: `translate(${(visual.x / 1080) * 100}%, ${(visual.y / 1920) * 100}%) scale(${visual.scale})`,
              }}
            >
              {asset && scene ? (
                asset.kind === "image" ? (
                  <img
                    draggable={false}
                    src={assetURL(project, asset.id)}
                    alt={asset.name}
                    style={geometry}
                  />
                ) : (
                  <video
                    ref={video}
                    src={assetURL(project, asset.id)}
                    playsInline
                    preload="auto"
                    style={geometry}
                  />
                )
              ) : (
                <div className="missing-preview">
                  <ImagePlus size={28} />
                  <strong>Media belum dipilih</strong>
                  <p>
                    Pilih media untuk scene ini
                    <br />
                    dari panel Media.
                  </p>
                </div>
              )}
            </div>
          </div>
          {asset && <span className="filename mono">{asset.name}</span>}
          {safe && (
            <>
              <div className="safe-area" />
              <span className="safe-label">AREA AMAN</span>
            </>
          )}
          {[scene, nextScene].map(
            (item) =>
              item && (
                <SceneOverlays
                  key={item.id}
                  scene={item}
                  style={project.caption_style}
                  frame={item.id === scene?.id ? offset : 0}
                  active={item.id === scene?.id}
                  enabled={motionEnabled}
                />
              ),
          )}
        </div>
      </div>
      {mediaError && (
        <p className="caption-error" role="alert">
          {mediaError}
        </p>
      )}
      <div className="transport">
        <button
          className="icon"
          aria-label="Mundur 1 detik"
          onClick={() => {
            setPlaying(false);
            setFrame(Math.max(0, frame - 30));
          }}
        >
          <SkipBack size={15} />
        </button>
        <button
          className="primary icon play"
          aria-label={playing ? "Jeda" : "Putar"}
          disabled={!total}
          onClick={() => {
            if (frame >= total - 1) setFrame(0);
            setPlaying(!playing);
          }}
        >
          {playing ? (
            <Pause size={18} />
          ) : (
            <Play size={18} fill="currentColor" />
          )}
        </button>
        <button
          className="icon"
          aria-label="Maju 1 detik"
          onClick={() => {
            setPlaying(false);
            setFrame(Math.min(total - 1, frame + 30));
          }}
        >
          <SkipForward size={15} />
        </button>
        <strong className="mono">{timecode(frame)}</strong>
        <span className="mono subtle small">/ {timecode(total)}</span>
        <div className="spacer" />
        <span className="hint">Space untuk putar / jeda</span>
      </div>
      {/* Keep the next narration mounted so WebKit can buffer it before the
          scene boundary. The scene key preserves that element on transition. */}
      {[scene, nextScene].map(
        (track) =>
          track?.audio_id && (
            <AudioTrack
              key={`${track.id}:${track.audio_id}:${track.audio_in}`}
              url={assetURL(project, track.audio_id)}
              time={
                (track.audio_in + (track.id === scene?.id ? offset : 0)) / 30
              }
              playing={playing && track.id === scene?.id}
              volume={project.narration_volume}
              onError={mediaFailed}
            />
          ),
      )}
      {music && (
        <AudioTrack
          key={music.id}
          url={assetURL(project, music.id)}
          time={frame / 30}
          playing={playing}
          volume={project.music_volume}
          loop
          onError={mediaFailed}
        />
      )}
    </section>
  );
}
