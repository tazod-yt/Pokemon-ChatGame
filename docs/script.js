// Interactive Category Tabs & Pokedex Database
document.addEventListener("DOMContentLoaded", () => {
  const tabs = document.querySelectorAll(".tab-btn");
  const cards = document.querySelectorAll(".command-card");

  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      // Set active class
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      // Filter cards
      const category = tab.getAttribute("data-category");
      cards.forEach(card => {
        if (category === "all" || card.getAttribute("data-category") === category) {
          card.style.display = "flex";
        } else {
          card.style.display = "none";
        }
      });
    });
  });

  // Pokémon Pokedex Search Database
  let baseStatsData = null;
  let evolutionRulesData = null;

  const pokedexInput = document.getElementById("pokedex-input");
  const suggestionsBox = document.getElementById("pokedex-suggestions");
  const resultContainer = document.getElementById("pokedex-result-container");

  // Load JSON datasets
  Promise.all([
    fetch("../image_data/pokemon_base_stats.json").then(res => res.json()),
    fetch("../image_data/evolution_rules.json").then(res => res.json())
  ]).then(([stats, evo]) => {
    baseStatsData = stats.pokemon;
    evolutionRulesData = evo;
    console.log("Pokedex data loaded successfully!");
  }).catch(err => {
    console.error("Failed to load Pokedex datasets:", err);
  });

  pokedexInput.addEventListener("input", () => {
    const query = pokedexInput.value.trim().toLowerCase();
    if (!query || !baseStatsData) {
      suggestionsBox.classList.add("hidden");
      suggestionsBox.innerHTML = "";
      return;
    }

    const matches = Object.keys(baseStatsData).filter(key => {
      const p = baseStatsData[key];
      return p.name.toLowerCase().includes(query) || String(p.dex_number) === query;
    }).slice(0, 5);

    if (matches.length === 0) {
      suggestionsBox.classList.add("hidden");
      suggestionsBox.innerHTML = "";
      return;
    }

    suggestionsBox.innerHTML = matches.map(key => {
      const p = baseStatsData[key];
      const dexStr = String(p.dex_number).padStart(3, '0');
      return `<div class="suggestion-item" data-key="${key}">
        <span>#${dexStr} - <strong>${p.name}</strong></span>
      </div>`;
    }).join("");

    suggestionsBox.classList.remove("hidden");

    // Add click listeners to suggestions
    document.querySelectorAll(".suggestion-item").forEach(item => {
      item.addEventListener("click", () => {
        const key = item.getAttribute("data-key");
        displayPokemon(key);
        pokedexInput.value = baseStatsData[key].name;
        suggestionsBox.classList.add("hidden");
        suggestionsBox.innerHTML = "";
      });
    });
  });

  // Hide suggestions when clicking outside
  document.addEventListener("click", (e) => {
    if (e.target !== pokedexInput && e.target !== suggestionsBox) {
      suggestionsBox.classList.add("hidden");
    }
  });

  function getBarWidth(val) {
    return Math.min(100, (val / 200) * 100) + "%";
  }

  function renderStatRow(label, val) {
    return `
      <div class="stat-row">
        <div class="stat-info">
          <span class="stat-label">${label}</span>
          <span class="stat-value">${val}</span>
        </div>
        <div class="bar-bg">
          <div class="bar-fill" style="width: ${getBarWidth(val)}"></div>
        </div>
      </div>
    `;
  }

  const typeColors = {
    normal: '#a8a77a',
    fire: '#ee8130',
    water: '#6390f0',
    electric: '#f7d02c',
    grass: '#7ac74c',
    ice: '#96d9d6',
    fighting: '#c22e28',
    poison: '#a33ea1',
    ground: '#e2bf65',
    flying: '#a98ff3',
    psychic: '#f95587',
    bug: '#a6b91a',
    rock: '#b6a136',
    ghost: '#735797',
    dragon: '#6f35fc',
    steel: '#b7b7c9',
    fairy: '#d685ad'
  };

  function displayPokemon(key) {
    if (!baseStatsData) return;
    const p = baseStatsData[key];
    const name = p.name;
    const dexStr = String(p.dex_number).padStart(3, '0');
    const stats = p.base_stats;
    const types = p.types;
    const imageFile = p.image_file;
    const catchRate = p.catch_rate?.value || "N/A";

    const typesHtml = types.map(t => {
      const color = typeColors[t.toLowerCase()] || '#777';
      return `<span class="type-badge" style="background-color: ${color}">${t}</span>`;
    }).join("");

    const imgUrl = `../image_data/images/${imageFile}`;

    const evos = evolutionRulesData ? (evolutionRulesData[name] || []) : [];
    let evoCardsHtml = "";

    if (evos.length === 0) {
      evoCardsHtml = `<div class="fully-evolved-msg">Fully Evolved! No further evolutions.</div>`;
    } else {
      evoCardsHtml = evos.map(e => {
        let method = "";
        if (e.type === "level-up") {
          method = `Reaches <strong>Level ${e.level}</strong>`;
        } else if (e.type === "use-item") {
          method = `Consume a <strong>${e.item}</strong>`;
        } else if (e.type === "trade") {
          if (e.held_item) {
            method = `Trade while holding a <strong>${e.held_item}</strong>`;
          } else {
            method = `Perform a standard <strong>Trade</strong>`;
          }
        } else {
          method = `Special evolution requirements`;
        }
        
        return `
          <div class="evo-card">
            <span class="evo-arrow">➔</span>
            <div class="evo-details">
              <div class="evo-target-name">${e.to}</div>
              <div class="evo-method">${method}</div>
            </div>
          </div>
        `;
      }).join("");
    }

    resultContainer.innerHTML = `
      <div class="pokedex-card animate-pop">
        <div class="pokedex-grid">
          
          <!-- Column 1: Info & Sprite -->
          <div class="pokedex-info-col">
            <div class="pokedex-header">
              <div class="pokedex-id">#${dexStr}</div>
              <h3 class="pokedex-name">${name}</h3>
              <div class="pokedex-types">${typesHtml}</div>
            </div>
            
            <div class="sprite-display">
              <img src="${imgUrl}" alt="${name}" class="pokedex-sprite" />
            </div>
            
            <div class="catch-rate-info">
              Base Catch Rate: <strong>${catchRate}</strong>
            </div>
          </div>

          <!-- Column 2: Base Stats -->
          <div>
            <div class="stats-header">Base Stats</div>
            <div class="stats-list">
              ${renderStatRow("HP", stats.hp)}
              ${renderStatRow("Attack", stats.attack)}
              ${renderStatRow("Defense", stats.defense)}
              ${renderStatRow("Sp. Atk", stats.sp_atk)}
              ${renderStatRow("Sp. Def", stats.sp_def)}
              ${renderStatRow("Speed", stats.speed)}
            </div>
            
            <div class="stat-total">
              <span class="stat-total-label">Total Stats</span>
              <span>${stats.total}</span>
            </div>
          </div>

          <!-- Column 3: Evolutions -->
          <div>
            <div class="evo-header">Evolutions</div>
            <div class="evolution-list">
              ${evoCardsHtml}
            </div>
          </div>

        </div>
      </div>
    `;

    resultContainer.classList.remove("hidden");
  }
});

// Clipboard Copy Function
function copyText(text) {
  navigator.clipboard.writeText(text).then(() => {
    const toast = document.getElementById("toast");
    toast.textContent = `Copied "${text}" to clipboard!`;
    toast.classList.add("show");
    setTimeout(() => {
      toast.classList.remove("show");
    }, 2000);
  });
}
