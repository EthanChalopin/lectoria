import { useMemo, useState } from "react";

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
  bookPrompt: string;
  language: string;
  tone: string;
  targetAge: string;
  chapterCount: number;
  imageStyle: string;
  childName: string;
  childAge: number;
  childTraits: string;
  favoriteThemes: string;
  fearsToAvoid: string;
  importantPeople: string;
  settingPreferences: string;
  moralOrGoal: string;
};

const STORAGE_KEY = "bookgen_api_url";

const DEFAULT_FORM: FormState = {
  apiUrl: localStorage.getItem(STORAGE_KEY) ?? "",
  bookPrompt:
    "Une aventure douce dans une foret ancienne ou un enfant decouvre un secret lumineux qui l'aide a grandir.",
  language: "fr",
  tone: "doux, merveilleux, rassurant",
  targetAge: "6-8",
  chapterCount: 4,
  imageStyle: "storybook, warm light, painterly children's illustration",
  childName: "Lina",
  childAge: 7,
  childTraits: "curieuse, sensible, courageuse",
  favoriteThemes: "foret, animaux, magie, amitie",
  fearsToAvoid: "violence, monstres effrayants",
  importantPeople: "Mamie Rose, Petit Renard",
  settingPreferences: "clairiere, cabane en bois, lac brillant",
  moralOrGoal: "prendre confiance en soi et apprendre a demander de l'aide",
};

function App() {
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [jobId, setJobId] = useState<string>("none");
  const [jobStatus, setJobStatus] = useState<JobStatus>("idle");
  const [statusText, setStatusText] = useState<string>("Ready.");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isGeneratingImages, setIsGeneratingImages] = useState(false);
  const [storyManifest, setStoryManifest] = useState<StoryManifest | null>(null);

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
        language: form.language.trim(),
        tone: form.tone.trim(),
        target_age: form.targetAge.trim(),
        chapter_count: Number(form.chapterCount),
        image_style: form.imageStyle.trim(),
        child_name: form.childName.trim(),
        child_age: Number(form.childAge),
        child_traits: form.childTraits,
        favorite_themes: form.favoriteThemes,
        fears_to_avoid: form.fearsToAvoid,
        important_people: form.importantPeople,
        setting_preferences: form.settingPreferences,
        moral_or_goal: form.moralOrGoal.trim(),
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

  const handleGenerate = async () => {
    if (!normalizedApiUrl) {
      setStatusText("Please enter the API URL first.");
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
        <h1>Personalized chapter generation</h1>
        <p className="muted">
          First generate all chapter text, then render chapter images in a second pass that keeps
          the GPU workload manageable.
        </p>
        <p className="muted">
          The worker now pauses and resumes the host-side Qwen service automatically before and
          after image rendering on a single GPU instance.
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
          <span>Global prompt</span>
          <textarea
            value={form.bookPrompt}
            onChange={(event) => updateField("bookPrompt", event.target.value)}
          />
        </label>

        <div className="row">
          <label className="field">
            <span>Language</span>
            <input
              type="text"
              value={form.language}
              onChange={(event) => updateField("language", event.target.value)}
            />
          </label>
          <label className="field">
            <span>Tone</span>
            <input
              type="text"
              value={form.tone}
              onChange={(event) => updateField("tone", event.target.value)}
            />
          </label>
        </div>

        <div className="row">
          <label className="field">
            <span>Target age</span>
            <input
              type="text"
              value={form.targetAge}
              onChange={(event) => updateField("targetAge", event.target.value)}
            />
          </label>
          <label className="field">
            <span>Chapters</span>
            <input
              type="number"
              min={1}
              max={12}
              value={form.chapterCount}
              onChange={(event) => updateField("chapterCount", Number(event.target.value))}
            />
          </label>
        </div>

        <label className="field">
          <span>Image style</span>
          <input
            type="text"
            value={form.imageStyle}
            onChange={(event) => updateField("imageStyle", event.target.value)}
          />
        </label>

        <div className="section-title">Personal profile</div>

        <div className="row">
          <label className="field">
            <span>Child name</span>
            <input
              type="text"
              value={form.childName}
              onChange={(event) => updateField("childName", event.target.value)}
            />
          </label>
          <label className="field">
            <span>Child age</span>
            <input
              type="number"
              min={1}
              max={18}
              value={form.childAge}
              onChange={(event) => updateField("childAge", Number(event.target.value))}
            />
          </label>
        </div>

        <label className="field">
          <span>Traits</span>
          <input
            type="text"
            value={form.childTraits}
            onChange={(event) => updateField("childTraits", event.target.value)}
            placeholder="curieuse, calme, imaginative"
          />
        </label>

        <label className="field">
          <span>Favorite themes</span>
          <input
            type="text"
            value={form.favoriteThemes}
            onChange={(event) => updateField("favoriteThemes", event.target.value)}
            placeholder="dragons, forets, amitie"
          />
        </label>

        <label className="field">
          <span>Fears to avoid</span>
          <input
            type="text"
            value={form.fearsToAvoid}
            onChange={(event) => updateField("fearsToAvoid", event.target.value)}
          />
        </label>

        <label className="field">
          <span>Important people</span>
          <input
            type="text"
            value={form.importantPeople}
            onChange={(event) => updateField("importantPeople", event.target.value)}
          />
        </label>

        <label className="field">
          <span>Preferred settings</span>
          <input
            type="text"
            value={form.settingPreferences}
            onChange={(event) => updateField("settingPreferences", event.target.value)}
          />
        </label>

        <label className="field">
          <span>Moral or goal</span>
          <textarea
            className="compact-textarea"
            value={form.moralOrGoal}
            onChange={(event) => updateField("moralOrGoal", event.target.value)}
          />
        </label>

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
              First generate the story text. Then launch image generation in a separate phase to
              avoid GPU memory conflicts.
            </p>
          </div>
        )}
      </section>
    </main>
  );
}

export default App;
