const statusEl = document.getElementById("status");
const spawnEl = document.getElementById("spawn");
const spawnNameEl = document.getElementById("spawn-name");
const timerEl = document.getElementById("timer");
const resultEl = document.getElementById("result");

function setHidden(el, hidden) {
  if (hidden) {
    el.classList.add("hidden");
  } else {
    el.classList.remove("hidden");
  }
}

function updateOverlay(state) {
  if (!state) {
    statusEl.textContent = "Waiting for a spawn...";
    setHidden(spawnEl, true);
    setHidden(resultEl, true);
    return;
  }

  statusEl.textContent = state.message || "";

  if (state.state === "spawn" && state.spawn) {
    spawnNameEl.textContent = state.spawn.name || "Unknown";
    const now = Math.floor(Date.now() / 1000);
    const expiresAt = state.spawn.expires_at || 0;
    const remaining = Math.max(0, expiresAt - now);
    timerEl.textContent = remaining;
    setHidden(spawnEl, false);
  } else {
    setHidden(spawnEl, true);
  }

  if (state.result) {
    if (state.result.type === "catch_success") {
      resultEl.textContent = `${state.result.user} caught ${state.result.creature}!`;
    } else if (state.result.type === "catch_fail") {
      resultEl.textContent = `${state.result.user} failed to catch ${state.result.creature}.`;
    } else if (state.result.type === "battle") {
      resultEl.textContent = `${state.result.winner} defeated ${state.result.loser}!`;
    } else {
      resultEl.textContent = "";
    }
    setHidden(resultEl, false);
  } else {
    setHidden(resultEl, true);
  }
}

async function poll() {
  try {
    const response = await fetch(`../Data/overlay_state.json?ts=${Date.now()}`);
    if (!response.ok) return;
    const data = await response.json();
    updateOverlay(data);
  } catch (err) {
    // ignore errors to keep overlay running
  }
}

setInterval(poll, 1000);
poll();
