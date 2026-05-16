import { ChangeEvent, DragEvent, useMemo, useRef, useState } from "react";

type JobStatus =
  | "idle"
  | "queued"
  | "in_progress"
  | "text_completed"
  | "completed"
  | "failed"
  | "unknown";

type StoryChapter = {
  chapter_number: number;
  title: string;
  summary: string;
  status: string;
  chapter_url?: string | null;
  image_url?: string | null;
  content?: {
    chapter_text?: string;
    visual_prompt?: string;
  };
};

type StoryManifest = {
  story_id: string;
  status: string;
  phase?: string;
  title: string;
  logline?: string;
  chapters_total: number;
  chapters_completed: number;
  chapters_text_completed?: number;
  chapters_images_completed?: number;
  chapters: StoryChapter[];
};

type JobResponse = {
  job_id: string;
  story_id?: string;
  status?: JobStatus;
  updated_at?: string;
  output_url?: string | null;
  error?: string | null;
  current_stage?: string | null;
  chapters_total?: number;
  chapters_completed?: number;
  story_title?: string | null;
  story_manifest?: StoryManifest | null;
};

type FormState = {
  apiUrl: string;
  childName: string;
  bookPrompt: string;
};

const STORAGE_KEY = "bookgen_api_url";

const DEFAULTS = {
  language: "fr",
  tone: "doux, merveilleux, rassurant",
  targetAge: "6-8",
  chapterCount: 2,
  imageStyle: "storybook, warm light, painterly children's illustration",
  childAge: 7,
  childTraits: "curieux, sensible, courageux",
  favoriteThemes: "foret, animaux, magie, amitie",
  fearsToAvoid: "violence, monstres effrayants",
  importantPeople: "Mamie Rose, Petit Renard",
  settingPreferences: "clairiere, cabane en bois, lac brillant",
  moralOrGoal: "prendre confiance en soi et apprendre a demander de l'aide",
};

const DEFAULT_FORM: FormState = {
  apiUrl: localStorage.getItem(STORAGE_KEY) ?? "",
  childName: "Lina",
  bookPrompt:
    "Une aventure douce dans une foret ancienne ou l'enfant decouvre un secret lumineux qui l'aide a grandir.",
};

