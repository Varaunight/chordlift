/* ChordLift — main.js */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const state = {
  originalChords: [],  // [{ time, time_seconds, chord, nns }]
  originalKey: "",
  semitones: 0,
  result: null,        // full server result
  pollTimer: null,
};

// ---------------------------------------------------------------------------
// Note transposition table (client-side)
// ---------------------------------------------------------------------------
const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const ENHARMONIC = { Db:"C#", Eb:"D#", Fb:"E", Gb:"F#", Ab:"G#", Bb:"A#", Cb:"B" };

function parseChord(chord) {
  if (!chord) return { root: "", quality: "" };
  let root, quality;
  if (chord.length >= 2 && (chord[1] === "#" || chord[1] === "b")) {
    root = chord.slice(0, 2);
    quality = chord.slice(2);
  } else {
    root = chord.slice(0, 1);
    quality = chord.slice(1);
  }
  root = ENHARMONIC[root] || root;
  return { root, quality };
}

function transposeChord(chord, semitones) {
  const { root, quality } = parseChord(chord);
  const idx = NOTE_NAMES.indexOf(root);
  if (idx === -1) return chord;
  const newRoot = NOTE_NAMES[(idx + semitones + 12) % 12];
  return newRoot + quality;
}

function transposeKey(key, semitones) {
  const isMinor = key.endsWith("m");
  const rootStr = isMinor ? key.slice(0, -1) : key;
  const normalised = ENHARMONIC[rootStr] || rootStr;
  const idx = NOTE_NAMES.indexOf(normalised);
  if (idx === -1) return key;
  const newRoot = NOTE_NAMES[(idx + semitones + 12) % 12];
  return newRoot + (isMinor ? "m" : "");
}

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------
const $ = id => document.getElementById(id);

function show(id) { $(id).style.display = ""; }
function hide(id) { $(id).style.display = "none"; }

function showSection(name) {
  ["upload-section", "progress-section", "results-section", "error-section"].forEach(s => {
    $(s).style.display = s === name ? "" : "none";
  });
}

// ---------------------------------------------------------------------------
// Upload + polling
// ---------------------------------------------------------------------------
function handleFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".mp3")) {
    alert("Please select an MP3 file.");
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    alert("File is too large. Maximum size is 10MB.");
    return;
  }
  $("file-name").textContent = file.name;
  $("file-size").textContent = (file.size / (1024 * 1024)).toFixed(2) + " MB";
  $("file-info").style.display = "flex";
  $("process-btn").disabled = false;
  $("process-btn").dataset.file = "ready";
  window.__selectedFile = file;
}

async function startProcessing() {
  const file = window.__selectedFile;
  if (!file) return;

  showSection("progress-section");

  const formData = new FormData();
  formData.append("file", file);
  formData.append("separate_vocals", $("separate-vocals").checked ? "true" : "false");

  let jobId;
  try {
    const res = await fetch("/upload", { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json();
      showError(err.error || "Upload failed.");
      return;
    }
    const data = await res.json();
    jobId = data.job_id;
  } catch (e) {
    showError("Network error during upload.");
    return;
  }

  // Poll every 3 seconds
  state.pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`/status/${jobId}`);
      const data = await res.json();
      if (data.status === "processing") {
        $("progress-stage").textContent = data.stage || "Processing…";
      } else if (data.status === "complete") {
        clearInterval(state.pollTimer);
        showResults(data.result);
      } else if (data.status === "error") {
        clearInterval(state.pollTimer);
        showError(data.message || "An error occurred during processing.");
      }
    } catch (e) {
      // transient network hiccup — keep polling
    }
  }, 3000);
}

