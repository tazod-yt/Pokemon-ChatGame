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
