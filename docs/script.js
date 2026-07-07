// Interactive Category Tabs
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

// Chat Simulator Core Logic
const chatMessages = document.getElementById("chat-messages");
const chatInput = document.getElementById("chat-input");

const commandMockResponses = {
  "!catch": [
    "🎣 @Trainer: !catch",
    "🤖 PokémonBot: ✨ @Trainer caught a wild Bulbasaur! (Brave)"
  ],
  "!catch great": [
    "🎣 @Trainer: !catch great",
    "🤖 PokémonBot: ✨ @Trainer caught a wild Ivysaur! (Adamant) using a Great Ball!"
  ],
  "!catch ultra": [
    "🎣 @Trainer: !catch ultra",
    "🤖 PokémonBot: ✨ @Trainer caught a wild Venusaur! (Lonely) using an Ultra Ball!"
  ],
  "!bag": [
    "🎒 @Trainer: !bag",
    "🤖 PokémonBot: @Trainer, your Bag contains: 4x fire-stone, 2x great-ball, 1x ultra-ball, 1x metal-coat."
  ],
  "!leaderboard": [
    "⚔️ @Trainer: !leaderboard",
    "🤖 PokémonBot: 🏆 **Trainer Leaderboard**\n1. @ankit (ELO: 1250)\n2. @tazod (ELO: 1180)\n3. @Trainer (ELO: 1045)\n4. @streamer (ELO: 980)"
  ],
  "!pokedex": [
    "📋 @Trainer: !pokedex",
    "🤖 PokémonBot: 📖 **Trainer's Pokédex Progress**\nUnique caught: 48/151 (31.8%)\nTotal Wins: 34 | Total Losses: 12 (Winrate: 73.9%)"
  ],
  "!stats jolteon": [
    "📋 @Trainer: !stats jolteon",
    "🤖 PokémonBot: 📋 **Trainer's Jolteon Collection**\n🔹 **Lv. 12 Jolteon** (PID: `P149`) - ELO: 1015 | Wins: 2 Losses: 0 | IVs: HP 15, ATK 12, DEF 8, SPD 14 (Trait: Jolly)\n🔹 **Lv. 8 Jolteon** (PID: `P204`) - ELO: 1000 | Wins: 0 Losses: 1 | IVs: HP 4, ATK 15, DEF 14, SPD 11 (Trait: Brave)"
  ],
  "!stats eevee": [
    "📋 @Trainer: !stats eevee",
    "🤖 PokémonBot: 📋 **Trainer's Eevee Collection**\n🔹 **Lv. 10 Eevee** (PID: `P1`) - ELO: 1000 | Wins: 0 Losses: 0 | IVs: HP 10, ATK 10, DEF 10, SPD 10 (Trait: Brave)"
  ],
  "!trade @tazod jolteon": [
    "🤝 @Trainer: !trade @tazod jolteon",
    "🤖 PokémonBot: ⚠️ @Trainer you have more than 1 Jolteon use PID instead, !stats jolteon to get pid"
  ],
  "!trade @tazod p149": [
    "🤝 @Trainer: !trade @tazod p149",
    "🤖 PokémonBot: 🤝 @Trainer wants to trade their Jolteon (PID: P149) with @tazod. @tazod, type !accepttrade @Trainer <pokemon_name/number> to complete the trade."
  ],
  "!use fire-stone p1": [
    "✨ @Trainer: !use fire-stone p1",
    "🤖 PokémonBot: ✨ @Trainer used a fire-stone on their Eevee (PID: P1), evolving it into Flareon!"
  ],
  "!battle @tazod eevee": [
    "⚔️ @Trainer: !battle @tazod eevee",
    "🤖 PokémonBot: ⚔️ @Trainer challenged @tazod with Eevee! @tazod, use !accept @Trainer <pokemon> within 120s."
  ]
};

function writeMessage(text, type = "system-msg") {
  const msgEl = document.createElement("div");
  msgEl.className = `message ${type}`;
  msgEl.textContent = text;
  chatMessages.appendChild(msgEl);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function runPreset(cmd) {
  executeSimulatorCmd(cmd);
}

function handleKeyDown(e) {
  if (e.key === "Enter") {
    sendInput();
  }
}

function sendInput() {
  const val = chatInput.value.trim();
  if (!val) return;
  chatInput.value = "";
  executeSimulatorCmd(val);
}

function executeSimulatorCmd(cmd) {
  const normCmd = cmd.toLowerCase().replace(/\s+/g, ' ');
  
  // Find match in responses key
  let responsePair = null;
  for (const key of Object.keys(commandMockResponses)) {
    if (normCmd === key || normCmd.startsWith(key + " ") || key.startsWith(normCmd)) {
      responsePair = commandMockResponses[key];
      break;
    }
  }

  // Write sender message
  writeMessage(`💬 Trainer: ${cmd}`, "user-msg");

  setTimeout(() => {
    if (responsePair) {
      // Simulate bot message
      writeMessage(responsePair[1], "bot-msg");
    } else {
      // Default fallback bot response
      if (cmd.startsWith("!")) {
        writeMessage(`🤖 PokémonBot: Unknown command "${cmd}". Try preset buttons or check guide.`, "bot-msg");
      } else {
        writeMessage("🤖 PokémonBot: Type a valid command starting with ! to interact with the game.", "bot-msg");
      }
    }
  }, 600);
}
