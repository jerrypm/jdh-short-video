export type PreviewMediaState = {
  time: number;
  playing: boolean;
  volume: number;
  loop?: boolean;
};

/** Owns one media element for one timeline clip. The element's media clock
 * runs freely between transport commands; React frames only update intent.
 * Repeated currentTime corrections can interrupt WebKit's audio decoder,
 * and calling play() after EOF can restart a short narration in its gap.
 */
export class PreviewMediaController {
  private state?: PreviewMediaState;
  private needsSeek = true;
  private started = false;
  private completed = false;
  private disposed = false;
  private generation = 0;

  constructor(
    private readonly media: HTMLMediaElement,
    private readonly onError: (message: string) => void,
  ) {
    media.addEventListener("loadedmetadata", this.ready);
    media.addEventListener("canplay", this.ready);
    media.addEventListener("ended", this.ended);
    media.addEventListener("error", this.failed);
  }

  update(next: PreviewMediaState) {
    if (this.disposed) return;
    const previous = this.state;
    if (
      !previous ||
      previous.playing !== next.playing ||
      (!next.playing && previous.time !== next.time) ||
      previous.loop !== next.loop
    ) {
      this.needsSeek = true;
      this.completed = false;
    }
    this.state = next;
    const volume = Math.max(0, Math.min(1, next.volume));
    if (this.media.volume !== volume) this.media.volume = volume;
    this.media.loop = Boolean(next.loop);
    this.reconcile();
  }

  private ready = () => this.reconcile();
  private ended = () => {
    this.completed = true;
  };
  private failed = () => {
    if (!this.disposed)
      this.onError(
        "Media preview tidak dapat diputar. Periksa file audio/video lalu coba lagi.",
      );
  };

  private reconcile() {
    if (this.disposed || !this.state) return;
    const { time, playing, loop } = this.state;
    const duration = this.media.duration;
    const knownDuration = Number.isFinite(duration) && duration > 0;
    const target = knownDuration
      ? loop
        ? Math.max(0, time) % duration
        : Math.min(duration, Math.max(0, time))
      : Math.max(0, time);

    if (!playing) {
      if (this.started) {
        this.generation++;
        this.started = false;
      }
      if (!this.media.paused) this.media.pause();
    } else if (!this.started && !loop && knownDuration && time >= duration) {
      // Starting in a scene's silence must not replay its narration. An already
      // running clip finishes on the media clock so startup latency cannot cut
      // its final syllable; the scene boundary still disposes the element.
      this.completed = true;
      if (!this.media.paused) this.media.pause();
      return;
    }

    // Wait for data before seeking/starting. Readiness callbacks use the latest
    // intent, so a pending load cannot start after Pause or a scene change.
    if (this.media.readyState < (playing ? 2 : 1)) return;
    if (playing && this.completed) return;
    if (this.needsSeek) {
      this.needsSeek = false;
      if (Math.abs(this.media.currentTime - target) > 1 / 60) {
        this.media.currentTime = target;
      }
    }
    if (playing && !this.started) {
      this.started = true;
      const generation = ++this.generation;
      void this.media.play().catch(() => {
        if (this.disposed || generation !== this.generation) return;
        this.onError(
          "Audio/video preview belum bisa diputar. Tekan Putar untuk mencoba kembali.",
        );
      });
    }
  }

  dispose() {
    this.disposed = true;
    this.generation++;
    this.media.removeEventListener("loadedmetadata", this.ready);
    this.media.removeEventListener("canplay", this.ready);
    this.media.removeEventListener("ended", this.ended);
    this.media.removeEventListener("error", this.failed);
    this.media.pause();
  }
}
