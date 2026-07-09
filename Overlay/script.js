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

// Evolution overlay elements
const evolutionContainerEl = document.getElementById("evolution-container");
const evolutionGifEl = document.getElementById("evolution-gif");
const evolutionMessageBoxEl = document.getElementById("evolution-message-box");

// Trade overlay elements
const tradeContainerEl = document.getElementById("trade-container");
const t1TrainerEl = document.getElementById("t1-trainer");
const t2TrainerEl = document.getElementById("t2-trainer");
const t1GifEl = document.getElementById("t1-gif");
const t2GifEl = document.getElementById("t2-gif");
const t1Bubble = document.getElementById("t1-bubble");
const t2Bubble = document.getElementById("t2-bubble");
const tradeMessageBoxEl = document.getElementById("trade-message-box");

let nameToImage = new Map();
let currentSpawnName = "";
const POKEMON_INDEX_URL = (() => {
  const base = new URL(window.location.href);
  return new URL("../image_data/pokemon_base_stats.json", base).toString();
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
  const gifUrl = `../image_data/gif/${encodeURIComponent(baseName)}.gif`;
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

function playCatchSuccessAnimation(pokemonName, ballType) {
  isAnimatingCatch = true;
  
  const ballContainer = document.getElementById("pokeball-container");
  const ball = ballContainer.querySelector(".pokeball");
  const starsContainer = document.getElementById("stars-container");
  
  // Reset and set ball class
  ball.className = "pokeball";
  if (ballType === "great-ball") {
    ball.classList.add("great-ball");
  } else if (ballType === "ultra-ball") {
    ball.classList.add("ultra-ball");
  }
  
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

function spawnStarsAtElement(el) {
  const numStars = 8;
  const tempStars = [];
  for (let i = 0; i < numStars; i++) {
    const star = document.createElement("div");
    star.className = "star";
    const angle = (i * 2 * Math.PI) / numStars;
    const distance = 35 + Math.random() * 20;
    const dx = Math.cos(angle) * distance;
    const dy = Math.sin(angle) * distance;
    
    star.style.setProperty("--dx", `${dx}px`);
    star.style.setProperty("--dy", `${dy}px`);
    el.appendChild(star);
    tempStars.push(star);
  }
  setTimeout(() => {
    tempStars.forEach(s => s.remove());
  }, 1000);
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
  
  p1GifEl.src = `../image_data/gif/${encodeURIComponent(p1Base)}.gif`;
  p2GifEl.src = `../image_data/gif/${encodeURIComponent(p2Base)}.gif`;
  
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

let lastProcessedTradeTime = -1;

function playTradeSequence(trade) {
  isAnimatingCatch = true;
  setHidden(spawnGifEl, true); // Hide active spawn during trade
  setHidden(tradeContainerEl, false);

  t1TrainerEl.textContent = trade.sender;
  t2TrainerEl.textContent = trade.receiver;

  // Retrieve sprites
  const p1Image = nameToImage.get(trade.sender_pokemon) || "";
  const p2Image = nameToImage.get(trade.receiver_pokemon) || "";

  const p1Base = p1Image.replace(/\.[^.]+$/, '');
  const p2Base = p2Image.replace(/\.[^.]+$/, '');

  const p1GifUrl = `../image_data/gif/${encodeURIComponent(p1Base)}.gif`;
  const p2GifUrl = `../image_data/gif/${encodeURIComponent(p2Base)}.gif`;

  // Reset classes and set initial source
  t1GifEl.src = p1GifUrl;
  t2GifEl.src = p2GifUrl;
  t1Bubble.className = "pokemon-bubble";
  t2Bubble.className = "pokemon-bubble";

  // Step 1: Start (0s)
  tradeMessageBoxEl.textContent = `Trade between @${trade.sender} and @${trade.receiver} starting...`;

  // Step 2: Shrink and glow (at 1.0s)
  setTimeout(() => {
    t1Bubble.classList.add("shrinking");
    t2Bubble.classList.add("shrinking");
    tradeMessageBoxEl.textContent = `Trading @${trade.sender}'s ${trade.sender_pokemon}...`;
  }, 1000);

  // Step 3: Swap travel (at 2.0s)
  setTimeout(() => {
    t1Bubble.classList.remove("shrinking");
    t2Bubble.classList.remove("shrinking");
    t1Bubble.classList.add("swapping");
    t2Bubble.classList.add("swapping");
    tradeMessageBoxEl.textContent = `...for @${trade.receiver}'s ${trade.receiver_pokemon}!`;
  }, 2000);

  // Step 4: Swap completion, swap src, reset positions, add reveal burst (at 3.5s)
  setTimeout(() => {
    t1Bubble.classList.remove("swapping");
    t2Bubble.classList.remove("swapping");
    
    // Swap the image sources
    t1GifEl.src = p2GifUrl;
    t2GifEl.src = p1GifUrl;

    // Trigger reveal burst
    t1Bubble.classList.add("revealing");
    t2Bubble.classList.add("revealing");

    // Spawn stars/particles at both platforms
    spawnStarsAtElement(t1Bubble);
    spawnStarsAtElement(t2Bubble);

    tradeMessageBoxEl.textContent = "Swapping complete!";
  }, 3500);

  // Step 5: Trade complete (at 4.5s)
  setTimeout(() => {
    t1Bubble.classList.remove("revealing");
    t2Bubble.classList.remove("revealing");
    tradeMessageBoxEl.textContent = "Trade complete!";
  }, 4500);

  // Step 6: Cleanup and hide (at 5.0s)
  setTimeout(() => {
    tradeContainerEl.style.transition = "opacity 0.5s";
    tradeContainerEl.style.opacity = "0";
    setTimeout(() => {
      setHidden(tradeContainerEl, true);
      tradeContainerEl.style.opacity = "1";
      tradeContainerEl.style.transition = "";
      isAnimatingCatch = false;
    }, 500);
  }, 5000);
}

let lastProcessedEvolutionTime = -1;

function playEvolutionSequence(ev) {
  isAnimatingCatch = true;
  setHidden(spawnGifEl, true); // Hide active spawn during animation
  setHidden(evolutionContainerEl, false);
  
  // Get sprites
  const oldImage = nameToImage.get(ev.from) || "";
  const newImage = nameToImage.get(ev.to) || "";
  
  const oldBase = oldImage.replace(/\.[^.]+$/, '');
  const newBase = newImage.replace(/\.[^.]+$/, '');
  
  const oldGifUrl = `../image_data/gif/${encodeURIComponent(oldBase)}.gif`;
  const newGifUrl = `../image_data/gif/${encodeURIComponent(newBase)}.gif`;
  
  // Set starting sprite
  evolutionGifEl.src = oldGifUrl;
  evolutionGifEl.className = "evolution-gif";
  evolutionMessageBoxEl.textContent = "Something is happening!";
  
  // Stage 1: Slow flash (0.8s intervals)
  evolutionGifEl.classList.add("flashing-slow");
  
  // Stage 2: Fast flash at 3s
  setTimeout(() => {
    evolutionGifEl.classList.remove("flashing-slow");
    evolutionGifEl.classList.add("flashing-fast");
  }, 3000);
  
  // Stage 3: Evolve at 5s
  setTimeout(() => {
    evolutionGifEl.classList.remove("flashing-fast");
    evolutionGifEl.src = newGifUrl;
    evolutionGifEl.classList.add("evolved");
    evolutionMessageBoxEl.textContent = `@${ev.username}'s ${ev.from} evolved into ${ev.to}!`;
  }, 5000);
  
  // Stage 4: Reset overlay at 8s
  setTimeout(() => {
    evolutionGifEl.classList.remove("evolved");
    setHidden(evolutionContainerEl, true);
    isAnimatingCatch = false;
  }, 8000);
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
        playCatchSuccessAnimation(state.spawn?.name, state.ball_type);
        return;
      }
    } else if (state.state === "battle" && state.result && state.result.type === "battle") {
      const now = Math.floor(Date.now() / 1000);
      const isBattleActive = now < (state.result.expires_at || 0);
      
      if (isBattleActive) {
        if (state.updated_at > lastProcessedBattleTime) {
          lastProcessedBattleTime = state.updated_at;
          currentSpawnName = "";
          playBattleSequence(state.result);
          return;
        }
      } else {
        if (state.updated_at > lastProcessedBattleTime) {
          lastProcessedBattleTime = state.updated_at;
        }
      }
    } else if (state.state === "evolution" && state.evolution) {
      const now = Math.floor(Date.now() / 1000);
      const isEvolutionActive = now < (state.evolution.expires_at || 0);
      
      if (isEvolutionActive) {
        if (state.updated_at > lastProcessedEvolutionTime) {
          lastProcessedEvolutionTime = state.updated_at;
          currentSpawnName = "";
          playEvolutionSequence(state.evolution);
          return;
        }
      } else {
        if (state.updated_at > lastProcessedEvolutionTime) {
          lastProcessedEvolutionTime = state.updated_at;
        }
      }
    } else if (state.state === "trade" && state.trade) {
      const now = Math.floor(Date.now() / 1000);
      const isTradeActive = now < (state.trade.expires_at || 0);
      
      if (isTradeActive) {
        if (state.updated_at > lastProcessedTradeTime) {
          lastProcessedTradeTime = state.updated_at;
          currentSpawnName = "";
          playTradeSequence(state.trade);
          return;
        }
      } else {
        if (state.updated_at > lastProcessedTradeTime) {
          lastProcessedTradeTime = state.updated_at;
        }
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