// ---------------------------------------------------------------------------
// Results rendering
// ---------------------------------------------------------------------------
function showResults(result) {
  state.result = result;
  state.originalChords = result.chords;
  state.originalKey = result.key || "";
  state.semitones = 0;

  $("result-title").textContent = result.title || "Unknown Track";
  $("result-artist").textContent = result.artist || "";
  $("result-key").textContent = result.key || "?";
  $("result-bpm").textContent = result.bpm ? Math.round(result.bpm) : "?";
  $("semitone-display").textContent = "0 st";

  renderChordTable();
  showSection("results-section");
}

function renderChordTable() {
  const tbody = $("chord-tbody");
  tbody.innerHTML = "";
  const transposedKey = transposeKey(state.originalKey, state.semitones);
  $("result-key").textContent = transposedKey || "?";

  state.originalChords.forEach(c => {
    const chord = state.semitones !== 0 ? transposeChord(c.chord, state.semitones) : c.chord;
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${c.time}</td><td>${chord}</td><td>${c.nns}</td>`;
    tbody.appendChild(tr);
  });
}

// ---------------------------------------------------------------------------
// Transpose controls
// ---------------------------------------------------------------------------
$("transpose-up").addEventListener("click", () => {
  if (state.semitones >= 6) return;
  state.semitones++;
  updateSemitoneDisplay();
  renderChordTable();
});

$("transpose-down").addEventListener("click", () => {
  if (state.semitones <= -6) return;
  state.semitones--;
  updateSemitoneDisplay();
  renderChordTable();
});

$("transpose-reset").addEventListener("click", () => {
  state.semitones = 0;
  updateSemitoneDisplay();
  renderChordTable();
});

function updateSemitoneDisplay() {
  const n = state.semitones;
  $("semitone-display").textContent = n === 0 ? "0 st" : (n > 0 ? `+${n} st` : `${n} st`);
}

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------
function buildExportPayload() {
  const transposedKey = transposeKey(state.originalKey, state.semitones);
  const chords = state.originalChords.map(c => ({
    ...c,
    chord: state.semitones !== 0 ? transposeChord(c.chord, state.semitones) : c.chord,
  }));
  return {
    title: state.result.title,
    artist: state.result.artist,
    key: transposedKey,
    bpm: state.result.bpm,
    chords,
  };
}

async function doExport(endpoint, mime, ext) {
  const payload = buildExportPayload();
  const filename = (state.result.title || "track").replace(/\s+/g, "-").toLowerCase() + `-chords.${ext}`;
  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) { alert("Export failed."); return; }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

$("export-pdf").addEventListener("click", () => doExport("/export/pdf", "application/pdf", "pdf"));
$("export-txt").addEventListener("click", () => doExport("/export/txt", "text/plain", "txt"));

// ---------------------------------------------------------------------------
// Error + reset
// ---------------------------------------------------------------------------
function showError(msg) {
  $("error-message").textContent = msg;
  showSection("error-section");
}

$("error-retry").addEventListener("click", resetToUpload);
$("start-over").addEventListener("click", resetToUpload);

function resetToUpload() {
  clearInterval(state.pollTimer);
  state.originalChords = [];
  state.result = null;
  state.semitones = 0;
  window.__selectedFile = null;
  $("file-input").value = "";
  $("file-info").style.display = "none";
  $("process-btn").disabled = true;
  showSection("upload-section");
}

// ---------------------------------------------------------------------------
// Drag-and-drop + file input
// ---------------------------------------------------------------------------
const dropZone = $("drop-zone");

dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("drag-over"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
dropZone.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  handleFile(e.dataTransfer.files[0]);
});
dropZone.addEventListener("click", () => $("file-input").click());
dropZone.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") $("file-input").click(); });
$("browse-trigger").addEventListener("click", e => { e.stopPropagation(); $("file-input").click(); });
$("file-input").addEventListener("change", e => handleFile(e.target.files[0]));
$("process-btn").addEventListener("click", startProcessing);

// ---------------------------------------------------------------------------
// Load saved track from history (if injected by server)
// ---------------------------------------------------------------------------
if (window.__SAVED_TRACK__) {
  showResults(window.__SAVED_TRACK__);
}
