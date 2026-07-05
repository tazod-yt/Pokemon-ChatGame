const overlayEl = document.querySelector(".overlay");
const statusEl = document.getElementById("status");
const spawnEl = document.getElementById("spawn");
const spawnNameEl = document.getElementById("spawn-name");
const timerEl = document.getElementById("timer");
const resultEl = document.getElementById("result");
const spawnGifEl = document.getElementById("spawn-gif");
const spawnSmokeEl = document.getElementById("spawn-smoke");

// Battle overlay elements
const battleContainerEl = document.getElementById("battle-container");
const p1TrainerEl = document.getElementById("p1-trainer");
const p2TrainerEl = document.getElementById("p2-trainer");
const p1GifEl = document.getElementById("p1-gif");
const p2GifEl = document.getElementById("p2-gif");
const p1Wrapper = document.getElementById("p1-wrapper");
const p2Wrapper = document.getElementById("p2-wrapper");
const battleMessageBoxEl = document.getElementById("battle-message-box");

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

let isAnimatingCatch = false;
let lastProcessedCatchTime = -1;

function playCatchSuccessAnimation(pokemonName) {
  isAnimatingCatch = true;
  
  const ballContainer = document.getElementById("pokeball-container");
  const starsContainer = document.getElementById("stars-container");
  
  // Make sure containers are visible and reset
  setHidden(ballContainer, false);
  ballContainer.className = "pokeball-container throwing";
  
  // Step 1: Throw ball (0.8s throw animation)
  setTimeout(() => {
    // Step 2: Hitting Pokemon & Sucking it in
    ballContainer.className = "pokeball-container"; // Stop spin/throw
    spawnGifEl.classList.add("capturing");
    
    setTimeout(() => {
      // Step 3: Pokemon is in. Hide Pokemon GIF and drop ball to ground.
      setHidden(spawnGifEl, true);
      spawnGifEl.classList.remove("capturing");
      ballContainer.className = "pokeball-container dropping";
      
      setTimeout(() => {
        // Step 4: Shaking (3 shakes with a delay in between)
        playWobble(ballContainer, 1, () => {
          playWobble(ballContainer, 2, () => {
            playWobble(ballContainer, 3, () => {
              // Capture success! Flash green and shoot stars
              ballContainer.className = "pokeball-container captured";
              spawnStars(starsContainer);
              
              // Let it shine for 1.5s then fade out
              setTimeout(() => {
                ballContainer.style.transition = "opacity 0.8s";
                ballContainer.style.opacity = "0";
                
                setTimeout(() => {
                  setHidden(ballContainer, true);
                  ballContainer.style.opacity = "1";
                  ballContainer.className = "pokeball-container hidden";
                  isAnimatingCatch = false;
                }, 800);
              }, 1500);
            });
          });
        });
      }, 400); // Wait for drop animation to end
    }, 600); // Wait for suck in animation to end
  }, 800); // Wait for throw to end
}

function playWobble(el, shakeNum, callback) {
  setTimeout(() => {
    el.classList.add("wobbling");
    const onWobbleEnd = () => {
      el.classList.remove("wobbling");
      el.removeEventListener("animationend", onWobbleEnd);
      callback();
    };
    el.addEventListener("animationend", onWobbleEnd);
  }, 500); // pause between shakes
}

function spawnStars(container) {
  container.innerHTML = "";
  const numStars = 8;
  for (let i = 0; i < numStars; i++) {
    const star = document.createElement("div");
    star.className = "star";
    
    // Calculate directions around the center of the ball
    const angle = (i * 2 * Math.PI) / numStars;
    const distance = 35 + Math.random() * 20;
    const dx = Math.cos(angle) * distance;
    const dy = Math.sin(angle) * distance;
    
    star.style.setProperty("--dx", `${dx}px`);
    star.style.setProperty("--dy", `${dy}px`);
    container.appendChild(star);
  }
}

