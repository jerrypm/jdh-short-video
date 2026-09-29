import { useEffect, useRef, type RefObject } from "react";
import {
  PreviewMediaController,
  type PreviewMediaState,
} from "./preview-media";

export function usePreviewMedia(
  ref: RefObject<HTMLMediaElement | null>,
  clipKey: string,
  state: PreviewMediaState,
  onError: (message: string) => void,
) {
  const controller = useRef<PreviewMediaController | null>(null);
  const errorHandler = useRef(onError);
  useEffect(() => {
    errorHandler.current = onError;
  }, [onError]);
  useEffect(() => {
    if (!ref.current) return;
    const media = new PreviewMediaController(ref.current, (message) =>
      errorHandler.current(message),
    );
    controller.current = media;
    return () => {
      media.dispose();
      controller.current = null;
    };
  }, [ref, clipKey]);
  useEffect(() => {
    controller.current?.update(state);
  }, [clipKey, state.time, state.playing, state.volume, state.loop]);
}
