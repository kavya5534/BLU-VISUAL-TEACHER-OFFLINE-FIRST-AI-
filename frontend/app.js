// ==========================================================================
// BLU VISUAL TEACHER — MULTILINGUAL, OFFLINE CONTROL CENTER & LOCAL AI BRAIN
// ==========================================================================

const $ = id => document.getElementById(id);

// App State
let current = null;
let sceneIndex = 0;
let playing = false;
let sceneTimer = null;
let currentLanguage = "en";

// Auth State
let currentUser = null;
let authToken = localStorage.getItem("blu_auth_token") || null;

// Course Library State
let allCourses = [];
let activeCategory = "all";

// Anti-Cheat Quiz State
let quizQuestions = [];
let quizCurrentIndex = 0;
let quizScore = 0;
let quizStrikes = 0;
let quizTimeRemaining = 60;
let quizTimerInterval = null;
let quizActive = false;
let quizSelectedOption = null;
let quizProctorEvents = [];

// Improved Flashcards State
let flashcardDeck = [];
let flashcardIndex = 0;
let flashcardsMastered = new Set();
let flashcardBookmarks = new Set();
let flashcardUndoStack = [];
let flashcardBookmarkFilter = false;

// AI Camera State
let cameraStream = null;
let cameraActive = false;
let visionLoopId = null;
let attentionLevel = 88;
let faceDetected = false;

// Audio State
let isAudioPlaying = false;

// Offline Control Center State
let strictOfflineMode = false;

// User Progress Cache
let userProgress = {
  xp: 120,
  level: 1,
  streak_days: 3,
  quizzes_taken: 1,
  badges: ["First Lesson", "Quiz Starter", "Polyglot Explorer"],
  history: []
};

// ==========================================================================
// SOUND UTILITIES (Web Audio API for UI alert beeps)
// ==========================================================================
let audioCtx = null;
function playAlertTone(type = "warning") {
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
    
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);

    if (type === "warning") {
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(580, audioCtx.currentTime);
      osc.frequency.setValueAtTime(880, audioCtx.currentTime + 0.15);
      gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.4);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.4);
    } else if (type === "success") {
      osc.type = "sine";
      osc.frequency.setValueAtTime(523.25, audioCtx.currentTime);
      osc.frequency.setValueAtTime(659.25, audioCtx.currentTime + 0.1);
      gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.35);
    }
  } catch (e) {
    console.warn("AudioContext tone error:", e);
  }
}

// ==========================================================================
// AUTHENTICATION & PROFILE MANAGEMENT
// ==========================================================================
async function checkAuthStatus() {
  if (!authToken) {
    updateAuthUI(null);
    return;
  }
  try {
    const res = await fetch("/api/auth/me", {
      headers: { "Authorization": `Bearer ${authToken}` }
    });
    if (res.ok) {
      const data = await res.json();
      currentUser = data.user;
      updateAuthUI(currentUser);
    } else {
      authToken = null;
      localStorage.removeItem("blu_auth_token");
      updateAuthUI(null);
    }
  } catch (err) {
    console.warn("Auth check error:", err);
    updateAuthUI(null);
  }
}

function updateAuthUI(user) {
  if (user) {
    $("header-user-avatar").textContent = "🎓";
    $("header-user-name").textContent = user.name || user.username;
    $("header-xp").textContent = `${user.xp || 120} XP`;
    $("header-streak").textContent = `${user.streak_days || 3} Days`;
    $("header-level").textContent = `Lvl ${user.level_num || 1}`;

    $("auth-logged-out").style.display = "none";
    $("auth-logged-in").style.display = "block";
    $("prof-name").textContent = user.name || user.username;
    $("prof-username").textContent = `@${user.username}`;
    $("prof-level-badge").textContent = `Level ${user.level_num || 1} Visual Pioneer`;
    $("prof-xp").textContent = `${user.xp || 120} XP`;
    $("prof-streak").textContent = `🔥 ${user.streak_days || 3} Days`;
    $("prof-lang").textContent = `${(user.language || "en").toUpperCase()} Neural`;
    $("prof-quizzes").textContent = user.quizzes_taken || 0;
  } else {
    $("header-user-avatar").textContent = "👤";
    $("header-user-name").textContent = "Sign In";
    $("auth-logged-out").style.display = "block";
    $("auth-logged-in").style.display = "none";
  }
}

$("auth-switch-login").onclick = () => {
  $("auth-switch-login").classList.add("active");
  $("auth-switch-register").classList.remove("active");
  $("login-form").style.display = "block";
  $("register-form").style.display = "none";
  hideAuthAlert();
};
$("auth-switch-register").onclick = () => {
  $("auth-switch-register").classList.add("active");
  $("auth-switch-login").classList.remove("active");
  $("login-form").style.display = "none";
  $("register-form").style.display = "block";
  hideAuthAlert();
};

function showAuthAlert(msg, type = "error") {
  const box = $("auth-alert");
  box.className = `auth-alert ${type}`;
  box.textContent = msg;
  box.style.display = "flex";
}
function hideAuthAlert() {
  $("auth-alert").style.display = "none";
}

$("login-form").addEventListener("submit", async e => {
  e.preventDefault();
  hideAuthAlert();
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username_or_email: $("login-ident").value,
        password: $("login-pw").value
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed");

    authToken = data.token;
    localStorage.setItem("blu_auth_token", authToken);
    currentUser = data.user;
    updateAuthUI(currentUser);
    showAuthAlert("Signed in successfully! Welcome back.", "success");
    loadUserProgress();
    setTimeout(() => switchTab("studio"), 1000);
  } catch (err) {
    showAuthAlert(err.message, "error");
  }
});

$("register-form").addEventListener("submit", async e => {
  e.preventDefault();
  hideAuthAlert();
  try {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: $("reg-name").value,
        username: $("reg-username").value,
        email: $("reg-email").value,
        password: $("reg-pw").value,
        language: $("reg-language").value,
        level: $("reg-level").value
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Registration failed");

    authToken = data.token;
    localStorage.setItem("blu_auth_token", authToken);
    currentUser = data.user;
    updateAuthUI(currentUser);
    showAuthAlert("Account created successfully! Welcome to Blu.", "success");
    loadUserProgress();
    setTimeout(() => switchTab("studio"), 1000);
  } catch (err) {
    showAuthAlert(err.message, "error");
  }
});

$("quick-demo-login-btn").onclick = async () => {
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username_or_email: "demo_learner", password: "password123" })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Demo login failed");

    authToken = data.token;
    localStorage.setItem("blu_auth_token", authToken);
    currentUser = data.user;
    updateAuthUI(currentUser);
    showAuthAlert("Logged in as Demo Explorer!", "success");
    loadUserProgress();
    setTimeout(() => switchTab("studio"), 800);
  } catch (err) {
    showAuthAlert(err.message, "error");
  }
};

$("logout-btn").onclick = () => {
  authToken = null;
  currentUser = null;
  localStorage.removeItem("blu_auth_token");
  updateAuthUI(null);
  loadUserProgress();
};

$("header-user-btn").onclick = () => switchTab("auth");
$("prof-go-studio").onclick = () => switchTab("studio");
$("prof-go-progress").onclick = () => switchTab("progress");

// ==========================================================================
// NEURAL AI AUDIO & SYNTHESIS
// ==========================================================================
async function playNeuralSceneAudio(scene) {
  if (!scene || !scene.narration) return;
  const lang = current?.lesson?.language || $("language").value || "en";
  const gender = $("voice-gender").value || "male";

  $("audio-status-text").textContent = `Synthesizing Neural AI voice (${lang.toUpperCase()})…`;
  $("neural-speak-btn").disabled = true;

  try {
    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: scene.narration,
        language: lang,
        gender: gender
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Audio synthesis error");

    const player = $("neural-audio-player");
    player.src = data.audio_url;
    player.play();
    isAudioPlaying = true;
    $("audio-status-text").textContent = `🎙️ Playing Neural Voice (${data.language.toUpperCase()})`;
    $("neural-speak-btn").textContent = "⏸ Pause Voice";

    player.onended = () => {
      isAudioPlaying = false;
      $("audio-status-text").textContent = `AI Voice Ready (${lang.toUpperCase()})`;
      $("neural-speak-btn").textContent = "▶ Listen AI Voice";
      $("neural-speak-btn").disabled = false;
    };
  } catch (err) {
    console.warn("Neural audio fallback to Web Speech:", err);
    speakWebSpeech(scene.narration, lang);
    $("audio-status-text").textContent = `🎙️ Browser Voice Active (${lang.toUpperCase()})`;
  } finally {
    $("neural-speak-btn").disabled = false;
  }
}