let lastProcessedBattleTime = -1;

function playBattleSequence(result) {
  isAnimatingCatch = true;
  setHidden(spawnGifEl, true); // Hide active spawn during battle
  setHidden(battleContainerEl, false);
  
  p1TrainerEl.textContent = result.challenger;
  p2TrainerEl.textContent = result.accepter;
  
  // Get sprites
  const p1Image = nameToImage.get(result.challenger_pokemon) || "";
  const p2Image = nameToImage.get(result.accepter_pokemon) || "";
  
  const p1Base = p1Image.replace(/\.[^.]+$/, '');
  const p2Base = p2Image.replace(/\.[^.]+$/, '');
  
  p1GifEl.src = `../data_downloader/gif/${encodeURIComponent(p1Base)}.gif`;
  p2GifEl.src = `../data_downloader/gif/${encodeURIComponent(p2Base)}.gif`;
  
  p1Wrapper.className = "fighter-wrapper left";
  p2Wrapper.className = "fighter-wrapper right";
  
  const transcript = result.transcript || [];
  let tIndex = 0;
  
  function playNextLine() {
    if (tIndex >= transcript.length) {
      setTimeout(() => {
        battleContainerEl.style.transition = "opacity 0.8s";
        battleContainerEl.style.opacity = "0";
        setTimeout(() => {
          setHidden(battleContainerEl, true);
          battleContainerEl.style.opacity = "1";
          isAnimatingCatch = false;
        }, 800);
      }, 3000);
      return;
    }
    
    const line = transcript[tIndex];
    battleMessageBoxEl.textContent = line;
    
    const p1WasFainted = p1Wrapper.classList.contains("fainted");
    const p2WasFainted = p2Wrapper.classList.contains("fainted");
    
    p1Wrapper.className = "fighter-wrapper left" + (p1WasFainted ? " fainted" : "");
    p2Wrapper.className = "fighter-wrapper right" + (p2WasFainted ? " fainted" : "");
    
    const isChallengerActor = line.toLowerCase().includes(`(${result.challenger.toLowerCase()})`);
    const isAccepterActor = line.toLowerCase().includes(`(${result.accepter.toLowerCase()})`);
    
    if (line.includes("attacks")) {
      if (isChallengerActor) {
        p1Wrapper.classList.add("attacking");
        setTimeout(() => {
          p2Wrapper.classList.add("hurt");
        }, 150);
      } else if (isAccepterActor) {
        p2Wrapper.classList.add("attacking");
        setTimeout(() => {
          p1Wrapper.classList.add("hurt");
        }, 150);
      }
    } else if (line.includes("fainted")) {
      if (isChallengerActor) {
        p1Wrapper.classList.add("fainted");
      } else if (isAccepterActor) {
        p2Wrapper.classList.add("fainted");
      }
    }
    
    tIndex++;
    setTimeout(playNextLine, 2500);
  }
  
  playNextLine();
}

function playDespawnSequence() {
  setHidden(spawnGifEl, true);
  showSmoke();
}

function updateOverlay(state) {
  if (isAnimatingCatch) return;

  if (state) {
    if (state.state === "catch_success") {
      if (lastProcessedCatchTime === -1) {
        lastProcessedCatchTime = state.updated_at || 0;
      }
      if (state.updated_at > lastProcessedCatchTime) {
        lastProcessedCatchTime = state.updated_at;
        currentSpawnName = "";
        playCatchSuccessAnimation(state.spawn?.name);
        return;
      }
    } else if (state.state === "battle" && state.result && state.result.type === "battle") {
      if (lastProcessedBattleTime === -1) {
        lastProcessedBattleTime = state.updated_at || 0;
      }
      if (state.updated_at > lastProcessedBattleTime) {
        lastProcessedBattleTime = state.updated_at;
        currentSpawnName = "";
        playBattleSequence(state.result);
        return;
      }
    }
  }

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
