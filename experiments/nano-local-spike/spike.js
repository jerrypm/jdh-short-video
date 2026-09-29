import { ideaSchema, validateIdeas } from "/validation.mjs";

const byId = (id) => document.getElementById(id);
const options = (language = "en", modality) => ({
  expectedInputs: [{ type: "text", languages: [language] }, ...(modality ? [{ type: modality }] : [])],
  expectedOutputs: [{ type: "text", languages: [language] }],
});
const report = {
  schema_version: 1, provider: "chrome-gemini-nano", inference: "on-device",
  started_at: new Date().toISOString(), user_agent: navigator.userAgent,
  origin: location.origin, capabilities: {}, results: [],
  limitations: [
    "The optional loopback companion tests a backend prototype, not the production Mac app or Native Messaging.",
    "Browser playback measurements do not prove audible Mac app playback quality.",
    "No OS-wide network audit or offline test has been performed by this page.",
  ],
};
let active = null;
let busy = false;
let saveChain = Promise.resolve();
const status = (message) => { byId("status").textContent = message; };
const errorData = (error) => ({ name: error.name || "Error", message: error.message || String(error) });
const round = (number) => Math.round(number * 10) / 10;

async function persist() {
  byId("report").textContent = JSON.stringify(report, null, 2);
  const body = JSON.stringify(report);
  saveChain = saveChain.catch(() => {}).then(async () => {
    const response = await fetch("/report", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-JDH-Spike-Token": document.querySelector('meta[name="spike-token"]').content },
      body,
    });
    if (!response.ok) throw new Error("Laporan tidak tersimpan (" + response.status + ").");
  });
  await saveChain;
}

async function operation(name, task) {
  if (busy) return;
  busy = true;
  for (const id of ["check", "prepare", "run", "cancel-test"]) byId(id).disabled = true;
  byId("stop").disabled = false;
  const controller = new AbortController();
  active = controller;
  const started = performance.now();
  const timer = setTimeout(() => controller.abort(new DOMException("Test timed out", "TimeoutError")), 120000);
  const entry = { name, at: new Date().toISOString() };
  status(name + "…");
  try {
    if (!window.LanguageModel) throw new Error("LanguageModel tidak tersedia pada browser ini.");
    Object.assign(entry, await task(controller.signal));
    entry.status = "passed";
    status(name + " selesai.");
  } catch (error) {
    entry.status = controller.signal.aborted ? "cancelled" : "failed";
    entry.error = errorData(error);
    status(name + ": " + entry.error.message);
  } finally {
    clearTimeout(timer);
    entry.elapsed_ms = round(performance.now() - started);
    report.results.push(entry);
    try { await persist(); } catch (error) { status(error.message); }
    if (active === controller) active = null;
    busy = false;
    for (const id of ["check", "prepare", "run", "cancel-test"]) byId(id).disabled = false;
    byId("stop").disabled = true;
  }
}

async function availabilityWithTimeout(sessionOptions, signal) {
  let abortHandler;
  let timer;
  try {
    return await Promise.race([
      LanguageModel.availability(sessionOptions),
      new Promise((_, reject) => {
        abortHandler = () => reject(signal.reason);
        if (signal.aborted) return abortHandler();
        signal.addEventListener("abort", abortHandler, { once: true });
        timer = setTimeout(() => reject(new Error("Availability check timed out.")), 10000);
      }),
    ]);
  } finally {
    clearTimeout(timer);
    if (abortHandler) signal.removeEventListener("abort", abortHandler);
  }
}

byId("check").addEventListener("click", () => operation("Pemeriksaan kemampuan", async (signal) => {
  for (const [key, sessionOptions] of [
    ["english_text", options("en")],
    ["indonesian_text", options("id")],
    ["english_image", options("en", "image")],
    ["english_audio", options("en", "audio")],
  ]) {
    if (signal.aborted) throw signal.reason;
    try { report.capabilities[key] = await availabilityWithTimeout(sessionOptions, signal); }
    catch (error) { report.capabilities[key] = { error: errorData(error) }; }
    await persist();
  }
  if (signal.aborted) throw signal.reason;
  return { note: "Availability only; unsupported options do not trigger inference." };
}));