function speakWebSpeech(text, langCode) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  
  const utterance = new SpeechSynthesisUtterance(text);
  const langMap = {
    "en": "en-US", "hi": "hi-IN", "ta": "ta-IN", "te": "te-IN", "kn": "kn-IN",
    "ml": "ml-IN", "bn": "bn-IN", "mr": "mr-IN", "gu": "gu-IN",
    "es": "es-ES", "fr": "fr-FR", "de": "de-DE", "ja": "ja-JP"
  };
  utterance.lang = langMap[langCode] || "en-US";
  const voices = window.speechSynthesis.getVoices();
  const match = voices.find(v => v.lang.startsWith(utterance.lang) || v.lang.startsWith(langCode));
  if (match) utterance.voice = match;

  window.speechSynthesis.speak(utterance);
}

$("neural-speak-btn").onclick = () => {
  const player = $("neural-audio-player");
  if (isAudioPlaying && !player.paused) {
    player.pause();
    isAudioPlaying = false;
    $("neural-speak-btn").textContent = "▶ Listen AI Voice";
  } else if (current?.lesson?.scenes?.[sceneIndex]) {
    playNeuralSceneAudio(current.lesson.scenes[sceneIndex]);
  }
};

// ==========================================================================
// NAVIGATION & TABS
// ==========================================================================
function initNavigation() {
  document.querySelectorAll(".nav-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      if (quizActive && tab.dataset.tab !== "quiz") {
        if (!confirm("⚠️ An active proctored quiz is running. Navigating away will record a strike. Continue?")) {
          return;
        }
        triggerProctorViolation("Navigated to another tab inside application");
      }
      switchTab(tab.dataset.tab);
    });
  });
}

function switchTab(tabId) {
  document.querySelectorAll(".nav-tab").forEach(t => {
    t.classList.toggle("active", t.dataset.tab === tabId);
  });
  document.querySelectorAll(".tab-pane").forEach(pane => {
    pane.classList.toggle("active", pane.id === `tab-${tabId}`);
  });

  if (tabId === "courses") loadCourseLibrary();
  if (tabId === "progress") loadUserProgress();
  if (tabId === "flashcards") renderCurrentFlashcard();
  if (tabId === "auth") checkAuthStatus();
  if (tabId === "control") loadControlCenterStatus();
  if (tabId === "brain") checkBrainStatus();
}

// ==========================================================================
// STUDIO (LESSON GENERATOR & VISUAL STAGE)
// ==========================================================================
$("seconds").addEventListener("input", () => {
  $("seconds-label").textContent = $("seconds").value + "s";
});

function stopPlayback() {
  playing = false;
  if (sceneTimer) clearTimeout(sceneTimer);
  sceneTimer = null;
  $("play").textContent = "▶ Play";
  const player = $("neural-audio-player");
  if (player) player.pause();
  isAudioPlaying = false;
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}

function renderScene() {
  if (!current || !current.lesson?.scenes?.length) return;
  const scenes = current.lesson.scenes;
  const s = scenes[sceneIndex];
  const stage = $("stage");
  stage.innerHTML = "";

  const eyebrow = document.createElement("div");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = `SCENE ${sceneIndex + 1} / ${scenes.length}`;
  stage.appendChild(eyebrow);

  const h2 = document.createElement("h2");
  h2.textContent = s.heading || "Lesson Step";
  stage.appendChild(h2);

  if (s.type === "code_walkthrough" && s.code) {
    const pre = document.createElement("pre");
    pre.className = "code";
    pre.textContent = s.code;
    stage.appendChild(pre);
  } else if (s.type === "diagram" && s.items?.length) {
    const items = document.createElement("div");
    items.className = "diagram-items";
    s.items.forEach((item, i) => {
      const span = document.createElement("span");
      span.textContent = item;
      items.appendChild(span);
      if (i < s.items.length - 1) {
        const arrow = document.createElement("span");
        arrow.textContent = "→";
        arrow.style.background = "transparent";
        arrow.style.border = "0";
        items.appendChild(arrow);
      }
    });
    stage.appendChild(items);
  } else {
    const orb = document.createElement("div");
    orb.className = "orb";
    orb.textContent = "✦";
    stage.appendChild(orb);
  }

  const p = document.createElement("p");
  p.textContent = s.narration;
  stage.appendChild(p);

  $("caption").textContent = s.narration;
  $("scene-count").textContent = `${scenes.length} SCENES`;
  $("language-pill").textContent = `${(current.lesson.language || "en").toUpperCase()} NEURAL`;
  $("progress-fill").style.width = `${((sceneIndex + 1) / scenes.length) * 100}%`;

  $("prev").disabled = sceneIndex === 0;
  $("next").disabled = sceneIndex === scenes.length - 1;
  $("quick-actions").style.display = "flex";
  $("export-json-btn").disabled = false;
  $("save-course-btn").disabled = false;

  playNeuralSceneAudio(s);
}

function nextScene() {
  if (!current) return;
  if (sceneIndex < current.lesson.scenes.length - 1) {
    sceneIndex++;
    renderScene();
  } else {
    stopPlayback();
  }
}

function playPlayback() {
  if (!current) return;
  if (playing) {
    stopPlayback();
    return;
  }
  playing = true;
  $("play").textContent = "Ⅱ Pause";

  function tick() {
    if (!playing) return;
    const s = current.lesson.scenes[sceneIndex];
    const words = (s.narration || "").split(/\s+/).length;
    const ms = Math.max(5000, Math.min(12000, words * 400));

    sceneTimer = setTimeout(() => {
      if (sceneIndex < current.lesson.scenes.length - 1) {
        sceneIndex++;
        renderScene();
        tick();
      } else {
        stopPlayback();
      }
    }, ms);
  }
  tick();
}

$("play").onclick = playPlayback;
$("prev").onclick = () => {
  stopPlayback();
  sceneIndex = Math.max(0, sceneIndex - 1);
  renderScene();
};
$("next").onclick = () => {
  stopPlayback();
  nextScene();
};

