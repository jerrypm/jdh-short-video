import { useCallback, useEffect, useRef, useState } from "react";
import { request } from "./api";
import type { Project } from "./model";

declare global {
  interface Window {
    jdhFlushProject?: () => Promise<void>;
    jdhEditorHistory?: (direction: "undo" | "redo") => void;
  }
}

export function useProject(initial: Project) {
  const [project, setProject] = useState(initial);
  const current = useRef(initial);
  const revision = useRef(initial.revision);
  const saved = useRef(JSON.stringify(initial));
  const saving = useRef<Promise<void> | null>(null);
  const [status, setStatus] = useState("Tersimpan");
  const [error, setError] = useState("");
  const history = useRef<Project[]>([]);
  const future = useRef<Project[]>([]);
  const change = useCallback((transform: (p: Project) => Project) => {
    const next = transform(current.current);
    if (next === current.current) return;
    history.current = [...history.current.slice(-49), current.current];
    future.current = [];
    current.current = next;
    setProject(next);
    setStatus("Menyimpan…");
  }, []);
  const flush = useCallback(async () => {
    if (saving.current) await saving.current;
    const value = current.current;
    const fingerprint = JSON.stringify(value);
    if (saved.current === fingerprint) {
      // A quick Undo → Redo can return to the saved value before autosave runs.
      setStatus((previous) =>
        previous === "Gagal menyimpan" ? previous : "Tersimpan",
      );
      return;
    }
    const work = (async () => {
      setStatus("Menyimpan…");
      try {
        const result = await request<Project>(`/projects/${value.id}`, "PUT", {
          ...value,
          revision: revision.current,
        });
        revision.current = result.revision;
        saved.current = fingerprint;
        setError("");
        setStatus(current.current === value ? "Tersimpan" : "Menyimpan…");
      } catch (e) {
        setError((e as Error).message);
        setStatus("Gagal menyimpan");
        throw e;
      }
    })();
    saving.current = work;
    try {
      await work;
    } finally {
      if (saving.current === work) saving.current = null;
    }
    if (current.current !== value) await flush();
  }, []);
  useEffect(() => {
    const timer = setTimeout(() => void flush().catch(() => {}), 650);
    return () => clearTimeout(timer);
  }, [project, flush]);
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (JSON.stringify(current.current) !== saved.current) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);
  const adopt = (value: Project, undoable = false) => {
    history.current = undoable
      ? [...history.current.slice(-49), current.current]
      : [];
    current.current = value;
    revision.current = value.revision;
    saved.current = JSON.stringify(value);
    setProject(value);
    setStatus("Tersimpan");
    future.current = [];
  };
  const undo = () => {
    const previous = history.current.pop();
    if (previous) {
      future.current.push(current.current);
      current.current = { ...previous, assets: current.current.assets };
      setProject(current.current);
      setStatus("Menyimpan…");
    }
  };
  const redo = () => {
    const next = future.current.pop();
    if (next) {
      history.current.push(current.current);
      current.current = { ...next, assets: current.current.assets };
      setProject(current.current);
      setStatus("Menyimpan…");
    }
  };
  useEffect(() => {
    window.jdhFlushProject = flush;
    window.jdhEditorHistory = (direction) => {
      if (
        document.activeElement?.matches(
          'input,textarea,[contenteditable="true"]',
        )
      ) {
        document.execCommand(direction);
      } else if (!document.querySelector("dialog[open]")) {
        direction === "undo" ? undo() : redo();
      }
    };
    return () => {
      delete window.jdhFlushProject;
      delete window.jdhEditorHistory;
    };
  }, [flush, undo, redo]);
  return {
    project,
    change,
    flush,
    adopt,
    undo,
    redo,
    status,
    error,
    current,
    canUndo: history.current.length > 0,
    canRedo: future.current.length > 0,
  };
}
