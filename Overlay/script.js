const overlayEl = document.querySelector(".overlay");
const statusEl = document.getElementById("status");
const spawnEl = document.getElementById("spawn");
const spawnNameEl = document.getElementById("spawn-name");
const timerEl = document.getElementById("timer");
const resultEl = document.getElementById("result");
const spawnGifEl = document.getElementById("spawn-gif");
const spawnSmokeEl = document.getElementById("spawn-smoke");
const catchAreaEl = document.getElementById("catch-area");
const catchPokemonWrapperEl = document.getElementById("catch-pokemon-wrapper");
const catchPokemonGlowEl = document.getElementById("catch-pokemon-glow");
const catchPokemonGifEl = document.getElementById("catch-pokemon-gif");
const pokeballEl = document.getElementById("pokeball");

let nameToImage = new Map();
let currentSpawnName = "";
let currentCatchEventId = null;
let catchAnimationRunning = false;
let spawnPosition = null; // {x, y} in viewport coordinates where the pokemon appears
const POKEMON_INDEX_URL = (() => {
  const base = new URL(window.location.href);
  return new URL("../data_downloader/pokemon_base_stats.json", base).toString();
})();

function setHidden(el, hidden) {
  if (!el) return;
  if (hidden) {
    el.classList.add("hidden");
    if ([spawnGifEl, spawnSmokeEl, catchPokemonGifEl, catchPokemonGlowEl, pokeballEl].includes(el)) {
      el.style.display = "none";
    }
    if (el === pokeballEl) {
      el.classList.remove("visible");
    }
  } else {
    el.classList.remove("hidden");
    if ([spawnGifEl, spawnSmokeEl, catchPokemonGifEl, catchPokemonGlowEl, pokeballEl].includes(el)) {
      el.style.display = "block";
    }
    if (el === pokeballEl) {
      el.classList.add("visible");
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

function showCatchGifForName(name) {
  const imageFile = nameToImage.get(name);
  if (!imageFile) return false;
  const baseName = imageFile.replace(/\.[^.]+$/, '');
  const gifUrl = `../data_downloader/gif/${encodeURIComponent(baseName)}.gif`;
  catchPokemonGifEl.onload = () => {
    setHidden(catchPokemonGifEl, false);
    catchPokemonGifEl.classList.add("visible");
  };
  catchPokemonGifEl.onerror = () => {
    setHidden(catchPokemonGifEl, true);
    catchPokemonGifEl.classList.remove("visible");
  };
  setHidden(catchPokemonGifEl, true);
  catchPokemonGifEl.classList.remove("visible");
  catchPokemonGifEl.src = "";
  catchPokemonGifEl.src = gifUrl;
  return true;
}

function setCatchVisible(visible) {
  if (visible) {
    catchAreaEl.classList.remove("hidden");
  } else {
    catchAreaEl.classList.add("hidden");
  }
}

function animate(duration, frameFn) {
  return new Promise((resolve) => {
    const start = performance.now();
    function step(now) {
      const elapsed = now - start;
      const progress = Math.min(1, elapsed / duration);
      frameFn(progress);
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        resolve();
      }
    }
    requestAnimationFrame(step);
  });
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function easeOutQuad(t) {
  return t * (2 - t);
}

function setPokeballPosition(x, y, angle = 0) {
  pokeballEl.style.left = `${x}px`;
  pokeballEl.style.top = `${y}px`;
  pokeballEl.style.transform = `translate(-50%, -50%) rotate(${angle}deg)`;
}

function playCatchAnimation(catchData) {
  if (catchAnimationRunning) return;
  catchAnimationRunning = true;
  setCatchVisible(true);
  setHidden(catchPokemonGlowEl, true);
  setHidden(pokeballEl, false);
  pokeballEl.classList.remove("locked", "open", "shake");
  setHidden(catchPokemonGifEl, true);
  catchPokemonGifEl.style.opacity = "1";

  const pokemonName = catchData.pokemon_name || catchData.name || "Pokemon";
  showCatchGifForName(pokemonName);
  catchPokemonWrapperEl.style.transform = "translate(-50%, -50%) scale(1)";

  // Determine throw target: use recorded spawnPosition (corner) if available
  const areaRect = catchAreaEl.getBoundingClientRect();
  // start off-screen to the right
  const startX = window.innerWidth + 80;
  // start a bit below the pokemon so the ball comes up to hit
  const startY = spawnPosition ? (spawnPosition.y + 80) : (areaRect.top + areaRect.height * 0.95);
  const endX = spawnPosition ? spawnPosition.x : (areaRect.left + areaRect.width * 0.5);
  const endY = spawnPosition ? spawnPosition.y : (areaRect.top + areaRect.height * 0.4);
  const controlX = (startX + endX) / 2;
  const controlY = Math.min(startY, endY) - Math.abs(endX - startX) * 0.25; // arc control above

  // If spawnPosition exists, position the pokemon GIF wrapper at that fixed corner
  if (spawnPosition) {
    catchPokemonWrapperEl.style.position = 'fixed';
    catchPokemonWrapperEl.style.left = `${spawnPosition.x}px`;
    catchPokemonWrapperEl.style.top = `${spawnPosition.y}px`;
  } else {
    // keep centered in the catch-area
    catchPokemonWrapperEl.style.position = '';
  }

  const throwDuration = 900;
  setPokeballPosition(startX, startY, 20);

  function bezierPoint(t, p0, p1, p2) {
    return (1 - t) * (1 - t) * p0 + 2 * (1 - t) * t * p1 + t * t * p2;
  }

  return animate(throwDuration, (t) => {
    const eased = easeOutQuad(t);
    const x = bezierPoint(eased, startX, controlX, endX);
    const y = bezierPoint(eased, startY, controlY, endY);
    const angle = lerp(-45, 0, eased);
    setPokeballPosition(x, y, angle);
  }).then(() => impactSequence(catchData));
}

function impactSequence(catchData) {
  setHidden(catchPokemonGlowEl, false);
  catchPokemonGlowEl.style.opacity = "1";
  setTimeout(() => {
    catchPokemonGlowEl.style.opacity = "0";
  }, 130);

  return animate(200, (t) => {
    const scale = lerp(1, 0.1, easeOutQuad(t));
    catchPokemonWrapperEl.style.transform = `translate(-50%, -50%) scale(${scale})`;
  }).then(() => {
    setHidden(catchPokemonGifEl, true);
    return shakeSequence(catchData);
  });
}

function shakeSequence(catchData) {
  pokeballEl.classList.add("shake");
  const shakeDuration = 900;
  return animate(shakeDuration, () => {}).then(() => {
    pokeballEl.classList.remove("shake");
    if (catchData.result === "success") {
      pokeballEl.classList.add("locked");
      return animate(400, (t) => {
        const fade = lerp(1, 0, t);
        pokeballEl.style.opacity = `${fade}`;
      }).then(() => {
        setHidden(pokeballEl, true);
        setCatchVisible(false);
        catchAnimationRunning = false;
      });
    }
    return failSequence();
  });
}

function failSequence() {
  pokeballEl.classList.add("open");
  return animate(200, (t) => {
    const fade = lerp(0, 1, t);
    catchPokemonGifEl.style.opacity = `${fade}`;
  }).then(() => {
    setHidden(catchPokemonGifEl, false);
    catchPokemonGifEl.style.opacity = "1";
    catchPokemonWrapperEl.style.transform = "translate(-50%, -50%) scale(1)";
    return animate(260, (t) => {
      const bounce = Math.sin(t * Math.PI) * 10;
      catchPokemonWrapperEl.style.transform = `translate(-50%, calc(-50% - ${bounce}px)) scale(1)`;
    });
  }).then(() => {
    pokeballEl.classList.remove("open");
    setHidden(pokeballEl, true);
    setCatchVisible(false);
    catchAnimationRunning = false;
  });
}

function handleCatchState(state) {
  const now = Math.floor(Date.now() / 1000);
  const catchInfo = state.catch;
  const activeCatch = catchInfo && now < (catchInfo.expires_at || 0);
  if (!activeCatch) {
    if (!catchAnimationRunning) {
      setCatchVisible(false);
    }
    return false;
  }

  const catchId = `${catchInfo.pokemon_name}-${catchInfo.result}-${catchInfo.expires_at}`;
  if (!catchAnimationRunning && catchId !== currentCatchEventId) {
    currentCatchEventId = catchId;
    playCatchAnimation(catchInfo);
  }
  return true;
}

function playSpawnSequence(name, timer) {
  if (!name) return;
  spawnNameEl.textContent = name;
  timerEl.textContent = timer != null ? timer : "0";
  statusEl.textContent = `A wild ${name} appeared!`;
  setHidden(spawnEl, false);
  showGifForName(name);
  setHidden(overlayEl, false);

  // record the spawn's viewport position (corner) so catch animation targets it
  setTimeout(() => {
    // prefer the gif element position; fallback to smoke or default corner
    let rect = null;
    try {
      rect = spawnGifEl.getBoundingClientRect();
      if (!rect || (rect.width === 0 && rect.height === 0)) {
        rect = spawnSmokeEl.getBoundingClientRect();
      }
    } catch (e) {
      rect = null;
    }
    if (rect && rect.width > 0 && rect.height > 0) {
      spawnPosition = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
      // position the catch wrapper at the spawn corner for consistency
      catchPokemonWrapperEl.style.position = 'fixed';
      catchPokemonWrapperEl.style.left = `${spawnPosition.x}px`;
      catchPokemonWrapperEl.style.top = `${spawnPosition.y}px`;
    } else {
      // default to bottom-right corner where spawn gif normally appears
      spawnPosition = { x: window.innerWidth - 80, y: window.innerHeight - 80 };
      catchPokemonWrapperEl.style.position = 'fixed';
      catchPokemonWrapperEl.style.left = `${spawnPosition.x}px`;
      catchPokemonWrapperEl.style.top = `${spawnPosition.y}px`;
    }
  }, 80);
}

function playDespawnSequence() {
  setHidden(spawnGifEl, true);
  showSmoke(() => {
    statusEl.textContent = "Waiting for a spawn...";
  });
  // clear recorded spawn position
  spawnPosition = null;
  catchPokemonWrapperEl.style.position = '';
}

function updateOverlay(state) {
  const now = Math.floor(Date.now() / 1000);
  if (state && state.catch) {
    const handled = handleCatchState(state);
    if (handled) {
      setHidden(overlayEl, true);
      return;
    }
  }

  const active = state && state.spawn && state.state === "spawn" && now < (state.spawn?.expires_at || 0);
  const spawnName = state?.spawn?.name || "";
  const timerValue = state?.timer != null ? state.timer : 0;

  if (!active) {
    if (currentSpawnName) {
      currentSpawnName = "";
      playDespawnSequence();
    }
    setHidden(overlayEl, true);
    setHidden(spawnEl, true);
    return;
  }

  if (currentSpawnName !== spawnName) {
    currentSpawnName = spawnName;
    playSpawnSequence(spawnName, timerValue);
  } else {
    timerEl.textContent = timerValue;
    setHidden(spawnEl, false);
  }
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
