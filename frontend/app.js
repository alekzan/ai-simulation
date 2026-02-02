const API_BASE = "";

const el = (id) => document.getElementById(id);
const titleScreen = el("screen-title");
const sceneScreen = el("screen-scene");
const loadingScreen = el("screen-loading");
const topbar = el("topbar");
const titleCards = el("title-cards");
const lengthToggle = el("length-toggle");
const refreshTitles = el("refresh-titles");
const customStory = el("custom-story");
const startCustomStory = el("start-custom-story");
const sessionIdEl = el("session-id");
const turnCounter = el("turn-counter");
const musicState = el("music-state");
const sceneText = el("scene-text");
const sceneImage = el("scene-image");
const sceneVideo = el("scene-video");
const sceneImageFallback = el("scene-image-fallback");
const actionList = el("action-list");
const customAction = el("custom-action");
const submitCustom = el("submit-custom");
const hintList = el("hint-list");
const loadingText = el("loading-text");
const loadingHints = el("loading-hints");
const ttsToggle = el("tts-toggle");
const musicToggle = el("music-toggle");
const backToTitle = el("back-to-title");
const toast = el("toast");

const state = {
  sessionId: null,
  turnNumber: 0,
  gameLength: "SHORT",
  ttsMuted: false,
  musicMuted: false,
  currentMusicPath: null,
  ttsAudio: new Audio(),
  musicAudio: new Audio(),
};

state.musicAudio.loop = true;

const loadingHintSets = {
  ideas: [
    "Drafting story hooks.",
    "Rendering 3 cover images in parallel.",
    "Building selection cards.",
  ],
  init: [
    "Constructing dramatic spine.",
    "Generating opening media in parallel.",
    "Preparing first scene options.",
  ],
  turn: [
    "Projecting next consequences.",
    "Updating canonical state.",
    "Rendering scene media.",
  ],
};

function normalizePath(path) {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return path.startsWith("/") ? path : `/${path}`;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.remove("hidden");
  window.setTimeout(() => toast.classList.add("hidden"), 3200);
}

function setToggleState(button, label, isMuted) {
  button.textContent = `${label}: ${isMuted ? "Off" : "On"}`;
  button.classList.toggle("is-off", isMuted);
}

function persistSettings() {
  localStorage.setItem("ttsMuted", JSON.stringify(state.ttsMuted));
  localStorage.setItem("musicMuted", JSON.stringify(state.musicMuted));
}

function loadSettings() {
  state.ttsMuted = JSON.parse(localStorage.getItem("ttsMuted") || "false");
  state.musicMuted = JSON.parse(localStorage.getItem("musicMuted") || "false");
  state.ttsAudio.muted = state.ttsMuted;
  state.musicAudio.muted = state.musicMuted;
  setToggleState(ttsToggle, "TTS", state.ttsMuted);
  setToggleState(musicToggle, "Music", state.musicMuted);
}

function updateTopStatus() {
  turnCounter.textContent = `Turn ${state.turnNumber || 1}`;
}

function setMusicState(label) {
  musicState.textContent = label;
}

function showScreen(screen) {
  [titleScreen, sceneScreen, loadingScreen].forEach((node) =>
    node.classList.add("hidden")
  );
  screen.classList.remove("hidden");

  const showTopbar = screen === sceneScreen || (screen === loadingScreen && !!state.sessionId);
  topbar.classList.toggle("hidden", !showTopbar);
}

function setLoading(message, hints) {
  loadingText.textContent = message;
  loadingHints.innerHTML = "";
  (hints || []).forEach((hint) => {
    const li = document.createElement("li");
    li.textContent = hint;
    loadingHints.appendChild(li);
  });
  showScreen(loadingScreen);
}

function renderSceneText(text) {
  sceneText.innerHTML = "";
  text.split("\n").forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    const p = document.createElement("p");
    p.textContent = trimmed;
    sceneText.appendChild(p);
  });
}

