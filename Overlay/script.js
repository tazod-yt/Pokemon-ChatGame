const spawnGifEl   = document.getElementById('spawn-gif');
const spawnSmokeEl = document.getElementById('spawn-smoke');
const pokeballEl   = document.getElementById('pokeball');

let nameToImage         = new Map();
let currentSpawnName    = '';
let currentCatchEventId = null;
let catchAnimationRunning = false;

const POKEMON_INDEX_URL = (() => {
  const base = new URL(window.location.href);
  return new URL('../data_downloader/pokemon_base_stats.json', base).toString();
})();

// ── Helpers ─────────────────────────────────────────────────

function setHidden(el, hidden) {
  if (!el) return;
  if (hidden) {
    el.classList.add('hidden');
    el.style.display = 'none';
  } else {
    el.classList.remove('hidden');
    el.style.display = 'block';
  }
}

function animate(duration, frameFn) {
  return new Promise((resolve) => {
    const start = performance.now();
    function step(now) {
      const progress = Math.min(1, (now - start) / duration);
      frameFn(progress);
      if (progress < 1) requestAnimationFrame(step);
      else resolve();
    }
    requestAnimationFrame(step);
  });
}

function lerp(a, b, t)   { return a + (b - a) * t; }
function easeOut(t)       { return t * (2 - t); }

// ── Pokemon index ────────────────────────────────────────────

async function loadPokemonIndex() {
  try {
    const res = await fetch(\?ts=\);
    if (!res.ok) return;
    const data = await res.json();
    if (data && data.pokemon) {
      for (const key of Object.keys(data.pokemon)) {
        const e = data.pokemon[key];
        if (e && e.name && e.image_file) nameToImage.set(e.name, e.image_file);
      }
    }
  } catch (err) { console.warn('Failed to load pokemon index:', err); }
}

loadPokemonIndex();
setInterval(loadPokemonIndex, 60_000);

// ── Smoke effect ─────────────────────────────────────────────

function showSmoke(onDone) {
  setHidden(spawnSmokeEl, false);
  spawnSmokeEl.classList.remove('show');
  void spawnSmokeEl.offsetWidth;
  spawnSmokeEl.classList.add('show');
  const done = () => {
    spawnSmokeEl.classList.remove('show');
    setHidden(spawnSmokeEl, true);
    spawnSmokeEl.removeEventListener('animationend', done);
    if (typeof onDone === 'function') onDone();
  };
  spawnSmokeEl.addEventListener('animationend', done);
}

// ── Spawn GIF ────────────────────────────────────────────────

function showGifForName(name) {
  const imageFile = nameToImage.get(name);
  if (!imageFile) return;
  const base = imageFile.replace(/\.[^.]+$/, '');
  const url  = ../data_downloader/gif/\.gif;
  spawnGifEl.onload  = () => { setHidden(spawnGifEl, false); };
  spawnGifEl.onerror = () => { setHidden(spawnGifEl, true); };
  setHidden(spawnGifEl, true);
  spawnGifEl.src = '';
  spawnGifEl.src = url;
}

// ── Pokeball helpers ─────────────────────────────────────────

// Returns center of the spawn gif in VIEWPORT coordinates.
// The gif is always at fixed bottom-right: bottom:38px right:48px width:83px
function getPokemonCenter() {
  const rect = spawnGifEl.getBoundingClientRect();
  if (rect.width > 0 && rect.height > 0) {
    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
  }
  // Fallback: approximate (gif is 83px wide, ~80px tall)
  return { x: window.innerWidth - 48 - 41, y: window.innerHeight - 38 - 40 };
}

// x, y are VIEWPORT coordinates (pokeball is position:fixed)
function setPokeballPos(x, y, angle = 0) {
  pokeballEl.style.left      = x + 'px';
  pokeballEl.style.top       = y + 'px';
  pokeballEl.style.transform = 	ranslate(-50%, -50%) rotate(\deg);
}

function bezier(t, p0, p1, p2) {
  const u = 1 - t;
  return u * u * p0 + 2 * u * t * p1 + t * t * p2;
}

// ── Catch animation ──────────────────────────────────────────