byId("prepare").addEventListener("click", () => operation("Persiapan model English", async (signal) => {
  const session = await LanguageModel.create({
    ...options(), signal,
    monitor(monitor) {
      monitor.addEventListener("downloadprogress", (event) => {
        status("Unduhan model lokal: " + Math.round(event.loaded * 100) + "%");
      });
    },
  });
  session.destroy();
  report.capabilities.english_text = await availabilityWithTimeout(options(), signal);
  return { availability_after: report.capabilities.english_text };
}));

const prompt = "Return three distinct English YouTube Shorts ideas about learning SwiftUI. " +
  "Each idea has a short title and a one-sentence hook. Use general educational examples. " +
  "Do not invent statistics, personal experience, or research. Return only the requested JSON.";

const video = byId("preview");
const mediaEvents = [];
for (const name of ["playing", "waiting", "stalled", "error", "pause", "ended"]) {
  video.addEventListener(name, () => {
    mediaEvents.push({ name, at_ms: performance.now(), media_time: video.currentTime });
    byId("playback").textContent = "Playback: " + name + " · " + video.currentTime.toFixed(2) + " detik";
  });
}
function observePlayback() {
  const started = performance.now();
  const initial = { playing: !video.paused, media_time: video.currentTime };
  const eventIndex = mediaEvents.length;
  let maxTickGap = 0;
  let lastTick = started;
  const timer = setInterval(() => {
    const now = performance.now();
    maxTickGap = Math.max(maxTickGap, now - lastTick);
    lastTick = now;
  }, 100);
  return () => {
    clearInterval(timer);
    return {
      initially_playing: initial.playing,
      initial_media_time: initial.media_time, final_media_time: video.currentTime,
      wall_ms: round(performance.now() - started),
      max_main_thread_tick_gap_ms: round(Math.max(maxTickGap, performance.now() - lastTick)),
      events: mediaEvents.slice(eventIndex),
      note: "Looping media may end at an earlier timestamp. This is not an audible-quality assertion.",
    };
  };
}

byId("run").addEventListener("click", () => operation("Inference English cold + warm", async (signal) => {
  const available = await availabilityWithTimeout(options(), signal);
  if (available !== "available") throw new Error("Model belum siap: " + available + ". Gunakan Siapkan model lokal.");
  const measure = observePlayback();
  let session;
  const samples = [];
  try {
    const beforeCreate = performance.now();
    session = await LanguageModel.create({ ...options(), signal });
    const createMs = round(performance.now() - beforeCreate);
    for (const kind of ["cold_session", "warm_session"]) {
      const start = performance.now();
      const text = await session.prompt(prompt, { signal, responseConstraint: ideaSchema });
      const responseMs = round(performance.now() - start);
      const validated = validateIdeas(text);
      samples.push({ kind, prompt_ms: responseMs, validated });
    }
    return {
      session_create_ms: createMs, samples,
      playback: measure(),
      note: "Cold means first prompt in a new session, not first process launch or model download.",
    };
  } catch (error) {
    report.results.push({ name: "Partial inference evidence", status: "incomplete", samples, playback: measure() });
    throw error;
  } finally { session?.destroy(); }
}));