function renderHints(hints) {
  hintList.innerHTML = "";
  const lines = hints?.lines?.length
    ? hints.lines
    : [
        { text: "Stay coherent with your objective." },
        { text: "The system rewards plausible intent." },
        { text: "Unexpected choices produce stronger shifts." },
      ];

  lines.forEach((hint) => {
    const li = document.createElement("li");
    li.textContent = hint.text;
    hintList.appendChild(li);
  });
}

function renderActions(actions) {
  actionList.innerHTML = "";
  actions.forEach((option, index) => {
    const button = document.createElement("button");
    button.className = "action-button";
    button.textContent = `${index + 1}. ${option.action}`;
    button.addEventListener("click", () => submitAction(option.action));
    actionList.appendChild(button);
  });
}

function renderTitlePlaceholders() {
  titleCards.innerHTML = "";
  for (let i = 0; i < 3; i += 1) {
    const card = document.createElement("article");
    card.className = "card placeholder";
    card.innerHTML = `
      <div class="card-media shimmer"></div>
      <div class="card-body">
        <div class="card-title shimmer"></div>
        <div class="card-line shimmer"></div>
        <div class="card-line shimmer"></div>
      </div>
    `;
    titleCards.appendChild(card);
  }
}

function renderTitleCards(ideas) {
  titleCards.innerHTML = "";

  ideas.forEach((idea) => {
    const card = document.createElement("article");
    card.className = "card";

    const image = document.createElement("img");
    image.className = "card-media";
    image.alt = `${idea.title} cover`;
    const coverPath = normalizePath(idea.cover_image_path);
    if (coverPath) {
      image.src = coverPath;
    }

    const body = document.createElement("div");
    body.className = "card-body";

    const title = document.createElement("div");
    title.className = "card-title";
    title.textContent = idea.title;

    const hook = document.createElement("p");
    hook.textContent = idea.one_liner;

    const startButton = document.createElement("button");
    startButton.className = "primary";
    startButton.textContent = "Start this simulation";
    startButton.addEventListener("click", () => {
      const storyText = `${idea.title} - ${idea.one_liner}`;
      startGame(storyText);
    });

    body.append(title, hook, startButton);
    card.append(image, body);
    titleCards.appendChild(card);
  });
}

async function fetchJson(url, payload = null) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload ? JSON.stringify(payload) : null,
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.message || "Request failed");
  }

  return data;
}

async function loadTitleIdeas() {
  setLoading("Analyzing story candidates...", loadingHintSets.ideas);
  renderTitlePlaceholders();

  try {
    const data = await fetchJson(`${API_BASE}/api/title-options-with-covers`);
    renderTitleCards(data.ideas || []);
    showScreen(titleScreen);
  } catch (err) {
    showToast(err.message || "Could not load title ideas.");
    showScreen(titleScreen);
  }
}

async function playAudio(audio, path) {
  if (!path) return;
  const source = normalizePath(path);
  if (!source) return;
  audio.src = source;
  try {
    await audio.play();
  } catch (_err) {
    showToast("Tap anywhere to enable browser audio playback.");
  }
}

async function playSceneAudio(ttsPath, musicPath, forceMusic = false) {
  if (ttsPath && !state.ttsMuted) {
    await playAudio(state.ttsAudio, ttsPath);
  }

  if (!musicPath) return;

  if (forceMusic || state.currentMusicPath !== musicPath) {
    state.currentMusicPath = musicPath;
    if (!state.musicMuted) {
      await playAudio(state.musicAudio, musicPath);
    } else {
      state.musicAudio.src = normalizePath(musicPath);
    }
  }
}

function setMediaDisplay(mediaType) {
  const isVideo = mediaType === "video";
  sceneVideo.classList.toggle("hidden", !isVideo);
  sceneImage.classList.toggle("hidden", isVideo);
}

function renderScene(scene) {
  updateTopStatus();
  renderSceneText(scene.text_story || "");
  renderActions(scene.action_options || []);
  setMediaDisplay(scene.media_type || "image");

  if (scene.media_type === "video") {
    const source = normalizePath(scene.image_path);
    if (source) {
      sceneVideo.src = source;
    }
    return;
  }

  const imageSource = normalizePath(scene.image_path);
  if (imageSource) {
    sceneImage.src = imageSource;
    sceneImageFallback.classList.add("hidden");
  } else {
    sceneImage.removeAttribute("src");
    sceneImageFallback.classList.remove("hidden");
  }
}