function playCatchAnimation(catchData) {
  if (catchAnimationRunning) return;
  catchAnimationRunning = true;

  // Target: center of the pokemon gif (always bottom-right, fixed)
  const target = getPokemonCenter();

  // Pokeball starts from off-screen right, slightly below target for upward arc
  const startX    = window.innerWidth + 80;
  const startY    = target.y + 70;
  const controlX  = (startX + target.x) / 2;
  const controlY  = target.y - Math.abs(startX - target.x) * 0.28;

  // Reset pokeball state and place it off-screen before revealing
  pokeballEl.classList.remove('locked', 'open', 'shake');
  pokeballEl.style.opacity = '1';
  setPokeballPos(startX, startY, 20);
  setHidden(pokeballEl, false);

  // Reset pokemon gif appearance
  spawnGifEl.style.transform = 'scale(1)';
  spawnGifEl.style.filter    = '';

  // ── Phase 1: Throw ──────────────────────────────────────
  animate(900, (t) => {
    const e = easeOut(t);
    setPokeballPos(
      bezier(e, startX, controlX, target.x),
      bezier(e, startY, controlY, target.y),
      lerp(-45, 0, e)
    );
  })

  // ── Phase 2: Impact — glow flash + pokemon shrinks ──────
  .then(() => {
    spawnGifEl.style.filter = 'brightness(5) saturate(0)';
    setTimeout(() => { spawnGifEl.style.filter = ''; }, 160);
    return animate(220, (t) => {
      spawnGifEl.style.transform = scale(\);
    });
  })

  // ── Phase 3: Pokemon absorbed — shake ball ──────────────
  .then(() => {
    setHidden(spawnGifEl, true);
    spawnGifEl.style.transform = 'scale(1)';
    spawnGifEl.style.filter    = '';
    // Pokeball stays at target position during shake
    setPokeballPos(target.x, target.y);
    pokeballEl.classList.add('shake');
    return animate(1100, () => {});
  })

  // ── Phase 4a: Success ───────────────────────────────────
  .then(() => {
    pokeballEl.classList.remove('shake');
    if (catchData.result === 'success') {
      pokeballEl.classList.add('locked');
      return animate(600, (t) => {
        pokeballEl.style.opacity = String(lerp(1, 0, t));
      }).then(() => {
        setHidden(pokeballEl, true);
        catchAnimationRunning = false;
      });
    }

    // ── Phase 4b: Fail — burst open, pokemon reappears ───
    pokeballEl.classList.add('open');
    return animate(400, () => {}).then(() => {
      pokeballEl.classList.remove('open');
      setHidden(pokeballEl, true);
      // Pokemon reappears at its fixed bottom-right position — same as always
      setHidden(spawnGifEl, false);
      catchAnimationRunning = false;
    });
  });
}

// ── Overlay state machine ────────────────────────────────────

function playSpawnSequence(name) {
  if (!name) return;
  spawnGifEl.style.transform = 'scale(1)';
  spawnGifEl.style.filter    = '';
  showGifForName(name);
}

function playDespawnSequence() {
  setHidden(spawnGifEl, true);
  showSmoke(() => {});
}

function updateOverlay(state) {
  // Never interrupt a running animation
  if (catchAnimationRunning) return;

  const now = Math.floor(Date.now() / 1000);

  // ── New catch event? ──────────────────────────────────────
  if (state && state.catch) {
    const ci = state.catch;
    if (now < (ci.expires_at || 0)) {
      const id = \-\-\;
      if (id !== currentCatchEventId) {
        currentCatchEventId = id;
        playCatchAnimation(ci);
        return;
      }
      // Already played this catch event — wait for it to expire in the JSON
      return;
    }
  }

  // ── Spawn / idle ──────────────────────────────────────────
  const active    = state && state.spawn && state.state === 'spawn' && now < (state.spawn?.expires_at || 0);
  const spawnName = state?.spawn?.name || '';

  if (!active) {
    if (currentSpawnName) {
      currentSpawnName = '';
      playDespawnSequence();
    }
    return;
  }

  if (currentSpawnName !== spawnName) {
    currentSpawnName = spawnName;
    playSpawnSequence(spawnName);
  }
}

// ── Poll ─────────────────────────────────────────────────────

function buildOverlayUrl() {
  const base = new URL(window.location.href);
  return new URL('../Data/overlay_state.json', base).toString();
}

async function poll() {
  try {
    const res = await fetch(\?ts=\);
    if (!res.ok) { console.warn('Overlay: failed to read overlay_state.json'); return; }
    updateOverlay(await res.json());
  } catch (err) {
    console.warn('Overlay: cannot access local JSON (check OBS local file access)');
  }
}

setInterval(poll, 1000);
poll();