$("lesson-form").addEventListener("submit", async e => {
  e.preventDefault();
  stopPlayback();
  $("generate").disabled = true;
  $("status").textContent = "GENERATING AI LESSON…";
  $("message").textContent = "Synthesizing lesson scenes, quizzes, flashcards, and Neural AI voice…";

  try {
    const res = await fetch("/api/lesson", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic: $("topic").value,
        level: $("level").value,
        language: $("language").value,
        seconds: +$("seconds").value
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not generate lesson");

    loadLessonIntoStudio(data);
    $("status").textContent = "LESSON READY";
    $("message").textContent = `Plan: ${data.source}. Audio: ${data.audio_note || "Neural AI Voice ready"}.`;
  } catch (err) {
    $("status").textContent = "ERROR";
    $("message").textContent = err.message;
  } finally {
    $("generate").disabled = false;
  }
});

function loadLessonIntoStudio(data) {
  current = data;
  sceneIndex = 0;
  currentLanguage = data.lesson.language || "en";
  $("language").value = currentLanguage;

  quizQuestions = data.lesson.quizzes || [];
  flashcardDeck = data.lesson.flashcards || [];
  flashcardIndex = 0;
  flashcardsMastered.clear();
  flashcardBookmarks.clear();
  flashcardUndoStack = [];

  renderScene();
  renderCurrentFlashcard();

  ["play", "prev", "next", "export", "export-json-btn", "save-course-btn"].forEach(id => {
    $(id).disabled = false;
  });
  $("quick-actions").style.display = "flex";
}

// MP4 Export & Video Player
$("export").onclick = async () => {
  if (!current) return;
  $("export").disabled = true;
  $("message").textContent = "Rendering 720p MP4 locally using FFmpeg & Neural Audio...";

  try {
    const res = await fetch(`/api/export/${current.id}`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Export failed");

    if (data.video_url) {
      $("mp4-player").src = data.video_url;
      $("video-filename").textContent = `Blu Lesson — ${current.lesson.title || "Video"}`;
      $("toggle-video-view").style.display = "inline-flex";
      showVideoPlayer();
    }

    const a = document.createElement("a");
    a.href = data.download_url;
    a.download = `blu-lesson-${current.id}.mp4`;
    a.click();

    $("message").textContent = `MP4 exported with ${data.audio || "Neural AI Audio"}!`;
  } catch (err) {
    $("message").textContent = `Export error: ${err.message}`;
  } finally {
    $("export").disabled = false;
  }
};

// ============================================================================
// PYTHON LOOP ANIMATED LESSON — Dedicated Load Button
// ============================================================================
async function loadPythonLoopLesson() {
  stopPlayback();
  const btn = $("load-loop-lesson-btn");
  if (btn) btn.disabled = true;
  $("status").textContent = "LOADING PYTHON LOOP LESSON…";
  $("message").textContent = "Fetching the animated Python loop lesson with motion scenes…";

  try {
    const res = await fetch("/api/lesson/python-loop");
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not load loop lesson");

    loadLessonIntoStudio(data);
    $("status").textContent = "ANIMATED LOOP LESSON READY";
    $("message").textContent = "Loaded! Click ▶ Play to animate, or 🎬 Export MP4 for a real moving video.";
    switchTab("studio");
  } catch (err) {
    $("status").textContent = "ERROR";
    $("message").textContent = err.message;
  } finally {
    if (btn) btn.disabled = false;
  }
}

// Wire the button if it exists in the DOM
document.addEventListener("DOMContentLoaded", () => {
  const loopBtn = $("load-loop-lesson-btn");
  if (loopBtn) loopBtn.onclick = loadPythonLoopLesson;
});

function showVideoPlayer() {
  $("stage").style.display = "none";
  $("video-container").style.display = "flex";
  $("toggle-video-view").textContent = "🖼️ Stage Mode";
  $("mp4-player").play().catch(() => {});
}

function showStagePlayer() {
  $("mp4-player").pause();
  $("video-container").style.display = "none";
  $("stage").style.display = "flex";
  $("toggle-video-view").textContent = "🎬 Video Mode";
}

$("toggle-video-view").onclick = () => {
  if ($("video-container").style.display === "none") {
    showVideoPlayer();
  } else {
    showStagePlayer();
  }
};
$("close-video-btn").onclick = showStagePlayer;

// MP4 File Upload
$("mp4-file-input").addEventListener("change", async e => {
  const file = e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  $("message").textContent = `Uploading MP4: ${file.name}…`;
  try {
    const res = await fetch("/api/upload/mp4", {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Video upload failed");

    $("mp4-player").src = data.video_url;
    $("video-filename").textContent = file.name;
    $("toggle-video-view").style.display = "inline-flex";
    showVideoPlayer();
    $("message").textContent = `Video uploaded & ready: ${file.name}`;
  } catch (err) {
    $("message").textContent = `Video upload error: ${err.message}`;
  }
});

// JSON File Import & Export
$("export-json-btn").onclick = () => {
  if (!current?.lesson) return;
  const jsonStr = JSON.stringify(current.lesson, null, 2);
  const blob = new Blob([jsonStr], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `lesson-${current.id || "export"}.json`;
  a.click();
  URL.revokeObjectURL(url);
  $("message").textContent = "Lesson exported as JSON.";
};

$("json-file-input").addEventListener("change", async e => {
  const file = e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  $("message").textContent = `Importing JSON: ${file.name}…`;
  try {
    const res = await fetch("/api/upload/json", {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Invalid JSON structure");

    loadLessonIntoStudio(data);
    $("status").textContent = "JSON LOADED";
    $("message").textContent = `Imported "${data.lesson.title}" successfully!`;
  } catch (err) {
    $("message").textContent = `JSON Import Error: ${err.message}`;
  }
});

$("save-course-btn").onclick = async () => {
  if (!current?.lesson) return;
  try {
    const res = await fetch("/api/courses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(current.lesson)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to save course");
    alert("⭐ Saved to Course Library!");
    loadCourseLibrary();
  } catch (err) {
    alert("Could not save to library: " + err.message);
  }
};

$("jump-to-quiz-btn").onclick = () => {
  switchTab("quiz");
  initQuizScreen();
};
$("jump-to-flashcards-btn").onclick = () => {
  switchTab("flashcards");
  renderCurrentFlashcard();
};

// ==========================================================================
// COURSE LIBRARY MODULE
// ==========================================================================
async function loadCourseLibrary() {
  try {
    const res = await fetch("/api/courses");
    const data = await res.json();
    allCourses = data.courses || [];
    renderCoursesGrid();
  } catch (err) {
    console.error("Error loading courses:", err);
  }
}

function renderCoursesGrid() {
  const grid = $("courses-grid");
  grid.innerHTML = "";

  const query = ($("course-search").value || "").toLowerCase().trim();
  const filtered = allCourses.filter(c => {
    const matchesCat = activeCategory === "all" || c.category === activeCategory;
    const matchesQuery = !query || 
      c.title.toLowerCase().includes(query) || 
      (c.summary && c.summary.toLowerCase().includes(query)) ||
      (c.tags && c.tags.some(t => t.toLowerCase().includes(query)));
    return matchesCat && matchesQuery;
  });

  if (!filtered.length) {
    grid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted);">No courses found matching criteria.</div>`;
    return;
  }

  filtered.forEach(course => {
    const card = document.createElement("div");
    card.className = "course-card";
    
    card.innerHTML = `
      <div class="course-card-top">
        <span class="cat-badge">${course.category || "General"}</span>
        <span class="duration-tag">⏱️ ${course.duration || "45 sec"}</span>
      </div>
      <h3>${course.title}</h3>
      <p>${course.summary || (course.scenes?.[0]?.narration || "").slice(0, 100) + "..."}</p>
      <div class="course-tags">
        ${(course.tags || []).map(t => `<span class="course-tag">#${t}</span>`).join("")}
        <span class="course-tag">🎙️ ${(course.language || "en").toUpperCase()} NEURAL</span>
      </div>
      <div class="course-actions">
        <button class="btn-primary load-course-btn">🎬 Load Lesson</button>
        <button class="btn-secondary take-quiz-btn">📝 Take Quiz</button>
      </div>
    `;

    card.querySelector(".load-course-btn").onclick = () => {
      loadLessonIntoStudio({
        id: course.id || "catalog-course",
        source: "Course Library",
        lesson: course
      });
      switchTab("studio");
    };

    card.querySelector(".take-quiz-btn").onclick = () => {
      loadLessonIntoStudio({
        id: course.id || "catalog-course",
        source: "Course Library",
        lesson: course
      });
      switchTab("quiz");
      initQuizScreen();
    };

    grid.appendChild(card);
  });
}

document.querySelectorAll(".filter-pill").forEach(pill => {
  pill.addEventListener("click", () => {
    document.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
    pill.classList.add("active");
    activeCategory = pill.dataset.category;
    renderCoursesGrid();
  });
});
$("course-search").addEventListener("input", renderCoursesGrid);

// ==========================================================================
// ANTI-CHEAT TIMED QUIZZES
// ==========================================================================
function initQuizScreen() {
  stopQuiz();
  $("quiz-start-screen").style.display = "block";
  $("quiz-question-screen").style.display = "none";
  $("quiz-result-screen").style.display = "none";

  const title = current?.lesson?.title || "Python Loops & Iteration";
  $("quiz-title").textContent = `Quiz: ${title}`;
  $("quiz-topic-tag").textContent = current?.lesson?.category || "Interactive Quiz";
  
  quizStrikes = 0;
  updateStrikesHUD();
  $("quiz-timer").textContent = "01:00";
}

$("start-quiz-btn").onclick = startQuiz;
$("quiz-fullscreen-btn").onclick = toggleFullscreen;

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(() => {});
  } else {
    document.exitFullscreen().catch(() => {});
  }
}

function startQuiz() {
  if (!quizQuestions.length) {
    quizQuestions = [
      {
        question: "What is the primary purpose of a loop in programming?",
        options: ["To delete files", "To repeat instructions for each item", "To slow down the processor", "To display images"],
        answer: 1,
        explanation: "Loops automate repetitive instructions over sequences or ranges."
      },
      {
        question: "What does active recall mean in learning?",
        options: ["Passively reading text", "Testing your own memory before looking at answers", "Listening while sleeping", "Writing in all caps"],
        answer: 1,
        explanation: "Active recall forces retrieval from memory, creating stronger neural connections."
      }
    ];
  }

  quizCurrentIndex = 0;
  quizScore = 0;
  quizStrikes = 0;
  quizTimeRemaining = 60;
  quizProctorEvents = [];
  quizActive = true;

  updateStrikesHUD();
  $("quiz-start-screen").style.display = "none";
  $("quiz-result-screen").style.display = "none";
  $("quiz-question-screen").style.display = "flex";

  renderQuizQuestion();
  startQuizTimer();
  attachAntiCheatListeners();
}

function startQuizTimer() {
  clearInterval(quizTimerInterval);
  updateTimerDisplay();

  quizTimerInterval = setInterval(() => {
    quizTimeRemaining--;
    updateTimerDisplay();

    if (quizTimeRemaining <= 0) {
      clearInterval(quizTimerInterval);
      finishQuiz(true);
    }
  }, 1000);
}

function updateTimerDisplay() {
  const m = Math.floor(Math.max(0, quizTimeRemaining) / 60);
  const s = Math.max(0, quizTimeRemaining) % 60;
  $("quiz-timer").textContent = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  
  if (quizTimeRemaining <= 15) {
    $("timer-box").classList.add("danger");
  } else {
    $("timer-box").classList.remove("danger");
  }
}

function renderQuizQuestion() {
  const q = quizQuestions[quizCurrentIndex];
  if (!q) {
    finishQuiz(false);
    return;
  }

  $("question-number").textContent = `Question ${quizCurrentIndex + 1} of ${quizQuestions.length}`;
  $("question-text").textContent = q.question;
  $("question-feedback").style.display = "none";
  $("submit-answer-btn").style.display = "inline-flex";
  $("submit-answer-btn").disabled = true;
  $("next-question-btn").style.display = "none";
  quizSelectedOption = null;

  const list = $("options-list");
  list.innerHTML = "";

  q.options.forEach((opt, idx) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "option-btn";
    btn.innerHTML = `
      <span class="option-num">${String.fromCharCode(65 + idx)}</span>
      <span>${opt}</span>
    `;
    btn.onclick = () => {
      document.querySelectorAll(".option-btn").forEach(b => b.classList.remove("selected"));
      btn.classList.add("selected");
      quizSelectedOption = idx;
      $("submit-answer-btn").disabled = false;
    };
    list.appendChild(btn);
  });
}

$("submit-answer-btn").onclick = () => {
  if (quizSelectedOption === null) return;
  const q = quizQuestions[quizCurrentIndex];
  const isCorrect = quizSelectedOption === q.answer;

  if (isCorrect) {
    quizScore++;
    playAlertTone("success");
  }

  const optionBtns = document.querySelectorAll(".option-btn");
  optionBtns.forEach((btn, idx) => {
    btn.disabled = true;
    if (idx === q.answer) btn.classList.add("correct");
    else if (idx === quizSelectedOption && !isCorrect) btn.classList.add("incorrect");
  });

  const fb = $("question-feedback");
  fb.className = `question-feedback ${isCorrect ? "correct" : "incorrect"}`;
  $("feedback-icon").textContent = isCorrect ? "✓ Correct!" : "✗ Incorrect";
  $("feedback-text").textContent = q.explanation || (isCorrect ? "Well done!" : "Review the concept above.");
  fb.style.display = "flex";

  $("submit-answer-btn").style.display = "none";
  $("next-question-btn").style.display = "inline-flex";
};

$("next-question-btn").onclick = () => {
  quizCurrentIndex++;
  if (quizCurrentIndex < quizQuestions.length) {
    renderQuizQuestion();
  } else {
    finishQuiz(false);
  }
};

function attachAntiCheatListeners() {
  document.addEventListener("visibilitychange", handleVisibilityChange);
  window.addEventListener("blur", handleWindowBlur);
}

function removeAntiCheatListeners() {
  document.removeEventListener("visibilitychange", handleVisibilityChange);
  window.removeEventListener("blur", handleWindowBlur);
}

function handleVisibilityChange() {
  if (!quizActive) return;
  if (document.hidden) {
    triggerProctorViolation("Tab switch or application minimize detected");
  }
}

function handleWindowBlur() {
  if (!quizActive) return;
  setTimeout(() => {
    if (quizActive && !document.hasFocus()) {
      triggerProctorViolation("Window lost focus (opened another app/window)");
    }
  }, 100);
}

function triggerProctorViolation(reason) {
  if (!quizActive) return;

  quizStrikes++;
  playAlertTone("warning");

  quizTimeRemaining = Math.max(5, quizTimeRemaining - 15);
  updateTimerDisplay();
  updateStrikesHUD();

  const timestamp = new Date().toLocaleTimeString();
  quizProctorEvents.push(`[${timestamp}] Strike ${quizStrikes}: ${reason}`);

  $("modal-strike-title").textContent = `WARNING STRIKE ${quizStrikes} OF 3`;
  $("modal-penalty-text").textContent = `15 seconds have been deducted from your timer. Reason: ${reason}.`;
  $("anti-cheat-modal").style.display = "flex";

  if (quizStrikes >= 3) {
    $("modal-penalty-text").textContent = "3 STRIKES REACHED. Automatic test failure & penalty enforced.";
    setTimeout(() => {
      dismissAntiCheatModal();
      finishQuiz(true);
    }, 2000);
  }
}

function updateStrikesHUD() {
  for (let i = 1; i <= 3; i++) {
    $(`strike-dot-${i}`).classList.toggle("active", quizStrikes >= i);
  }
  $("strikes-text").textContent = `${quizStrikes} / 3 Strikes`;
}

function dismissAntiCheatModal() {
  $("anti-cheat-modal").style.display = "none";
}
$("dismiss-cheat-warning-btn").onclick = dismissAntiCheatModal;

async function finishQuiz(forcedTimeout = false) {
  quizActive = false;
  clearInterval(quizTimerInterval);
  removeAntiCheatListeners();

  const total = quizQuestions.length;
  const pct = Math.round((quizScore / Math.max(1, total)) * 100);

  $("quiz-question-screen").style.display = "none";
  $("quiz-result-screen").style.display = "block";

  $("result-score-percent").textContent = `${pct}%`;
  $("result-detail").textContent = `You answered ${quizScore} out of ${total} questions correctly.`;

  if (forcedTimeout && quizStrikes >= 3) {
    $("result-headline").textContent = "⚠️ Quiz Terminated (Strike Limit Exceeded)";
    $("result-headline").style.color = "var(--accent-rose)";
  } else if (pct >= 80) {
    $("result-headline").textContent = "🎉 Outstanding Performance!";
    $("result-headline").style.color = "var(--accent-mint)";
  } else {
    $("result-headline").textContent = "Study Needed — Review Flashcards";
    $("result-headline").style.color = "var(--accent-amber)";
  }

  $("result-strikes").textContent = quizStrikes === 0 ? "0 (Clean)" : `${quizStrikes} Strikes`;
  $("result-integrity").textContent = quizStrikes === 0 ? "🛡️ Verified Clean (+30 XP)" : "⚠️ Violations Recorded";

  try {
    const headers = { "Content-Type": "application/json" };
    if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

    const res = await fetch("/api/quiz/submit", {
      method: "POST",
      headers: headers,
      body: JSON.stringify({
        lesson_id: current?.id || "quick-quiz",
        lesson_title: current?.lesson?.title || "Lesson Quiz",
        score: quizScore,
        total: total,
        strikes: quizStrikes,
        time_taken: 60 - quizTimeRemaining
      })
    });
    const data = await res.json();
    $("result-xp").textContent = `+${data.earned_xp || quizScore * 50} XP`;
    updateProgressHeader(data.total_xp, data.level);
  } catch (err) {
    $("result-xp").textContent = `+${quizScore * 50} XP`;
  }
}

function stopQuiz() {
  quizActive = false;
  clearInterval(quizTimerInterval);
  removeAntiCheatListeners();
}

$("retake-quiz-btn").onclick = startQuiz;
$("review-flashcards-btn").onclick = () => switchTab("flashcards");
$("back-to-studio-btn").onclick = () => switchTab("studio");

// ==========================================================================
// REQUIREMENT 4: IMPROVED FLASHCARDS DECK & CONTROLS
// ==========================================================================
function getActiveDeck() {
  if (flashcardBookmarkFilter) {
    const bookmarked = flashcardDeck.filter((_, idx) => flashcardBookmarks.has(idx));
    return bookmarked.length ? bookmarked : flashcardDeck;
  }
  return flashcardDeck;
}

function renderCurrentFlashcard() {
  if (!flashcardDeck.length) {
    flashcardDeck = [
      {
        front: "What is an Iteration?",
        back: "A single execution of the loop body for one value in the sequence.",
        tip: "Think of one complete lap around a racetrack."
      },
      {
        front: "range(start, stop, step)",
        back: "Generates integers from start up to stop-1, advancing by step.",
        tip: "Default start is 0, default step is 1."
      },
      {
        front: "Active Recall",
        back: "Retrieving information from memory to strengthen recall pathways.",
        tip: "Test before checking the back!"
      }
    ];
  }

  const deck = getActiveDeck();
  flashcardIndex = Math.max(0, Math.min(deck.length - 1, flashcardIndex));

  const card = $("active-flashcard");
  card.classList.remove("is-flipped");
  hideHintBanner();
  hideAiDrawer();

  const fc = deck[flashcardIndex];
  $("fc-counter").textContent = `Card ${flashcardIndex + 1} of ${deck.length}`;
  $("fc-front-text").textContent = fc.front;
  $("fc-back-text").textContent = fc.back;
  $("fc-tip-text").textContent = fc.tip ? `💡 ${fc.tip}` : "";
  $("fc-hint-text").textContent = fc.tip || "Think about the input data and the logical outcome.";

  const isBookmarked = flashcardBookmarks.has(flashcardIndex);
  $("card-star-badge").style.display = isBookmarked ? "inline-block" : "none";
  $("card-star-badge-back").style.display = isBookmarked ? "inline-block" : "none";
  $("fc-bookmark-icon").textContent = isBookmarked ? "★" : "☆";
  $("fc-bookmark-count").textContent = flashcardBookmarks.size;

  const rate = Math.round((flashcardsMastered.size / Math.max(1, flashcardDeck.length)) * 100);
  $("fc-mastery-rate").textContent = `${rate}% Mastered`;
  $("fc-progress-fill").style.width = `${rate}%`;
}

function flipFlashcard() {
  $("active-flashcard").classList.toggle("is-flipped");
}

$("active-flashcard").onclick = flipFlashcard;
$("fc-flip-btn").onclick = flipFlashcard;

// 1. LISTEN CONTROL: Read question or answer aloud
$("fc-tool-listen").onclick = () => {
  const deck = getActiveDeck();
  const fc = deck[flashcardIndex];
  if (!fc) return;

  const isFlipped = $("active-flashcard").classList.contains("is-flipped");
  const textToRead = isFlipped ? fc.back : fc.front;
  const lang = current?.lesson?.language || "en";

  speakWebSpeech(textToRead, lang);
  playAlertTone("success");
};

// 2. HINT CONTROL: Reveal clue before answer
$("fc-tool-hint").onclick = () => {
  const banner = $("fc-hint-banner");
  if (banner.style.display === "none") {
    banner.style.display = "block";
  } else {
    banner.style.display = "none";
  }
};
function hideHintBanner() {
  $("fc-hint-banner").style.display = "none";
}
$("close-hint-btn").onclick = hideHintBanner;

// 3. EXPLAIN CONTROL: Generate simple explanation using local AI
$("fc-tool-explain").onclick = async () => {
  const deck = getActiveDeck();
  const fc = deck[flashcardIndex];
  if (!fc) return;

  const drawer = $("fc-ai-drawer");
  drawer.style.display = "block";
  $("fc-drawer-title").textContent = `🧠 Local AI: Explaining "${fc.front.slice(0, 30)}..."`;
  $("fc-ai-drawer-content").textContent = "Consulting Local AI Brain...";
  $("fc-ai-cache-chip").style.display = "none";

  try {
    const res = await fetch("/api/ai/brain/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic: fc.front,
        difficulty: "beginner",
        language: current?.lesson?.language || "en"
      })
    });
    const data = await res.json();
    $("fc-ai-drawer-content").textContent = data.result;
    if (data.cached) $("fc-ai-cache-chip").style.display = "inline-block";
  } catch (err) {
    $("fc-ai-drawer-content").textContent = `Explanation: ${fc.back}. Study the relationship between initial condition and logical outcome.`;
  }
};
function hideAiDrawer() {
  $("fc-ai-drawer").style.display = "none";
}
$("close-ai-drawer-btn").onclick = hideAiDrawer;

// 4. KANNADA CONTROL: Show bilingual English + Kannada explanation
$("fc-tool-kannada").onclick = async () => {
  const deck = getActiveDeck();
  const fc = deck[flashcardIndex];
  if (!fc) return;

  const drawer = $("fc-ai-drawer");
  drawer.style.display = "block";
  $("fc-drawer-title").textContent = `🌐 ದ್ವಿಭಾಷಾ ವಿವರಣೆ (English + ಕನ್ನಡ)`;
  $("fc-ai-drawer-content").textContent = "ಸ್ಥಳೀಯ AI ಮೂಲಕ ವಿವರಣೆಯನ್ನು ಪಡೆಯಲಾಗುತ್ತಿದೆ...";

  try {
    const res = await fetch("/api/ai/brain/kannada-bilingual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        concept: fc.front,
        details: fc.back
      })
    });
    const data = await res.json();
    $("fc-ai-drawer-content").textContent = data.kannada_bilingual;
    if (data.cached) $("fc-ai-cache-chip").style.display = "inline-block";
  } catch (err) {
    $("fc-ai-drawer-content").textContent = `🇬🇧 English: ${fc.front}: ${fc.back}\n\n🇮🇳 ಕನ್ನಡ: ${fc.front} ಎಂಬುದು ಪ್ರಮುಖ ಪರಿಕಲ್ಪನೆಯಾಗಿದೆ.\n\n💡 ಸುಳಿವು: ${fc.tip || 'ಹಂತಗಳನ್ನು ಗಮನಿಸಿ'}`;
  }
};

// 5. BOOKMARK CONTROL: Save important cards
$("fc-tool-bookmark").onclick = () => {
  if (flashcardBookmarks.has(flashcardIndex)) {
    flashcardBookmarks.delete(flashcardIndex);
  } else {
    flashcardBookmarks.add(flashcardIndex);
    playAlertTone("success");
  }
  renderCurrentFlashcard();
};

$("fc-filter-bookmarks-btn").onclick = () => {
  flashcardBookmarkFilter = !flashcardBookmarkFilter;
  $("fc-filter-bookmarks-btn").classList.toggle("active", flashcardBookmarkFilter);
  flashcardIndex = 0;
  renderCurrentFlashcard();
};

// 6. SHUFFLE CONTROL: Randomize deck order
$("fc-tool-shuffle").onclick = () => {
  for (let i = flashcardDeck.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [flashcardDeck[i], flashcardDeck[j]] = [flashcardDeck[j], flashcardDeck[i]];
  }
  flashcardIndex = 0;
  playAlertTone("success");
  renderCurrentFlashcard();
};

// 7. UNDO CONTROL: Reverse previous review action
$("fc-tool-undo").onclick = () => {
  if (!flashcardUndoStack.length) {
    alert("Nothing to undo!");
    return;
  }
  const last = flashcardUndoStack.pop();
  flashcardIndex = last.index;
  if (last.mastered) {
    flashcardsMastered.delete(last.index);
  } else {
    flashcardsMastered.add(last.index);
  }
  renderCurrentFlashcard();
};

// 8. EXPORT CONTROL: Save deck as JSON or CSV
$("fc-tool-export").onclick = () => {
  const menu = $("fc-export-menu");
  menu.style.display = menu.style.display === "none" ? "flex" : "none";
};

$("fc-export-json").onclick = () => {
  const str = JSON.stringify(flashcardDeck, null, 2);
  const blob = new Blob([str], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `flashcards-${current?.id || "deck"}.json`;
  a.click();
  $("fc-export-menu").style.display = "none";
};

$("fc-export-csv").onclick = () => {
  let csv = "Front,Back,Tip\n";
  flashcardDeck.forEach(c => {
    const f = (c.front || "").replace(/"/g, '""');
    const b = (c.back || "").replace(/"/g, '""');
    const t = (c.tip || "").replace(/"/g, '""');
    csv += `"${f}","${b}","${t}"\n`;
  });
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `flashcards-${current?.id || "deck"}.csv`;
  a.click();
  $("fc-export-menu").style.display = "none";
};

document.addEventListener("click", e => {
  if (!e.target.closest(".fc-export-dropdown")) {
    const menu = $("fc-export-menu");
    if (menu) menu.style.display = "none";
  }
});

// Standard Next / Prev / Rating
$("fc-prev-btn").onclick = () => {
  const deck = getActiveDeck();
  flashcardIndex = (flashcardIndex - 1 + deck.length) % deck.length;
  renderCurrentFlashcard();
};
$("fc-next-btn").onclick = () => {
  const deck = getActiveDeck();
  flashcardIndex = (flashcardIndex + 1) % deck.length;
  renderCurrentFlashcard();
};
$("fc-again-btn").onclick = () => {
  flashcardUndoStack.push({ index: flashcardIndex, mastered: false });
  flashcardsMastered.delete(flashcardIndex);
  $("fc-next-btn").click();
};
$("fc-mastered-btn").onclick = () => {
  flashcardUndoStack.push({ index: flashcardIndex, mastered: true });
  flashcardsMastered.add(flashcardIndex);
  playAlertTone("success");
  $("fc-next-btn").click();
};

window.addEventListener("keydown", e => {
  if (e.code === "Space" && document.querySelector("#tab-flashcards.active") && e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA") {
    e.preventDefault();
    flipFlashcard();
  }
});

// ==========================================================================
// REQUIREMENT 1: OFFLINE CONTROL CENTER
// ==========================================================================
async function loadControlCenterStatus() {
  try {
    const res = await fetch("/api/control-center/status");
    const data = await res.json();

    // 1. Local AI Status
    const ai = data.local_ai;
    $("sc-ai-badge").textContent = ai.ready ? "Active" : "Offline";
    $("sc-ai-badge").className = `status-badge ${ai.ready ? "online" : "offline"}`;
    $("sc-ai-desc").textContent = ai.details;
    $("sc-ai-models").textContent = `${ai.model_count} Models (${ai.models.join(", ") || "None pulled"})`;

    // 2. Database Status
    const db = data.database;
    $("sc-db-badge").textContent = db.ready ? "Healthy" : "Degraded";
    $("sc-db-badge").className = `status-badge ${db.ready ? "healthy" : "offline"}`;
    $("sc-db-desc").textContent = db.details;
    $("sc-db-records").textContent = `${db.records?.courses || 0} courses, ${db.records?.users || 0} users, ${db.records?.cached_ai_items || 0} AI cache`;

    // 3. Audio Engine Status
    const aud = data.audio_engine;
    $("sc-audio-badge").textContent = aud.ready ? "Ready" : "Degraded";
    $("sc-audio-desc").textContent = aud.details;

    // 4. Internet Status
    const net = data.internet;
    const isStrict = data.strict_offline_mode;
    $("sc-net-badge").textContent = isStrict ? "Strict Offline" : (net.online ? "Connected" : "Offline");
    $("sc-net-badge").className = `status-badge ${net.online && !isStrict ? "online" : "offline"}`;
    $("sc-net-desc").textContent = net.details;
    $("sc-net-mode").textContent = isStrict ? "🔒 100% Strict Offline" : "Hybrid Local-First";

    // Header updates
    $("header-conn-dot").className = `status-indicator-dot ${net.online && !isStrict ? "online" : "offline"}`;
    $("header-conn-text").textContent = isStrict ? "Strict Offline" : (net.online ? "Online" : "Offline");
    $("system-mode-badge").textContent = isStrict ? "🔒 STRICT OFFLINE MODE" : "LOCAL-FIRST · OFFLINE READY";
    $("strict-offline-toggle").checked = isStrict;

    // 5. Storage Indicator
    const st = data.storage;
    $("storage-used-label").innerHTML = `<strong>${st.total_mb} MB</strong> used (${st.percent_used}%)`;
    $("storage-quota-label").textContent = `${st.max_quota_mb} MB Allocation Quota`;
    $("storage-progress-fill").style.width = `${st.percent_used}%`;
    $("sb-val-video").textContent = `${st.breakdown?.video_mb || 0} MB`;
    $("sb-val-audio").textContent = `${st.breakdown?.audio_mb || 0} MB`;
    $("sb-val-uploads").textContent = `${st.breakdown?.uploads_mb || 0} MB`;
    $("sb-val-data").textContent = `${st.breakdown?.data_mb || 0} MB`;

  } catch (err) {
    console.warn("Control center status error:", err);
  }
}

$("refresh-control-btn").onclick = loadControlCenterStatus;

$("strict-offline-toggle").onchange = async () => {
  const enabled = $("strict-offline-toggle").checked;
  try {
    const res = await fetch("/api/control-center/toggle-offline", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled })
    });
    const data = await res.json();
    loadControlCenterStatus();
  } catch (err) {
    console.error("Failed to toggle offline mode:", err);
  }
};

$("clear-cache-btn").onclick = async () => {
  if (!confirm("Clear temporary audio and generated voice files? Courses and accounts will be kept.")) return;
  try {
    const res = await fetch("/api/control-center/clear-cache", { method: "POST" });
    const data = await res.json();
    alert(data.message || "Cache cleared!");
    loadControlCenterStatus();
  } catch (err) {
    alert("Could not clear cache: " + err.message);
  }
};

// ==========================================================================
// REQUIREMENT 2: LOCAL AI BRAIN (OLLAMA INTEGRATION & CACHE)
// ==========================================================================
async function checkBrainStatus() {
  try {
    const res = await fetch("/api/control-center/status");
    const data = await res.json();
    const ai = data.local_ai;
    $("brain-ollama-dot").className = `live-dot ${ai.ready ? "active" : ""}`;
    $("brain-ollama-label").textContent = ai.ready ? `Ollama Active (${ai.model_count} models)` : "Ollama Offline (Heuristic Engine Active)";
  } catch (err) {}
}

// 1. Brain Explain
$("brain-explain-btn").onclick = async () => {
  const topic = $("brain-explain-input").value.trim();
  if (!topic) { alert("Please enter a topic to explain."); return; }

  const box = $("brain-explain-res");
  box.style.display = "block";
  box.textContent = "🧠 Thinking with Local AI Brain...";

  try {
    const res = await fetch("/api/ai/brain/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic,
        difficulty: $("brain-explain-level").value,
        language: $("brain-explain-lang").value
      })
    });
    const data = await res.json();
    const cacheTag = data.cached ? "⚡ Instant from Local Cache (0ms latency, 0 network)\n\n" : "";
    box.textContent = cacheTag + data.result;
  } catch (err) {
    box.textContent = "Could not generate explanation: " + err.message;
  }
};

// 2. Brain Flashcards
$("brain-fc-btn").onclick = async () => {
  const text = $("brain-fc-input").value.trim();
  if (!text) { alert("Please enter notes or a topic."); return; }

  const box = $("brain-fc-res");
  box.style.display = "block";
  box.textContent = "🗂️ Generating study flashcards...";

  try {
    const res = await fetch("/api/ai/brain/flashcards", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, count: 4, language: "en" })
    });
    const data = await res.json();
    const cards = data.flashcards || [];

    box.innerHTML = `
      <div style="margin-bottom:8px; font-weight:700; color:var(--accent-mint)">
        ${data.cached ? "⚡ Instant from Local Cache" : "Generated by Local AI"}: ${cards.length} Flashcards Created!
      </div>
      <div style="font-size:12px; margin-bottom:12px;">
        ${cards.map((c, i) => `<b>${i+1}. ${c.front}</b> → ${c.back}<br>`).join("")}
      </div>
      <button class="btn-primary btn-sm" id="load-brain-fc-btn">📥 Load into Flashcards Tab</button>
    `;

    $("load-brain-fc-btn").onclick = () => {
      flashcardDeck = cards;
      flashcardIndex = 0;
      switchTab("flashcards");
      renderCurrentFlashcard();
    };
  } catch (err) {
    box.textContent = "Error: " + err.message;
  }
};

// 3. Brain Quiz
$("brain-quiz-btn").onclick = async () => {
  const text = $("brain-quiz-input").value.trim();
  if (!text) { alert("Please enter chapter notes or a topic."); return; }

  const box = $("brain-quiz-res");
  box.style.display = "block";
  box.textContent = "📝 Formulating practice questions...";

  try {
    const res = await fetch("/api/ai/brain/quiz", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, count: 3, language: "en" })
    });
    const data = await res.json();
    const questions = data.questions || [];

    box.innerHTML = `
      <div style="margin-bottom:8px; font-weight:700; color:var(--accent-mint)">
        ${data.cached ? "⚡ Instant from Local Cache" : "Generated by Local AI"}: ${questions.length} Practice Questions Ready!
      </div>
      <div style="font-size:12px; margin-bottom:12px;">
        ${questions.map((q, i) => `<b>Q${i+1}: ${q.question}</b> (${q.options.length} options)<br>`).join("")}
      </div>
      <button class="btn-primary btn-sm" id="load-brain-quiz-btn">🎯 Start Timed Practice Quiz</button>
    `;

    $("load-brain-quiz-btn").onclick = () => {
      quizQuestions = questions;
      switchTab("quiz");
      initQuizScreen();
    };
  } catch (err) {
    box.textContent = "Error: " + err.message;
  }
};

// 4. Brain Summarize
$("brain-sum-btn").onclick = async () => {
  const notes = $("brain-sum-input").value.trim();
  if (!notes) { alert("Please enter study notes to summarize."); return; }

  const box = $("brain-sum-res");
  box.style.display = "block";
  box.textContent = "📑 Synthesizing executive study notes...";

  try {
    const res = await fetch("/api/ai/brain/summarize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes, language: "en" })
    });
    const data = await res.json();
    box.textContent = (data.cached ? "⚡ Instant from Local Cache\n\n" : "") + data.summary;
  } catch (err) {
    box.textContent = "Error: " + err.message;
  }
};

// ==========================================================================
// REQUIREMENT 3: OFFLINE CAMERA & PDF TUTOR
// ==========================================================================
$("tutor-toggle-pdf").onclick = () => {
  $("tutor-toggle-pdf").classList.add("active");
  $("tutor-toggle-cam").classList.remove("active");
  $("tutor-pdf-box").style.display = "block";
  $("tutor-cam-box").style.display = "none";
};

$("tutor-toggle-cam").onclick = () => {
  $("tutor-toggle-cam").classList.add("active");
  $("tutor-toggle-pdf").classList.remove("active");
  $("tutor-pdf-box").style.display = "none";
  $("tutor-cam-box").style.display = "block";
};

// PDF Upload & Extraction
$("tutor-pdf-file").addEventListener("change", async e => {
  const file = e.target.files[0];
  if (!file) return;

  $("extracted-meta-badge").textContent = `Extracting ${file.name}…`;
  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/ocr/extract-pdf", {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Extraction failed");

    $("tutor-extracted-text").value = data.text;
    $("extracted-meta-badge").textContent = `${data.word_count} Words (${data.pages_read} Pages)`;
    $("tutor-status-badge").textContent = "Text Extracted";

    renderTutorOutputPreview(data.text);
  } catch (err) {
    alert("PDF Extraction error: " + err.message);
  }
});

// Image Upload & OCR
$("tutor-img-file").addEventListener("change", async e => {
  const file = e.target.files[0];
  if (!file) return;

  $("extracted-meta-badge").textContent = "Running Local OCR…";
  
  // Try client-side Tesseract.js if loaded
  if (typeof Tesseract !== "undefined") {
    try {
      const { data: { text } } = await Tesseract.recognize(file, 'eng');
      if (text && text.trim().length > 10) {
        $("tutor-extracted-text").value = text;
        $("extracted-meta-badge").textContent = `${text.split(/\s+/).length} Words (Client OCR)`;
        renderTutorOutputPreview(text);
        return;
      }
    } catch (e) {
      console.warn("Client OCR fallback to backend:", e);
    }
  }

  // Backend vision fallback
  const formData = new FormData();
  formData.append("file", file);
  try {
    const res = await fetch("/api/ocr/extract-image", { method: "POST", body: formData });
    const data = await res.json();
    $("tutor-extracted-text").value = data.text;
    $("extracted-meta-badge").textContent = "Extracted from Image";
    renderTutorOutputPreview(data.text);
  } catch (err) {
    alert("Image OCR error: " + err.message);
  }
});

// Snapshot from Webcam for Tutor
$("tutor-snap-webcam-btn").onclick = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    const video = document.createElement("video");
    video.srcObject = stream;
    await video.play();

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0);

    stream.getTracks().forEach(t => t.stop());

    canvas.toBlob(async blob => {
      const file = new File([blob], "textbook_snap.png", { type: "image/png" });
      const dt = new DataTransfer();
      dt.items.add(file);
      $("tutor-img-file").files = dt.files;
      $("tutor-img-file").dispatchEvent(new Event("change"));
    });
  } catch (err) {
    alert("Could not access camera for textbook snapshot: " + err.message);
  }
};

function renderTutorOutputPreview(text) {
  const container = $("tutor-output-container");
  container.innerHTML = `
    <div style="background:#0c1729; border:1px solid #223758; border-radius:10px; padding:16px; margin-bottom:14px;">
      <h4 style="color:#6ee7b7; margin-bottom:6px;">📖 Content Ready for Study Conversion</h4>
      <p style="font-size:13px; color:#cbd5e1; line-height:1.5;">${text.slice(0, 300)}...</p>
    </div>
    <p style="font-size:12px; color:var(--text-dim);">Use the buttons on the left to convert this into Flashcards, Quizzes, or Summary.</p>
  `;
}

// Convert Buttons
$("tutor-to-fc-btn").onclick = async () => {
  const text = $("tutor-extracted-text").value.trim();
  if (!text) { alert("Please extract or paste textbook text first."); return; }

  $("tutor-status-badge").textContent = "Creating Cards…";
  try {
    const res = await fetch("/api/ocr/convert-to-study", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, aids: ["flashcards"] })
    });
    const data = await res.json();
    if (data.flashcards?.length) {
      flashcardDeck = data.flashcards;
      flashcardIndex = 0;
      switchTab("flashcards");
      renderCurrentFlashcard();
    }
  } catch (err) {
    alert("Error: " + err.message);
  }
};

$("tutor-to-quiz-btn").onclick = async () => {
  const text = $("tutor-extracted-text").value.trim();
  if (!text) { alert("Please extract or paste textbook text first."); return; }

  $("tutor-status-badge").textContent = "Formulating Quiz…";
  try {
    const res = await fetch("/api/ocr/convert-to-study", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, aids: ["quiz"] })
    });
    const data = await res.json();
    if (data.quiz?.length) {
      quizQuestions = data.quiz;
      switchTab("quiz");
      initQuizScreen();
    }
  } catch (err) {
    alert("Error: " + err.message);
  }
};

$("tutor-to-summary-btn").onclick = async () => {
  const text = $("tutor-extracted-text").value.trim();
  if (!text) { alert("Please extract or paste textbook text first."); return; }

  $("tutor-status-badge").textContent = "Summarizing…";
  try {
    const res = await fetch("/api/ocr/convert-to-study", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, aids: ["summary"] })
    });
    const data = await res.json();
    $("tutor-output-container").innerHTML = `
      <div style="background:#0c1729; border:1px solid #223758; border-radius:10px; padding:18px;">
        <h4 style="color:#facc15; margin-bottom:10px;">📑 Textbook Chapter Summary</h4>
        <div style="font-size:13px; line-height:1.6; white-space:pre-wrap; color:#e2e8f0;">${data.summary}</div>
      </div>
    `;
    $("tutor-status-badge").textContent = "Summary Ready";
  } catch (err) {
    alert("Error: " + err.message);
  }
};

// ==========================================================================
// AI CAMERA TUTOR & REAL-TIME VISION PROCTOR
// ==========================================================================
$("toggle-cam-btn").onclick = toggleCamera;

async function toggleCamera() {
  if (cameraActive) {
    stopCamera();
  } else {
    await startCamera();
  }
}

async function startCamera() {
  try {
    const video = $("webcam-video");
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480, facingMode: "user" },
      audio: false
    });
    video.srcObject = cameraStream;
    video.play();

    cameraActive = true;
    $("cam-live-dot").classList.add("active");
    $("cam-status-label").textContent = "Camera Live (AI Tracking)";
    $("toggle-cam-btn").textContent = "Turn Camera Off ⏹️";
    $("snapshot-btn").disabled = false;
    $("cam-idle-overlay").style.display = "none";

    logCameraActivity("Camera & AI vision pipeline active.");
    startVisionLoop();
  } catch (err) {
    alert("Camera permission denied or camera not available: " + err.message);
  }
}

function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach(t => t.stop());
    cameraStream = null;
  }
  if (visionLoopId) cancelAnimationFrame(visionLoopId);

  cameraActive = false;
  $("cam-live-dot").classList.remove("active");
  $("cam-status-label").textContent = "Camera Idle";
  $("toggle-cam-btn").textContent = "Turn Camera On 📹";
  $("snapshot-btn").disabled = true;
  $("cam-idle-overlay").style.display = "flex";
  $("face-box").style.display = "none";
}

function startVisionLoop() {
  const video = $("webcam-video");
  const canvas = $("vision-canvas");
  const ctx = canvas.getContext("2d", { willReadFrequently: true });

  let frameCount = 0;

  function loop() {
    if (!cameraActive) return;

    if (video.readyState === video.HAVE_ENOUGH_DATA) {
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      frameCount++;
      if (frameCount % 5 === 0) {
        analyzeFrame(ctx, canvas.width, canvas.height);
      }
    }
    visionLoopId = requestAnimationFrame(loop);
  }
  visionLoopId = requestAnimationFrame(loop);
}

function analyzeFrame(ctx, w, h) {
  const imgData = ctx.getImageData(0, 0, w, h);
  const data = imgData.data;

  let skinPixels = 0;
  let totalBrightness = 0;
  let sumX = 0;
  let sumY = 0;

  const step = 4;
  const totalSampled = (w * h) / step;

  for (let i = 0; i < data.length; i += 4 * step) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];

    const brightness = (r + g + b) / 3;
    totalBrightness += brightness;

    if (r > 80 && g > 35 && b > 20 && (r - g) > 10 && r > b) {
      skinPixels++;
      const pixelIndex = i / 4;
      const x = pixelIndex % w;
      const y = Math.floor(pixelIndex / w);
      sumX += x;
      sumY += y;
    }
  }

  const avgBrightness = totalBrightness / totalSampled;
  const skinRatio = skinPixels / totalSampled;
  faceDetected = skinRatio > 0.04 && skinRatio < 0.65;

  const lightBadge = $("badge-lighting");
  const lightText = $("status-lighting-text");
  if (avgBrightness < 45) {
    lightText.textContent = "Too Dark";
    lightBadge.querySelector(".tb-status").className = "tb-status warning";
  } else {
    lightText.textContent = "Optimal";
    lightBadge.querySelector(".tb-status").className = "tb-status good";
  }

  const faceBox = $("face-box");
  const faceText = $("status-face-text");
  const gazeText = $("status-gaze-text");
  const postureText = $("status-posture-text");

  if (faceDetected) {
    const centerX = sumX / skinPixels;
    const centerY = sumY / skinPixels;

    const boxW = Math.max(120, Math.min(260, skinRatio * 500));
    const boxH = boxW * 1.25;
    const left = (centerX - boxW / 2) / w * 100;
    const top = (centerY - boxH / 2) / h * 100;

    faceBox.style.display = "block";
    faceBox.style.left = `${Math.max(5, Math.min(75, left))}%`;
    faceBox.style.top = `${Math.max(5, Math.min(65, top))}%`;
    faceBox.style.width = `${boxW}px`;
    faceBox.style.height = `${boxH}px`;

    faceText.textContent = "Detected";
    $("badge-face").querySelector(".tb-status").className = "tb-status good";

    const isCentered = Math.abs(centerX - w / 2) < w * 0.22;
    if (isCentered) {
      gazeText.textContent = "Centered";
      $("badge-gaze").querySelector(".tb-status").className = "tb-status good";
      attentionLevel = Math.min(98, attentionLevel + 1);
    } else {
      gazeText.textContent = "Looking Away";
      $("badge-gaze").querySelector(".tb-status").className = "tb-status warning";
      attentionLevel = Math.max(45, attentionLevel - 2);

      if (quizActive && $("proctor-sync-toggle").checked && Math.random() < 0.05) {
        logCameraActivity("⚠️ Student gaze averted during quiz.");
      }
    }

    if (centerY > h * 0.7) {
      postureText.textContent = "Head Down";
      $("badge-posture").querySelector(".tb-status").className = "tb-status warning";
    } else {
      postureText.textContent = "Upright";
      $("badge-posture").querySelector(".tb-status").className = "tb-status good";
    }

  } else {
    faceBox.style.display = "none";
    faceText.textContent = "Missing";
    $("badge-face").querySelector(".tb-status").className = "tb-status bad";
    gazeText.textContent = "No Face";
    $("badge-gaze").querySelector(".tb-status").className = "tb-status bad";
    attentionLevel = Math.max(20, attentionLevel - 3);

    if (quizActive && $("proctor-sync-toggle").checked && Math.random() < 0.05) {
      logCameraActivity("⚠️ Face not detected in camera frame during assessment!");
    }
  }

  $("metric-attention").textContent = `${attentionLevel}%`;
  $("attention-fill").style.width = `${attentionLevel}%`;
  if (attentionLevel > 75) {
    $("attention-status-text").textContent = "🟢 High Focus: Direct engagement with lesson.";
  } else if (attentionLevel > 50) {
    $("attention-status-text").textContent = "🟡 Moderate Focus: Occasional glances away.";
  } else {
    $("attention-status-text").textContent = "🔴 Low Attention: Please look at the screen.";
  }
}

function logCameraActivity(msg) {
  const log = $("camera-log");
  const li = document.createElement("li");
  const time = new Date().toTimeString().slice(0, 5);
  li.innerHTML = `<span class="log-time">${time}</span> ${msg}`;
  log.prepend(li);
  if (log.children.length > 8) log.removeChild(log.lastChild);
}

$("snapshot-btn").onclick = () => {
  if (!cameraActive) return;
  const canvas = $("vision-canvas");
  
  const snapCanvas = document.createElement("canvas");
  snapCanvas.width = canvas.width;
  snapCanvas.height = canvas.height;
  const sCtx = snapCanvas.getContext("2d");

  sCtx.translate(snapCanvas.width, 0);
  sCtx.scale(-1, 1);
  sCtx.drawImage(canvas, 0, 0);
  sCtx.setTransform(1, 0, 0, 1, 0, 0);

  sCtx.fillStyle = "rgba(15, 23, 42, 0.75)";
  sCtx.fillRect(16, snapCanvas.height - 64, snapCanvas.width - 32, 48);
  sCtx.font = "bold 16px sans-serif";
  sCtx.fillStyle = "#38bdf8";
  sCtx.fillText("BLU VISUAL TEACHER — STUDY SNAPSHOT", 28, snapCanvas.height - 34);
  sCtx.font = "12px sans-serif";
  sCtx.fillStyle = "#cbd5e1";
  sCtx.fillText(`Topic: ${current?.lesson?.title || "Python Loop"} · Focus: ${attentionLevel}%`, 28, snapCanvas.height - 18);

  const url = snapCanvas.toDataURL("image/png");
  const a = document.createElement("a");
  a.href = url;
  a.download = `blu-study-snapshot-${Date.now()}.png`;
  a.click();
  logCameraActivity("📸 Study snapshot saved to your computer!");
};

// ==========================================================================
// PROGRESS & ACHIEVEMENTS DASHBOARD
// ==========================================================================
async function loadUserProgress() {
  try {
    const headers = {};
    if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

    const res = await fetch("/api/progress", { headers });
    const data = await res.json();
    userProgress = data;

    $("dash-xp").textContent = data.xp || 120;
    $("dash-streak").textContent = `${data.streak_days || 3} Days`;
    $("dash-level").textContent = `Level ${data.level_num || data.level || 1}`;
    $("dash-quizzes").textContent = data.quizzes_taken || 1;

    updateProgressHeader(data.xp, data.level_num || data.level);

    const level = data.level_num || data.level || 1;
    const nextLevelXP = level * 100;
    const currentLevelBaseXP = (level - 1) * 100;
    const progressXP = (data.xp || 120) - currentLevelBaseXP;
    const pct = Math.min(100, Math.max(0, Math.round((progressXP / 100) * 100)));
    $("level-xp-text").textContent = `${data.xp || 120} / ${nextLevelXP} XP`;
    $("level-progress-fill").style.width = `${pct}%`;

    renderHistoryTable(data.history || []);
  } catch (err) {
    console.warn("Could not load user progress:", err);
  }
}

function updateProgressHeader(xp, level) {
  $("header-xp").textContent = `${xp || 120} XP`;
  $("header-level").textContent = `Lvl ${level || 1}`;
}

function renderHistoryTable(history) {
  const tbody = $("history-table-body");
  tbody.innerHTML = "";

  if (!history.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color: var(--text-muted);">No assessments recorded yet. Take your first quiz!</td></tr>`;
    return;
  }

  history.slice().reverse().forEach(h => {
    const tr = document.createElement("tr");
    const isClean = h.strikes === 0;
    const scoreClass = h.percent >= 80 ? "good" : (h.percent >= 50 ? "average" : "poor");

    tr.innerHTML = `
      <td>${h.lesson_title || "General Lesson"}</td>
      <td><span class="score-pill ${scoreClass}">${h.percent}%</span></td>
      <td>${h.strikes} Strikes</td>
      <td><span class="${isClean ? "status-clean" : ""}">${isClean ? "🛡️ Verified Clean" : "⚠️ Tab Switches"}</span></td>
      <td>+${h.earned_xp || 50} XP</td>
    `;
    tbody.appendChild(tr);
  });
}

// ==========================================================================
// INITIALIZATION
// ==========================================================================
window.addEventListener("DOMContentLoaded", () => {
  initNavigation();
  checkAuthStatus();
  loadControlCenterStatus();
  loadCourseLibrary();
  loadUserProgress();

  fetch("/api/lesson", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      topic: "How does a Python loop work?",
      level: "beginner",
      language: "en",
      seconds: 45
    })
  })
    .then(r => r.json())
    .then(data => {
      loadLessonIntoStudio(data);
    })
    .catch(err => {
      console.warn("Initial load fallback:", err);
    });
});
