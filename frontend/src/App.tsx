import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import "./App.css";
import { api, ApiError } from "./api";
import { config } from "./config";
import {
  extractOrRecover,
  formatStepStatus,
  refreshVideoState,
  resolveVideoForUrl,
  shouldSkipTranscribe,
} from "./pipeline";
import type { ChatResponse, PipelineRun, ServiceHealthItem, VideoRecord } from "./types";

const serviceHealthEndpoints = [
  { name: "youtube-audio-service", url: `${config.youtubeServiceUrl}/api/v1/health` },
  { name: "audio-text-service", url: `${config.audioTextServiceUrl}/api/v1/health` },
  { name: "rag-indexer", url: `${config.ragIndexerUrl}/health` },
  { name: "chat-service", url: `${config.chatServiceUrl}/health` },
  { name: "db-service", url: `${config.dbServiceUrl}/api/v1/health` },
];

function App() {
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [collection, setCollection] = useState(config.defaultCollection);
  const [knownVideo, setKnownVideo] = useState<VideoRecord | null>(null);
  const [knownVideoLoading, setKnownVideoLoading] = useState(false);
  const [pipelineInProgress, setPipelineInProgress] = useState(false);
  const [pipelineRuns, setPipelineRuns] = useState<PipelineRun[]>([]);

  const [collections, setCollections] = useState<string[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(false);

  const [question, setQuestion] = useState("");
  const [chatCollection, setChatCollection] = useState(config.defaultCollection);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatResponse, setChatResponse] = useState<ChatResponse | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);

  const [serviceHealth, setServiceHealth] = useState<ServiceHealthItem[]>([]);
  const [healthLoading, setHealthLoading] = useState(false);

  const latestRun = useMemo(() => pipelineRuns[0] ?? null, [pipelineRuns]);

  const loadCollections = async () => {
    try {
      setCollectionsLoading(true);
      const response = await api.getCollections();
      const names = response.collections.map((item) => item.name);
      setCollections(names);
      if (names.length > 0 && !names.includes(chatCollection)) {
        setChatCollection(names[0]);
      }
    } catch {
      setCollections([]);
    } finally {
      setCollectionsLoading(false);
    }
  };

  const loadHealth = async () => {
    setHealthLoading(true);
    try {
      const checks = await Promise.all(
        serviceHealthEndpoints.map((service) => api.getServiceHealth(service.name, service.url))
      );
      setServiceHealth(
        checks.map((item) => ({
          name: item.name,
          status:
            item.status === "healthy" || item.status === "degraded" || item.status === "unhealthy"
              ? item.status
              : "unknown",
          detail: item.detail,
        }))
      );
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    loadCollections();
    loadHealth();
    const interval = window.setInterval(loadHealth, 30000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    const url = youtubeUrl.trim();
    if (!url) {
      setKnownVideo(null);
      return;
    }

    let cancelled = false;
    setKnownVideoLoading(true);

    resolveVideoForUrl(url)
      .then((video) => {
        if (!cancelled) {
          setKnownVideo(video);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setKnownVideo(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setKnownVideoLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [youtubeUrl]);

  const resolvedVideoId = useMemo(
    () => knownVideo?.video_id ?? api.extractVideoId(youtubeUrl.trim()),
    [knownVideo, youtubeUrl]
  );

  const executePipeline = async (
    runId: string,
    url: string,
    targetCollection: string,
    startAt: "extract" | "transcribe" | "index"
  ) => {
    let videoId = resolvedVideoId ?? api.extractVideoId(url);
    let extractSkipped = false;
    let transcribeSkipped = false;

    if (startAt === "extract") {
      updateRun(runId, { extractStatus: "running" });
      const existingVideo = await resolveVideoForUrl(url);
      const extract = await extractOrRecover(url, existingVideo);
      extractSkipped = Boolean(extract.skipped);
      videoId = extract.video_id;
      updateRun(runId, {
        extractStatus: "success",
        extractSkipped,
        transcribeStatus: "running",
        videoId: extract.video_id,
        title: extract.title,
      });
    } else if (!videoId) {
      throw new ApiError("Could not determine video_id from URL");
    } else if (startAt === "transcribe") {
      updateRun(runId, {
        extractStatus: "success",
        extractSkipped: true,
        transcribeStatus: "running",
        videoId,
        title: knownVideo?.title,
      });
    } else {
      updateRun(runId, {
        extractStatus: "success",
        extractSkipped: true,
        transcribeStatus: "success",
        transcribeSkipped: true,
        indexStatus: "running",
        videoId,
        title: knownVideo?.title,
      });
    }

    if (startAt !== "index") {
      const videoState = videoId ? await refreshVideoState(videoId) : null;
      if (shouldSkipTranscribe(videoState)) {
        transcribeSkipped = true;
        updateRun(runId, {
          transcribeStatus: "success",
          transcribeSkipped: true,
          indexStatus: "running",
        });
      } else {
        await api.processAudio(videoId!);
        updateRun(runId, {
          transcribeStatus: "success",
          indexStatus: "running",
        });
      }
    }

    await api.indexByVideoId(videoId!, targetCollection);
    updateRun(runId, {
      indexStatus: "success",
    });

    await loadCollections();
  };

  const updateRun = (runId: string, patch: Partial<PipelineRun>) => {
    setPipelineRuns((current) =>
      current.map((run) => (run.id === runId ? { ...run, ...patch } : run))
    );
  };

  const runPipeline = async (event: FormEvent) => {
    event.preventDefault();
    if (!youtubeUrl.trim() || !collection.trim()) {
      return;
    }

    const runId = crypto.randomUUID();
    const initialRun: PipelineRun = {
      id: runId,
      startedAt: new Date().toISOString(),
      youtubeUrl: youtubeUrl.trim(),
      collection: collection.trim(),
      extractStatus: "running",
      transcribeStatus: "idle",
      indexStatus: "idle",
    };

    setPipelineRuns((current) => [initialRun, ...current].slice(0, 10));
    setPipelineInProgress(true);

    try {
      await executePipeline(runId, initialRun.youtubeUrl, initialRun.collection, "extract");
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Unknown error";

      setPipelineRuns((current) =>
        current.map((run) => {
          if (run.id !== runId) {
            return run;
          }

          if (run.extractStatus === "running") {
            return { ...run, extractStatus: "failed", error: message };
          }
          if (run.transcribeStatus === "running") {
            return { ...run, transcribeStatus: "failed", error: message };
          }
          if (run.indexStatus === "running") {
            return { ...run, indexStatus: "failed", error: message };
          }

          return { ...run, error: message };
        })
      );
    } finally {
      setPipelineInProgress(false);
    }
  };

  const runFromStep = async (startAt: "transcribe" | "index") => {
    if (!collection.trim()) {
      return;
    }
    if (!resolvedVideoId && !youtubeUrl.trim()) {
      return;
    }

    const runId = crypto.randomUUID();
    const initialRun: PipelineRun = {
      id: runId,
      startedAt: new Date().toISOString(),
      youtubeUrl: youtubeUrl.trim() || resolvedVideoId || "",
      collection: collection.trim(),
      extractStatus: startAt === "index" ? "success" : "idle",
      transcribeStatus: startAt === "index" ? "success" : "running",
      indexStatus: startAt === "index" ? "running" : "idle",
      extractSkipped: true,
      transcribeSkipped: startAt === "index",
      videoId: resolvedVideoId ?? undefined,
      title: knownVideo?.title,
    };

    setPipelineRuns((current) => [initialRun, ...current].slice(0, 10));
    setPipelineInProgress(true);

    try {
      await executePipeline(
        runId,
        initialRun.youtubeUrl,
        initialRun.collection,
        startAt
      );
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Unknown error";

      setPipelineRuns((current) =>
        current.map((run) => {
          if (run.id !== runId) {
            return run;
          }

          if (run.transcribeStatus === "running") {
            return { ...run, transcribeStatus: "failed", error: message };
          }
          if (run.indexStatus === "running") {
            return { ...run, indexStatus: "failed", error: message };
          }

          return { ...run, error: message };
        })
      );
    } finally {
      setPipelineInProgress(false);
    }
  };

  const askQuestion = async (event: FormEvent) => {
    event.preventDefault();
    if (!question.trim() || !chatCollection.trim()) {
      return;
    }

    setChatLoading(true);
    setChatError(null);
    setChatResponse(null);
    try {
      const response = await api.chat(question.trim(), chatCollection.trim(), 5);
      setChatResponse(response);
    } catch (error) {
      setChatError(error instanceof Error ? error.message : "Failed to query chat service");
    } finally {
      setChatLoading(false);
    }
  };

  const rerunLatest = () => {
    if (!latestRun || pipelineInProgress) {
      return;
    }
    setYoutubeUrl(latestRun.youtubeUrl);
    setCollection(latestRun.collection);
  };

  return (
    <main className="page">
      <header className="pageHeader">
        <h1>Bold Quokka Platform UI</h1>
        <p>Run ingestion, transcription, indexing, and chat in one place.</p>
      </header>

      <section className="grid">
        <article className="card">
          <h2>Guided Pipeline</h2>
          <p className="muted">
            One-click flow: Extract → Transcribe → Index. Skips steps already in Postgres.
          </p>
          {knownVideoLoading && <p className="muted">Checking database for this video…</p>}
          {knownVideo && (
            <p className="muted">
              Found in DB: <strong>{knownVideo.title}</strong> — audio: yes, text:{" "}
              {knownVideo.text_status === "TEXT" ? "yes" : "no"}
            </p>
          )}
          <form className="stack" onSubmit={runPipeline}>
            <label className="field">
              <span>YouTube URL</span>
              <input
                value={youtubeUrl}
                onChange={(event) => setYoutubeUrl(event.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                required
              />
            </label>
            <label className="field">
              <span>Collection</span>
              <input
                value={collection}
                onChange={(event) => setCollection(event.target.value)}
                placeholder="batem-palma"
                required
              />
            </label>
            <div className="actions">
              <button type="submit" disabled={pipelineInProgress}>
                {pipelineInProgress ? "Running..." : "Run Pipeline"}
              </button>
              <button
                type="button"
                className="secondary"
                disabled={pipelineInProgress || !resolvedVideoId}
                onClick={() => runFromStep("transcribe")}
              >
                Transcribe Only
              </button>
              <button
                type="button"
                className="secondary"
                disabled={pipelineInProgress || !resolvedVideoId}
                onClick={() => runFromStep("index")}
              >
                Index Only
              </button>
              <button type="button" className="secondary" onClick={rerunLatest}>
                Reuse Last Input
              </button>
            </div>
          </form>

          <div className="runHistory">
            {pipelineRuns.length === 0 ? (
              <p className="muted">No runs yet.</p>
            ) : (
              pipelineRuns.map((run) => (
                <div className="runItem" key={run.id}>
                  <div className="runHeader">
                    <strong>{run.title ?? run.youtubeUrl}</strong>
                    <span>{new Date(run.startedAt).toLocaleTimeString()}</span>
                  </div>
                  <p className="muted">
                    video_id: {run.videoId ?? "pending"} | collection: {run.collection}
                  </p>
                  <div className="statusRow">
                    <span
                      className={`status ${run.extractSkipped ? "skipped" : run.extractStatus}`}
                    >
                      extract: {formatStepStatus(run.extractStatus, run.extractSkipped)}
                    </span>
                    <span
                      className={`status ${run.transcribeSkipped ? "skipped" : run.transcribeStatus}`}
                    >
                      transcribe: {formatStepStatus(run.transcribeStatus, run.transcribeSkipped)}
                    </span>
                    <span className={`status ${run.indexStatus}`}>index: {run.indexStatus}</span>
                  </div>
                  {run.error && <p className="error">{run.error}</p>}
                </div>
              ))
            )}
          </div>
        </article>

        <article className="card">
          <h2>Chat Workspace</h2>
          <p className="muted">Ask questions on indexed transcript collections.</p>

          <form className="stack" onSubmit={askQuestion}>
            <label className="field">
              <span>Collection</span>
              <select
                value={chatCollection}
                onChange={(event) => setChatCollection(event.target.value)}
                disabled={collectionsLoading || collections.length === 0}
              >
                {collections.length === 0 ? (
                  <option value={config.defaultCollection}>{config.defaultCollection}</option>
                ) : (
                  collections.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))
                )}
              </select>
            </label>
            <label className="field">
              <span>Question</span>
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Who was the main contestant and what was their strategy?"
                required
              />
            </label>
            <div className="actions">
              <button type="submit" disabled={chatLoading}>
                {chatLoading ? "Asking..." : "Ask"}
              </button>
              <button type="button" className="secondary" onClick={loadCollections}>
                Refresh Collections
              </button>
            </div>
          </form>

          {chatError && <p className="error">{chatError}</p>}

          {chatResponse && (
            <div className="chatResult">
              <h3>Answer</h3>
              <p>{chatResponse.answer}</p>
              <h3>Sources</h3>
              {chatResponse.sources.length === 0 ? (
                <p className="muted">No sources returned.</p>
              ) : (
                <ul className="sourceList">
                  {chatResponse.sources.map((source, index) => (
                    <li key={`${source.video_id}-${source.chunk_index}-${index}`}>
                      <strong>{source.title || source.video_id}</strong>
                      <span>score: {source.score.toFixed(3)}</span>
                      <p>{source.text_preview}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </article>
      </section>

      <section className="card">
        <div className="healthHeader">
          <h2>Service Health</h2>
          <button type="button" className="secondary" onClick={loadHealth} disabled={healthLoading}>
            {healthLoading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
        <div className="healthGrid">
          {serviceHealth.map((service) => (
            <div key={service.name} className="healthItem">
              <div>
                <strong>{service.name}</strong>
                <p className="muted">{service.detail ?? "No errors reported"}</p>
              </div>
              <span className={`status ${service.status}`}>{service.status}</span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

export default App;