function App() {
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [jobId, setJobId] = useState<string>("none");
  const [jobStatus, setJobStatus] = useState<JobStatus>("idle");
  const [statusText, setStatusText] = useState<string>("Ready.");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isGeneratingImages, setIsGeneratingImages] = useState(false);
  const [storyManifest, setStoryManifest] = useState<StoryManifest | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const normalizedApiUrl = useMemo(
    () => form.apiUrl.trim().replace(/\/$/, ""),
    [form.apiUrl]
  );

  const updateField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  async function createStoryJob(): Promise<JobResponse> {
    const response = await fetch(`${normalizedApiUrl}/jobs/story`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        book_prompt: form.bookPrompt.trim(),
        language: DEFAULTS.language,
        tone: DEFAULTS.tone,
        target_age: DEFAULTS.targetAge,
        chapter_count: DEFAULTS.chapterCount,
        image_style: DEFAULTS.imageStyle,
        child_name: form.childName.trim(),
        child_age: DEFAULTS.childAge,
        child_traits: DEFAULTS.childTraits,
        favorite_themes: DEFAULTS.favoriteThemes,
        fears_to_avoid: DEFAULTS.fearsToAvoid,
        important_people: DEFAULTS.importantPeople,
        setting_preferences: DEFAULTS.settingPreferences,
        moral_or_goal: DEFAULTS.moralOrGoal,
      }),
    });

    if (!response.ok) {
      throw new Error(`Job creation failed (${response.status})`);
    }

    return response.json();
  }

  async function createStoryImagesJob(currentStoryId: string): Promise<JobResponse> {
    const response = await fetch(`${normalizedApiUrl}/jobs/${currentStoryId}/images`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!response.ok) {
      throw new Error(`Image job creation failed (${response.status})`);
    }
    return response.json();
  }

  async function fetchJob(currentJobId: string): Promise<JobResponse> {
    const response = await fetch(`${normalizedApiUrl}/jobs/${currentJobId}`);
    if (!response.ok) {
      throw new Error(`Status fetch failed (${response.status})`);
    }
    return response.json();
  }

  function buildStatusText(job: JobResponse): string {
    const manifest = job.story_manifest;
    return [
      `Job ${job.job_id}`,
      `Status: ${job.status ?? "unknown"}`,
      `Stage: ${job.current_stage ?? "n/a"}`,
      `Title: ${job.story_title ?? manifest?.title ?? "n/a"}`,
      `Text progress: ${manifest?.chapters_text_completed ?? 0}/${job.chapters_total ?? manifest?.chapters_total ?? 0}`,
      `Image progress: ${manifest?.chapters_images_completed ?? 0}/${job.chapters_total ?? manifest?.chapters_total ?? 0}`,
      `Updated: ${job.updated_at ?? "n/a"}`,
      job.error ? `Error: ${job.error}` : "",
    ]
      .filter(Boolean)
      .join("\n");
  }

  async function pollJob(currentJobId: string): Promise<void> {
    const job = await fetchJob(currentJobId);
    const status = job.status ?? "unknown";
    setJobStatus(status);
    setStatusText(buildStatusText(job));
    setStoryManifest(job.story_manifest ?? null);

    if (status === "completed" || status === "text_completed") {
      return;
    }

    if (status === "failed") {
      throw new Error(job.error ?? "Story generation failed");
    }

    window.setTimeout(() => {
      pollJob(currentJobId).catch((error: Error) => {
        setStatusText(`Polling error: ${error.message}`);
        setJobStatus("failed");
      });
    }, 5000);
  }

  async function loadPromptFile(file: File) {
    const text = await file.text();
    updateField("bookPrompt", text.trim());
    setStatusText(`Prompt loaded from ${file.name}.`);
  }

  const handleFileSelection = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    await loadPromptFile(file);
    event.target.value = "";
  };

  const handleDrop = async (event: DragEvent<HTMLButtonElement>) => {
    event.preventDefault();
    setIsDragActive(false);
    const file = event.dataTransfer.files?.[0];
    if (!file) {
      return;
    }
    await loadPromptFile(file);
  };

  const handleGenerate = async () => {
    if (!normalizedApiUrl) {
      setStatusText("Please enter the API URL first.");
      return;
    }
    if (!form.childName.trim() || !form.bookPrompt.trim()) {
      setStatusText("Please enter the child's name and a prompt.");
      return;
    }

    localStorage.setItem(STORAGE_KEY, normalizedApiUrl);
    setIsGenerating(true);
    setStoryManifest(null);
    setJobId("none");
    setJobStatus("idle");
    setStatusText("Sending story text job...");

    try {
      const job = await createStoryJob();
      const currentJobId = job.job_id;
      setJobId(currentJobId);
      setJobStatus(job.status ?? "queued");
      setStatusText(`Story text job ${currentJobId} created.\nPlanning chapters...`);
      await pollJob(currentJobId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setStatusText(`Error: ${message}`);
      setJobStatus("failed");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleGenerateImages = async () => {
    if (!normalizedApiUrl || !storyManifest?.story_id) {
      setStatusText("Generate story text first.");
      return;
    }

    setIsGeneratingImages(true);
    setStatusText("Sending image generation job...");

    try {
      const job = await createStoryImagesJob(storyManifest.story_id);
      const currentJobId = job.job_id;
      setJobId(currentJobId);
      setJobStatus(job.status ?? "queued");
      setStatusText(`Image job ${currentJobId} created.\nRendering chapter images...`);
      await pollJob(storyManifest.story_id);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setStatusText(`Error: ${message}`);
      setJobStatus("failed");
    } finally {
      setIsGeneratingImages(false);
    }
  };

  return (
    <main className="app-shell">
      <section className="panel">
        <div className="eyebrow">Bookgen Studio</div>
        <h1>Histoire en deux clics</h1>
        <p className="muted">
          Entre juste le nom de l'enfant et ton idee d'histoire. Tu peux aussi glisser un fichier
          texte de prompt dans la zone prevue.
        </p>

        <label className="field">
          <span>API URL</span>
          <input
            type="text"
            value={form.apiUrl}
            onChange={(event) => updateField("apiUrl", event.target.value)}
            placeholder="https://xxxx.execute-api.eu-west-1.amazonaws.com"
          />
        </label>

        <label className="field">
          <span>Nom de l'enfant</span>
          <input
            type="text"
            value={form.childName}
            onChange={(event) => updateField("childName", event.target.value)}
            placeholder="Lina"
          />
        </label>

        <label className="field">
          <span>Prompt</span>
          <textarea
            value={form.bookPrompt}
            onChange={(event) => updateField("bookPrompt", event.target.value)}
            placeholder="Decris l'univers, l'ambiance et l'aventure que tu veux raconter."
          />
        </label>

        <div className="field">
          <span>Glisser-deposer un prompt texte</span>
          <button
            type="button"
            className={`dropzone ${isDragActive ? "dropzone-active" : ""}`}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragActive(true);
            }}
            onDragLeave={() => setIsDragActive(false)}
            onDrop={(event) => {
              handleDrop(event).catch((error: Error) => {
                setStatusText(`Error: ${error.message}`);
                setJobStatus("failed");
              });
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <strong>Glisse un fichier `.txt` ici</strong>
            <span>ou clique pour en choisir un depuis le projet.</span>
          </button>
          <input
            ref={fileInputRef}
            className="hidden-file-input"
            type="file"
            accept=".txt,text/plain"
            onChange={(event) => {
              handleFileSelection(event).catch((error: Error) => {
                setStatusText(`Error: ${error.message}`);
                setJobStatus("failed");
              });
            }}
          />
        </div>

        <button type="button" onClick={handleGenerate} disabled={isGenerating}>
          {isGenerating ? "Generating..." : "Generate Story Text"}
        </button>
        <button
          type="button"
          onClick={handleGenerateImages}
          disabled={
            isGeneratingImages ||
            !storyManifest ||
            (storyManifest.chapters_text_completed ?? 0) !== storyManifest.chapters_total
          }
        >
          {isGeneratingImages ? "Rendering..." : "Generate Chapter Images"}
        </button>

        <pre className="status-box">{statusText}</pre>
      </section>

      <section className="viewer">
        <div className="viewer-meta">
          <div>
            <div>
              Current job: <code>{jobId}</code>
            </div>
            <div>
              Status: <code>{jobStatus}</code>
            </div>
          </div>
          {storyManifest ? (
            <div className="progress-pill">
              Text {storyManifest.chapters_text_completed ?? 0}/{storyManifest.chapters_total} ·
              Images {storyManifest.chapters_images_completed ?? 0}/{storyManifest.chapters_total}
            </div>
          ) : null}
        </div>

        {storyManifest ? (
          <div className="story-board">
            <header className="story-header">
              <h2>{storyManifest.title}</h2>
              <p>{storyManifest.logline}</p>
            </header>

            <div className="chapter-grid">
              {storyManifest.chapters.map((chapter) => (
                <article key={chapter.chapter_number} className="chapter-card">
                  <div className="chapter-card-header">
                    <div className="chapter-index">Chapter {chapter.chapter_number}</div>
                    <div className={`chapter-status status-${chapter.status}`}>{chapter.status}</div>
                  </div>
                  <h3>{chapter.title}</h3>
                  <p className="chapter-summary">{chapter.summary}</p>
                  {chapter.image_url ? (
                    <img className="chapter-image" src={chapter.image_url} alt={chapter.title} />
                  ) : (
                    <div className="placeholder compact-placeholder">
                      The image will appear here when chapter rendering finishes.
                    </div>
                  )}
                  <p className="chapter-text">
                    {chapter.content?.chapter_text ??
                      "The chapter text is being prepared and will show up here as soon as it is generated."}
                  </p>
                </article>
              ))}
            </div>
          </div>
        ) : (
          <div className="empty-state">
            <h2>Story workspace</h2>
            <p>
              Generate the story text first, then launch image generation when the chapters are
              ready.
            </p>
          </div>
        )}
      </section>
    </main>
  );
}

export default App;
