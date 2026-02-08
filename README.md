# AI-Driven Simulation Engine

An autonomous, multimodal narrative simulation powered by **Gemini 3**.

This project is **not** a chatbot and not a prompt wrapper. It is a stateful simulation engine where Gemini acts as a **Narrator Director**, evolving a world over time with rules, consequences, memory, and multimodal outputs.

## What This Is

AI-Driven Simulation Engine is an interactive first-person simulation where:

- The player chooses **actions**, not chat prompts
- Gemini reasons about **consequences**, not just style
- The world evolves with continuity across many turns
- The simulation can run in **SHORT**, **LONG**, or **INFINITE** mode

The goal is cinematic immersion with product-level rigor: deterministic backend behavior, strict schema validation, persistent state, and low-latency multimodal generation.

## Quick Start (Local)

1. Create and activate a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Start the server.

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

4. Open the app.

```text
http://127.0.0.1:8000
```

5. Enter your Gemini API key in the app’s API key screen.

Important: the backend expects a per-request key (`X-Gemini-Api-Key`). The frontend handles this automatically after you enter your key.

## Why Gemini

This project leans on Gemini because it can:

- Perform long-horizon reasoning
- Return reliable structured JSON
- Orchestrate multimodal outputs (text, image, audio, video)
- Preserve narrative continuity over longer runs

The design intentionally avoids:

- Prompt-only wrappers
- Basic RAG templates
- Generic chat UX patterns

## Key Features

### Narrative Simulation (Not Chat)

- Player actions drive the world
- The model behaves as a director, not a conversational assistant
- Implausible moves generate believable consequences

### Structured Reasoning

- Model output is validated with Pydantic schemas
- Backend applies state updates deterministically
- Skills, inventory, and narrative state are canonicalized and persisted

### Long-Running Story Memory

- Earlier scenes can be summarized into compact memory
- Future turns reason over recent scenes plus memory
- Enables long sessions without unbounded context growth

### Multimodal Output Per Scene

- Narrative text
- Scene image
- TTS narration
- Background music
- Ending video (when story reaches a terminal arc)

Media generation is orchestrated in parallel where appropriate to reduce perceived latency.

### Persistent Simulation State

- SQLite is the source of truth per session
- State includes scenes, skills, inventory, memory, media paths, and usage metrics

## How the Simulation Loop Works

1. Title selection
- Gemini generates multiple story options with title + cover

2. Initialization (`/api/init`)
- Builds dramatic concept, plot spine, anchor events, possible endings, and scene one
- Generates initial media

3. Per turn (`/api/turn`)
- Player submits one action
- Director returns structured next-scene output
- Backend validates, applies updates, persists state, and generates media

4. Long-run continuity
- Story memory summarization keeps long sessions coherent

## API Key Behavior

### Frontend flow (recommended)

- Enter key once in UI
- Stored in browser local storage
- Sent as `X-Gemini-Api-Key` on API calls

### Direct API calls

```bash
curl -X POST http://127.0.0.1:8000/api/title-options-with-covers \
  -H 'X-Gemini-Api-Key: YOUR_KEY'
```

If key is missing, backend returns `401 MISSING_API_KEY`.

## Core Endpoints

- `GET /health`
- `POST /api/title-options-with-covers`
- `POST /api/init`
- `POST /api/turn`
- `GET /api/simulation-metrics/{session_id}`

## Production Notes

- Run Uvicorn behind Nginx
- Terminate HTTPS at Nginx (Let’s Encrypt)
- Serve `/media/` directly via Nginx for better delivery performance

Minimal app process command:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

## Environment Variables

Most users can run without `.env`, but these are available:

- `APP_ENV`
- `SIM_DB_PATH`
- `TITLE_DEV_FIXED_OPTIONS`
- `GEMINI_THINKING_LEVEL`
- `GEMINI_FORCE_DEV_THINKING_LEVEL`
- `MEDIA_IMAGE_RETENTION_SECONDS`
- `MEDIA_AUDIO_RETENTION_SECONDS`
- `MEDIA_VIDEO_RETENTION_SECONDS`
- `EPHEMERAL_IMAGE_FORMAT`
- `EPHEMERAL_IMAGE_QUALITY`
- `EPHEMERAL_IMAGE_MAX_DIM`
- `ENDING_DEBUG_TOKEN`
- `GAMEOVER_DEBUG_TOKEN`

## Troubleshooting

### 401 `MISSING_API_KEY`

- Ensure key is set in UI or pass `X-Gemini-Api-Key` manually.

### 500 on `/api/init` or `/api/turn`

- Check backend logs for `MODEL_CALL_FAILED` or `MEDIA_GENERATION_FAILED`.
- Verify Gemini key validity and quota.

### Slow media in production

- Keep `/media/` served by Nginx with cache headers.
- Keep compressed image settings enabled.
- Avoid over-aggressive media deletion while sessions are active.

## Final Note

This project explores what happens when AI is treated not as a responder, but as a director of reality.

Welcome to the simulation.