async function startGame(storyText) {
  if (!storyText || !storyText.trim()) {
    showToast("Write a custom story seed or choose a generated idea.");
    return;
  }

  setLoading("Bootstrapping simulation...", loadingHintSets.init);

  try {
    const data = await fetchJson(`${API_BASE}/api/init`, {
      story_text: storyText.trim(),
      game_length_mode: state.gameLength,
    });

    state.sessionId = data.session_id;
    state.turnNumber = 1;
    state.currentMusicPath = null;
    sessionIdEl.textContent = state.sessionId.slice(0, 8);
    updateTopStatus();
    setMusicState("Initialized");

    renderScene({
      ...data.initial_scene,
      media_type: "image",
      image_path: data.initial_media?.image_path,
      tts_path: data.initial_media?.tts_path,
      music_path: data.initial_media?.music_path,
    });

    renderHints(data.initial_script?.hints || { lines: [] });
    showScreen(sceneScreen);

    await playSceneAudio(
      data.initial_media?.tts_path,
      data.initial_media?.music_path,
      true
    );
  } catch (err) {
    showToast(err.message || "Failed to initialize the simulation.");
    showScreen(titleScreen);
  }
}

async function submitAction(actionText) {
  if (!state.sessionId || !actionText) return;

  setLoading("Predicting next reality state...", loadingHintSets.turn);

  try {
    const data = await fetchJson(`${API_BASE}/api/turn`, {
      session_id: state.sessionId,
      action: actionText,
    });

    state.turnNumber = data.turn_number || state.turnNumber + 1;
    updateTopStatus();

    renderScene(data.scene || {});
    renderHints(data.hints || { lines: [] });

    const musicChanged = data.scene?.music_action === "CHANGE";
    setMusicState(musicChanged ? "Transition" : "Stable");

    showScreen(sceneScreen);

    await playSceneAudio(
      data.scene?.tts_path,
      musicChanged ? data.scene?.music_path : state.currentMusicPath,
      musicChanged
    );
  } catch (err) {
    showToast(err.message || "Failed to process turn.");
    showScreen(sceneScreen);
  }
}

lengthToggle.addEventListener("click", (event) => {
  const target = event.target.closest("button");
  if (!target || !target.dataset.length) return;

  state.gameLength = target.dataset.length;
  [...lengthToggle.querySelectorAll("button")].forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.length === state.gameLength);
  });
});

refreshTitles.addEventListener("click", () => {
  loadTitleIdeas();
});

startCustomStory.addEventListener("click", () => {
  startGame(customStory.value);
});

submitCustom.addEventListener("click", () => {
  const value = customAction.value.trim();
  if (!value) return;
  customAction.value = "";
  submitAction(value);
});

customAction.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    submitCustom.click();
  }
});

ttsToggle.addEventListener("click", () => {
  state.ttsMuted = !state.ttsMuted;
  state.ttsAudio.muted = state.ttsMuted;
  setToggleState(ttsToggle, "TTS", state.ttsMuted);
  persistSettings();
});

musicToggle.addEventListener("click", () => {
  state.musicMuted = !state.musicMuted;
  state.musicAudio.muted = state.musicMuted;
  setToggleState(musicToggle, "Music", state.musicMuted);
  persistSettings();

  if (!state.musicMuted && state.currentMusicPath) {
    playAudio(state.musicAudio, state.currentMusicPath);
  }
});

backToTitle.addEventListener("click", () => {
  state.sessionId = null;
  state.turnNumber = 0;
  state.currentMusicPath = null;
  sessionIdEl.textContent = "--";
  setMusicState("Idle");
  state.ttsAudio.pause();
  state.ttsAudio.removeAttribute("src");
  state.musicAudio.pause();
  state.musicAudio.removeAttribute("src");
  showScreen(titleScreen);
});

loadSettings();
setMusicState("Idle");
loadTitleIdeas();
