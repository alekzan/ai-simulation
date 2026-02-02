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
const sceneText = el("scene-text");
const sceneImage = el("scene-image");
const sceneVideo = el("scene-video");
const sceneImageFallback = el("scene-image-fallback");
const actionList = el("action-list");
const customAction = el("custom-action");
const submitCustom = el("submit-custom");
const skillsList = el("skills-list");
const inventoryList = el("inventory-list");
const loadingText = el("loading-text");
const loadingSubtext = el("loading-subtext");
const loadingHints = el("loading-hints");
const loadingHintsPanel = el("loading-hints-panel");
const loaderLayout = el("loader-layout");
const metricsToggle = el("metrics-toggle");
const ttsToggle = el("tts-toggle");
const musicToggle = el("music-toggle");
const backToTitle = el("back-to-title");
const toast = el("toast");
const resetModal = el("reset-modal");
const cancelReset = el("cancel-reset");
const confirmReset = el("confirm-reset");
const metricsModal = el("metrics-modal");
const closeMetrics = el("close-metrics");
const metricInput = el("metric-input");
const metricThinking = el("metric-thinking");
const metricOutput = el("metric-output");
const metricTotal = el("metric-total");
const metricsBreakdown = el("metrics-breakdown");

const state = {
  sessionId: null,
  turnNumber: 0,
  gameLength: "SHORT",
  ttsMuted: false,
  musicMuted: false,
  transitionHints: [],
  currentMusicPath: null,
  currentTtsPath: null,
  inventory: [],
  inventoryDelta: [],
  skills: [],
  skillDelta: [],
  simulationMetrics: null,
  ttsAudio: new Audio(),
  musicAudio: new Audio(),
};

state.musicAudio.loop = true;
const defaultTurnLoadingHints = [
  "Reading your intent and projected risk.",
  "Rebalancing the simulation around your move.",
  "Materializing the next observed moment.",
];

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
  state.musicAudio.muted = state.musicMuted;
  setToggleState(ttsToggle, "TTS", state.ttsMuted);
  setToggleState(musicToggle, "Music", state.musicMuted);
}

function updateTopStatus() {
  turnCounter.textContent = `Turn ${state.turnNumber || 1}`;
}

function _fmt(value) {
  return Number(value || 0).toLocaleString();
}

function renderSimulationMetrics(metrics) {
  const totals = metrics?.totals || {};
  metricInput.textContent = _fmt(totals.input_tokens);
  metricThinking.textContent = _fmt(totals.thinking_tokens);
  metricOutput.textContent = _fmt(totals.output_tokens);
  metricTotal.textContent = _fmt(totals.total_tokens);

  const byCall = metrics?.by_call_type || {};
  const entries = Object.entries(byCall);
  if (!entries.length) {
    metricsBreakdown.textContent = "No calls yet.";
    return;
  }

  metricsBreakdown.innerHTML = "";
  entries
    .sort((a, b) => (b[1]?.total_tokens || 0) - (a[1]?.total_tokens || 0))
    .forEach(([callType, usage]) => {
      const row = document.createElement("div");
      row.className = "metrics-breakdown-row";
      const label = document.createElement("span");
      label.textContent = callType.replaceAll("_", " ");
      const value = document.createElement("span");
      value.textContent = `${_fmt(usage.total_tokens)} total`;
      row.append(label, value);
      metricsBreakdown.appendChild(row);
    });
}

function setSimulationMetrics(metrics) {
  state.simulationMetrics = metrics || null;
  renderSimulationMetrics(state.simulationMetrics);
}

function showScreen(screen) {
  [titleScreen, sceneScreen, loadingScreen].forEach((node) =>
    node.classList.add("hidden")
  );
  screen.classList.remove("hidden");

  const showTopbar = screen === sceneScreen || (screen === loadingScreen && !!state.sessionId);
  topbar.classList.toggle("hidden", !showTopbar);
}

function setLoading(message, hints, subtext) {
  const safeHints = Array.isArray(hints) ? hints.filter(Boolean) : [];
  loadingText.textContent = message;
  loadingSubtext.textContent =
    subtext ||
    "Synchronizing simulation layers before the next scene resolves.";
  loadingHints.innerHTML = "";
  safeHints.forEach((hint) => {
    const li = document.createElement("li");
    li.textContent = hint;
    loadingHints.appendChild(li);
  });
  loadingHintsPanel.classList.toggle("hidden", safeHints.length === 0);
  loaderLayout.classList.toggle("no-hints", safeHints.length === 0);
  showScreen(loadingScreen);
}

