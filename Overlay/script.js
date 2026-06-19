const overlayEl = document.querySelector(".overlay");
const statusEl = document.getElementById("status");
const spawnEl = document.getElementById("spawn");
const spawnNameEl = document.getElementById("spawn-name");
const timerEl = document.getElementById("timer");
const resultEl = document.getElementById("result");
const spawnGifEl = document.getElementById("spawn-gif");
const spawnSmokeEl = document.getElementById("spawn-smoke");

let nameToImage = new Map();
let currentSpawnName = "";
const POKEMON_INDEX_URL = (() => {
  const base = new URL(window.location.href);
  return new URL("../data_downloader/pokemon_base_stats.json", base).toString();
})();

function setHidden(el, hidden) {
  if (hidden) {
    el.classList.add("hidden");
    if (el === spawnGifEl || el === spawnSmokeEl) {
      el.style.display = "none";
    }
  } else {
    el.classList.remove("hidden");
    if (el === spawnGifEl || el === spawnSmokeEl) {
      el.style.display = "block";
    }
  }
}

async function loadPokemonIndex() {
  try {
    const response = await fetch(`${POKEMON_INDEX_URL}?ts=${Date.now()}`);
    if (!response.ok) return;
    const data = await response.json();
    if (data && data.pokemon) {
      for (const key of Object.keys(data.pokemon)) {
        const entry = data.pokemon[key];
        if (entry && entry.name && entry.image_file) {
          nameToImage.set(entry.name, entry.image_file);
        }
      }
    }
  } catch (err) {
    console.warn("Failed to load pokemon index:", err);
  }
}

loadPokemonIndex();
// refresh mapping occasionally in case files change
setInterval(loadPokemonIndex, 60 * 1000);

function showSmoke(callback) {
  setHidden(spawnSmokeEl, false);
  spawnSmokeEl.style.display = "block";
  spawnSmokeEl.classList.remove("show");
  void spawnSmokeEl.offsetWidth;
  spawnSmokeEl.classList.add("show");

  const onAnimationEnd = () => {
    spawnSmokeEl.classList.remove("show");
    setHidden(spawnSmokeEl, true);
    spawnSmokeEl.style.display = "none";
    spawnSmokeEl.removeEventListener("animationend", onAnimationEnd);
    if (typeof callback === "function") {
      callback();
    }
  };

  spawnSmokeEl.addEventListener("animationend", onAnimationEnd);
}

function showGifForName(name) {
  const imageFile = nameToImage.get(name);
  if (!imageFile) return false;
  const baseName = imageFile.replace(/\.[^.]+$/, '');
  const gifUrl = `../data_downloader/gif/${encodeURIComponent(baseName)}.gif`;
  spawnGifEl.onload = () => {
    setHidden(spawnGifEl, false);
    spawnGifEl.classList.add("visible");
  };
  spawnGifEl.onerror = () => {
    setHidden(spawnGifEl, true);
    spawnGifEl.classList.remove("visible");
  };
  setHidden(spawnGifEl, true);
  spawnGifEl.classList.remove("visible");
  spawnGifEl.src = "";
  spawnGifEl.src = gifUrl;
  return true;
}

function playSpawnSequence(name) {
  setHidden(spawnGifEl, true);
  showSmoke(() => {
    showGifForName(name);
  });
}

function playDespawnSequence() {
  setHidden(spawnGifEl, true);
  showSmoke();
}

function updateOverlay(state) {
  const now = Math.floor(Date.now() / 1000);
  const active = state && state.state === "spawn" && state.spawn && now < (state.spawn?.expires_at || 0);
  const spawnName = state?.spawn?.name || "";

  if (!active) {
    if (currentSpawnName) {
      playDespawnSequence();
      currentSpawnName = "";
    }
    setHidden(overlayEl, true);
    return;
  }

  if (currentSpawnName !== spawnName) {
    currentSpawnName = spawnName;
    playSpawnSequence(spawnName);
  } else {
    setHidden(spawnGifEl, false);
  }

  setHidden(overlayEl, true);
}

function buildOverlayUrl() {
  const base = new URL(window.location.href);
  return new URL("../Data/overlay_state.json", base).toString();
}

async function poll() {
  try {
    const url = buildOverlayUrl();
    const response = await fetch(`${url}?ts=${Date.now()}`);
    if (!response.ok) {
      statusEl.textContent = "Overlay: failed to read overlay_state.json";
      return;
    }
    const data = await response.json();
    updateOverlay(data);
  } catch (err) {
    statusEl.textContent = "Overlay: cannot access local JSON (check OBS local file access)";
  }
}

setInterval(poll, 1000);
poll();
