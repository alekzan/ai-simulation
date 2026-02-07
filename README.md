# AI-Driven Simulation Engine

An autonomous, multimodal narrative simulation powered by **Gemini 3**.

This project is **not a chatbot** and not a prompt wrapper.  
It is a stateful simulation engine where Gemini 3 acts as a **Narrator Director**, evolving a world over time with rules, consequences, memory, and multimodal outputs.

---

## 🚀 What is this?

AI-Driven Simulation Engine is an interactive, first-person simulation where:

- The user chooses **actions**, not chat prompts
- Gemini 3 **reasons about consequences**
- The world evolves consistently over many turns
- The simulation can run in **SHORT**, **LONG**, or **INFINITE** mode

The system is designed to feel cinematic, but behave like a **real product**: deterministic backend, strict schemas, persistent state, and low-latency multimodal generation.

---

## 🧠 Why Gemini 3?

Gemini 3 is uniquely suited for this project because it can:

- Perform **long-horizon reasoning**
- Return **structured JSON** reliably
- Orchestrate **multimodal outputs** (text, image, audio, video)
- Maintain continuity across long-running sessions

This project intentionally avoids:
- Prompt-only wrappers
- Basic RAG
- Generic chat interfaces

---

## ✨ Key Features

### 🎭 Narrative Simulation (not chat)
- Player selects first-person actions
- Gemini acts as a **Narrator Director**, not a conversational agent
- Implausible actions are punished, not ignored

### 🧩 Structured Reasoning
- Every model response is validated against **Pydantic schemas**
- Backend applies all state updates deterministically
- Inventory, skills, music, and scenes are canonicalized and persisted

### 🧠 Long-Running Autonomous Agent (Marathon-style)
- After enough turns, earlier scenes are summarized into **story memory**
- From that point on, Gemini reasons using:
  - a compact memory of the past
  - only the most recent scenes
- Enables **infinite simulations** without token explosion

### 🎨 Full Multimodality
Per scene, the system can generate:
- Narrative text
- Scene image
- Text-to-speech narration
- Background music
- Final ending video

All media is generated **in parallel** to minimize perceived latency.

### 💾 Persistent State
- SQLite is the single source of truth per session
- Full state is saved every turn:
  - scenes
  - skills
  - inventory
  - music
  - memory
  - media paths
  - token usage (dev stats)

---

## 🔁 How the Simulation Loop Works

1. **Title Selection**
   - Gemini generates multiple story concepts with titles and cover images

2. **Initialization**
   - One-time call builds:
     - dramatic concept
     - internal plot spine
     - anchor events
     - possible endings
     - initial scene
     - base skills
   - Initial media (image, TTS, music) is generated in parallel

3. **Per Turn**
   - User selects an action
   - Gemini returns structured JSON:
     - next scene
     - action options
     - skill delta (max 1)
     - inventory changes
     - narrative alignment
     - ending flags
   - Backend validates, applies, persists, and generates media

4. **Long-Run Memory**
   - After enough scenes, earlier history is summarized
   - Future turns use bounded context plus story memory

---

## 🧪 Technical Highlights

- FastAPI backend
- Strict schema validation for all model outputs
- Parallel media generation using thread pools
- Repo-relative media paths for frontend portability
- State Canonicalizer fallback to handle AI naming drift
- Clean separation between:
  - AI creativity
  - backend enforcement
  - frontend rendering

---

### Open in browser

```text
http://127.0.0.1:8000
```

## Demo Flow

1. Select a story title
2. Experience Scene 1 with image, narration, and music
3. Choose actions and watch the world evolve
4. Toggle narration and music (settings persist)
5. Continue into deeper scenes or infinite mode

## API Overview

### Start a simulation

```text
POST /api/init
```

Returns:

1. Initial scene
2. Generated image, TTS, and music
3. Session ID

### Advance the simulation

```text
POST /api/turn
```

Returns:

1. Next scene
2. Updated world state
3. Media paths
4. Skills, inventory, and flags

## Infinite Mode

The simulation does not require an ending.

If enabled, the engine:

1. Continues generating scenes
2. Periodically summarizes memory
3. Maintains coherence indefinitely

This aligns with Gemini 3 Marathon Agent philosophy.

## Why Gemini 3?

This project relies on Gemini 3 for:

1. Deep narrative reasoning
2. Structured JSON outputs
3. Multi step decision making
4. Long context understanding
5. Coordinating multimodal tools

## Status

1. Backend complete through Step 10
2. Multimodal orchestration working
3. Story memory verified in SQLite
4. Frontend vertical slice complete
5. Ready for judging

## Final Note

This project demonstrates what happens when AI is treated not as a responder, but as a director of reality.

Welcome to the simulation.