byId("cancel-test").addEventListener("click", () => operation("Pembatalan inference", async (signal) => {
  if (await availabilityWithTimeout(options(), signal) !== "available") throw new Error("Model belum siap.");
  let session;
  let cancelTimer;
  const local = new AbortController();
  const propagate = () => local.abort(signal.reason);
  signal.addEventListener("abort", propagate, { once: true });
  try {
    session = await LanguageModel.create({ ...options(), signal });
    const started = performance.now();
    cancelTimer = setTimeout(() => local.abort(new DOMException("Test cancellation", "AbortError")), 100);
    let error;
    try {
      await session.prompt("Write 100 different short educational video ideas, each explained in a paragraph.", { signal: local.signal });
    } catch (caught) { error = caught; }
    clearTimeout(cancelTimer);
    if (signal.aborted) throw signal.reason;
    if (!error || error.name !== "AbortError") throw new Error("AbortError was not observed; cancellation is unproven.");
    session.destroy();
    session = await LanguageModel.create({ ...options(), signal });
    const recovered = validateIdeas(await session.prompt(prompt, { signal, responseConstraint: ideaSchema }));
    return { cancellation: errorData(error), recovery_validated: recovered, total_ms: round(performance.now() - started) };
  } finally {
    clearTimeout(cancelTimer);
    signal.removeEventListener("abort", propagate);
    session?.destroy();
  }
}));

byId("stop").addEventListener("click", () => active?.abort(new DOMException("Stopped by user", "AbortError")));
byId("download").addEventListener("click", () => {
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url; link.download = "jdh-gemini-nano-local-report.json"; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

let bridgeEnabled = false;
let bridgeJobActive = false;
async function bridgeRequest(path, data) {
  const response = await fetch(path, {
    method: data ? "POST" : "GET",
    headers: {
      "Content-Type": "application/json",
      "X-JDH-Spike-Token": document.querySelector('meta[name="spike-token"]').content,
    },
    ...(data ? { body: JSON.stringify(data) } : {}),
  });
  if (!response.ok) throw new Error("Bridge HTTP " + response.status);
  return response.json();
}
byId("bridge").addEventListener("click", async () => {
  if (bridgeEnabled) return;
  if (!window.LanguageModel) return status("LanguageModel tidak tersedia.");
  const state = await LanguageModel.availability(options());
  if (state !== "available") return status("Siapkan model lokal lebih dahulu: " + state);
  bridgeEnabled = true;
  byId("bridge").disabled = true;
  const heartbeat = async () => {
    if (!bridgeEnabled) return;
    try {
      // Keep the lease live during inference, but never claim overlapping work.
      const result = await bridgeRequest("/bridge/poll");
      byId("bridge-status").textContent = bridgeJobActive ? "Memproses permintaan lokal…" : "Terhubung · menunggu permintaan lokal.";
      if (result.job) {
        if (bridgeJobActive || busy) {
          await bridgeRequest("/bridge/result", { id: result.job.id, status: "failed", error: "companion_busy" });
        } else {
          bridgeJobActive = true;
          void runBridgeJob(result.job).finally(() => { bridgeJobActive = false; });
        }
      }
    } catch (error) {
      byId("bridge-status").textContent = "Koneksi terputus: " + error.message;
    } finally {
      if (bridgeEnabled) setTimeout(heartbeat, 1000);
    }
  };
  await heartbeat();
});
async function runBridgeJob(job) {
  await operation("Permintaan backend lokal", async (signal) => {
    const started = performance.now();
    let session;
    try {
      if (job.action !== "ideas_fixture") throw new Error("Unsupported operation.");
      session = await LanguageModel.create({ ...options(), signal });
      const output = validateIdeas(await session.prompt(prompt, { signal, responseConstraint: ideaSchema }));
      const result = { id: job.id, status: "completed", output, elapsed_ms: round(performance.now() - started) };
      await bridgeRequest("/bridge/result", result);
      return { request_id: job.id, validated: output, inference_ms: result.elapsed_ms };
    } catch (error) {
      try { await bridgeRequest("/bridge/result", { id: job.id, status: "failed", error: errorData(error) }); }
      catch { /* Report the original failure even if the local server disconnected. */ }
      throw error;
    } finally { session?.destroy(); }
  });
}