function extractHintTexts(hints) {
  const lines = hints?.lines || [];
  return lines.map((line) => line.text).filter(Boolean);
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

function _skillKey(skill) {
  return `${skill.domain}::${skill.name}`;
}

function setSkills(skills, skillDelta) {
  state.skills = Array.isArray(skills) ? skills : [];
  state.skillDelta = Array.isArray(skillDelta) ? skillDelta : [];
  const changedByKey = new Map(
    state.skillDelta.map((row) => [_skillKey(row), row.delta || 0])
  );

  skillsList.innerHTML = "";
  if (!state.skills.length) {
    skillsList.innerHTML = '<div class="empty-list">No skill profile available yet.</div>';
    return;
  }

  state.skills.forEach((skill) => {
    const key = _skillKey(skill);
    const delta = changedByKey.get(key) || 0;
    const row = document.createElement("div");
    row.className = `skill-row${delta !== 0 ? " is-changed" : ""}`;
    row.innerHTML = `
      <div class="skill-header">
        <div>
          <div class="skill-name">${skill.name}</div>
          <div class="skill-domain">${skill.domain}</div>
        </div>
        <div class="skill-value">Level ${skill.value}/10</div>
      </div>
      ${delta !== 0 ? `<div class="skill-delta">${delta > 0 ? "+" : ""}${delta} this turn</div>` : ""}
    `;
    skillsList.appendChild(row);
  });
}

function setInventory(inventory, inventoryDelta) {
  state.inventory = Array.isArray(inventory) ? inventory : [];
  state.inventoryDelta = Array.isArray(inventoryDelta) ? inventoryDelta : [];
  const deltaByName = new Map(state.inventoryDelta.map((row) => [row.name, row]));

  inventoryList.innerHTML = "";
  if (!state.inventory.length) {
    inventoryList.innerHTML = '<div class="empty-list">No items collected yet.</div>';
    return;
  }

  state.inventory.forEach((item) => {
    const delta = deltaByName.get(item.name);
    const isNew = delta?.change_type === "NEW";
    const isIncreased = delta?.change_type === "INCREASED";
    const row = document.createElement("div");
    row.className = `inventory-row${isNew ? " is-new" : ""}${isIncreased ? " is-increased" : ""}`;

    const badge = isNew
      ? '<div class="inventory-badge">New this turn</div>'
      : isIncreased
      ? '<div class="inventory-badge">Increased this turn</div>'
      : "";

    row.innerHTML = `
      <div class="inventory-header">
        <div class="inventory-name">${item.name}</div>
        <div class="inventory-count">Count ${item.new_count}</div>
      </div>
      ${item.note ? `<div class="inventory-note">${item.note}</div>` : ""}
      ${badge}
    `;
    inventoryList.appendChild(row);
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

async function fetchSimulationMetrics(sessionId) {
  if (!sessionId) return;
  try {
    const response = await fetch(`${API_BASE}/api/simulation-metrics/${sessionId}`);
    if (!response.ok) return;
    const data = await response.json();
    if (data?.simulation_metrics) {
      setSimulationMetrics(data.simulation_metrics);
    }
  } catch (_err) {
    // Keep the UI responsive even if metrics fetch fails.
  }
}

async function loadTitleIdeas() {
  setLoading(
    "Calibrating simulation scenarios...",
    [],
    "Scanning possible realities and preparing your entry points."
  );
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

function isSameAudioSource(audio, source) {
  if (!audio.src) return false;
  try {
    return (
      new URL(audio.src).pathname === new URL(source, window.location.origin).pathname
    );
  } catch (_err) {
    return audio.src.endsWith(source);
  }
}

async function playAudio(audio, path, options = {}) {
  const { restart = false } = options;
  if (!path) return;
  const source = normalizePath(path);
  if (!source) return;
  const sameSource = isSameAudioSource(audio, source);
  if (!sameSource) {
    audio.src = source;
  } else if (restart) {
    audio.currentTime = 0;
  }
  try {
    await audio.play();
  } catch (_err) {
    showToast("Tap anywhere to enable browser audio playback.");
  }
}

async function playSceneAudio(ttsPath, musicPath, forceMusic = false) {
  if (ttsPath) {
    state.currentTtsPath = ttsPath;
  }

  if (state.currentTtsPath && !state.ttsMuted) {
    await playAudio(state.ttsAudio, state.currentTtsPath, { restart: true });
  }

  if (!musicPath) return;

  if (forceMusic || state.currentMusicPath !== musicPath) {
    state.currentMusicPath = musicPath;
    if (!state.musicMuted) {
      await playAudio(state.musicAudio, musicPath, { restart: forceMusic });
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
  state.currentTtsPath = scene.tts_path || null;
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

  setLoading(
    "Initializing your simulation instance...",
    [],
    "Stabilizing world conditions before your first live scene begins."
  );

  try {
    const data = await fetchJson(`${API_BASE}/api/init`, {
      story_text: storyText.trim(),
      game_length_mode: state.gameLength,
    });

    state.sessionId = data.session_id;
    state.turnNumber = 1;
    state.currentMusicPath = null;
    state.transitionHints = extractHintTexts(data.initial_script?.hints);
    sessionIdEl.textContent = state.sessionId.slice(0, 8);
    updateTopStatus();
    setSimulationMetrics(data.simulation_metrics);
    setInventory(data.inventory || [], data.inventory_delta_this_turn || []);
    setSkills(data.skills || data.initial_script?.skills || [], data.skill_delta_this_turn || []);

    renderScene({
      ...data.initial_scene,
      media_type: "image",
      image_path: data.initial_media?.image_path,
      tts_path: data.initial_media?.tts_path,
      music_path: data.initial_media?.music_path,
    });

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

  state.ttsAudio.pause();
  state.ttsAudio.currentTime = 0;
  setLoading(
    "Advancing to the next simulation turn...",
    state.transitionHints.length > 0 ? state.transitionHints : defaultTurnLoadingHints,
    "Hold position while the system resolves your action."
  );

  try {
    const data = await fetchJson(`${API_BASE}/api/turn`, {
      session_id: state.sessionId,
      action: actionText,
    });

    state.turnNumber = data.turn_number || state.turnNumber + 1;
    updateTopStatus();
    setSimulationMetrics(data.simulation_metrics);
    setInventory(data.inventory || [], data.inventory_delta_this_turn || []);
    setSkills(data.skills || [], data.skill_delta_this_turn || []);

    renderScene(data.scene || {});
    state.transitionHints = extractHintTexts(data.hints);

    showScreen(sceneScreen);

    await playSceneAudio(
      data.scene?.tts_path,
      data.scene?.music_action === "CHANGE"
        ? data.scene?.music_path
        : state.currentMusicPath,
      data.scene?.music_action === "CHANGE"
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
  setToggleState(ttsToggle, "TTS", state.ttsMuted);
  persistSettings();
  if (state.ttsMuted) {
    state.ttsAudio.pause();
    state.ttsAudio.currentTime = 0;
    return;
  }

  if (state.currentTtsPath) {
    playAudio(state.ttsAudio, state.currentTtsPath, { restart: true });
  }
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
  resetModal.classList.remove("hidden");
});

metricsToggle.addEventListener("click", async () => {
  if (state.sessionId) {
    await fetchSimulationMetrics(state.sessionId);
  } else {
    renderSimulationMetrics(state.simulationMetrics);
  }
  metricsModal.classList.remove("hidden");
});

closeMetrics.addEventListener("click", () => {
  metricsModal.classList.add("hidden");
});

cancelReset.addEventListener("click", () => {
  resetModal.classList.add("hidden");
});

confirmReset.addEventListener("click", () => {
  resetModal.classList.add("hidden");
  metricsModal.classList.add("hidden");
  state.sessionId = null;
  state.turnNumber = 0;
  state.currentMusicPath = null;
  state.currentTtsPath = null;
  state.transitionHints = [];
  state.inventory = [];
  state.inventoryDelta = [];
  state.skills = [];
  state.skillDelta = [];
  state.simulationMetrics = null;
  setInventory([], []);
  setSkills([], []);
  renderSimulationMetrics(null);
  sessionIdEl.textContent = "--";
  state.ttsAudio.pause();
  state.ttsAudio.removeAttribute("src");
  state.musicAudio.pause();
  state.musicAudio.removeAttribute("src");
  showScreen(titleScreen);
});

loadSettings();
setInventory([], []);
setSkills([], []);
renderSimulationMetrics(null);
loadTitleIdeas();
