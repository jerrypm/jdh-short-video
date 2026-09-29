import { useEffect, useState } from "react";
import { bootstrap, request } from "@/lib/api";
import { ideaActivity } from "@/lib/dailyIdeas";
import type { Project } from "@/lib/model";
import Projects from "./Projects";
import Setup from "./Setup";
import Workspace from "./Workspace";
import ContentMemory from "./ContentMemory";
import Performance from "./Performance";
import Research from "./Research";
import { Busy, Brand } from "./UI";
export default function Studio() {
  const [projects, setProjects] = useState<Project[]>([]),
    [ideaId, setIdeaId] = useState<string | undefined>(undefined),
    [active, setActive] = useState<Project | null>(null),
    [setup, setSetup] = useState(false),
    [memory, setMemory] = useState(false),
    [performance, setPerformance] = useState(false),
    [research, setResearch] = useState(false),
    [ready, setReady] = useState(false),
    [error, setError] = useState("");
  const refresh = async () =>
    setProjects(await request<Project[]>("/projects"));
  useEffect(() => {
    bootstrap()
      .then(refresh)
      .then(() => setReady(true))
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!ready || (!active && !setup && !memory && !performance && !research))
      return;
    const heartbeat = () => {
      void ideaActivity(true).catch(() => undefined);
    };
    heartbeat();
    const timer = setInterval(heartbeat, 5000);
    return () => clearInterval(timer);
  }, [ready, active, setup, memory, performance, research]);
  if (!ready)
    return (
      <div className="loading-page">
        <Brand />
        {error ? (
          <p className="error-banner">
            {error}
            <button onClick={() => location.reload()}>Coba lagi</button>
          </p>
        ) : (
          <Busy text="Membuka studio lokal…" />
        )}
      </div>
    );
  if (setup) return <Setup onBack={() => setSetup(false)} />;
  if (memory) return <ContentMemory onBack={() => setMemory(false)} />;
  if (performance) return <Performance onBack={() => setPerformance(false)} />;
  if (research) return <Research onBack={() => setResearch(false)} />;
  if (active)
    return (
      <Workspace
        key={active.id}
        initial={active}
        initialIdeaId={ideaId}
        onBack={() => {
          setActive(null);
          setIdeaId(undefined);
          void refresh();
        }}
        onSetup={(p) => {
          setActive(p);
          setSetup(true);
        }}
      />
    );
  return (
    <Projects
      projects={projects}
      onOpen={(p) => {
        setIdeaId(undefined);
        setActive(p);
      }}
      onDraft={(p, id) => {
        setIdeaId(id);
        setActive(p);
      }}
      onSetup={() => setSetup(true)}
      onMemory={() => setMemory(true)}
      onPerformance={() => setPerformance(true)}
      onResearch={() => setResearch(true)}
      onRefresh={() => void refresh()}
    />
  );
}
