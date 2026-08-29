document.documentElement.dataset.palsReady = "true";

function setPalsTheme(theme) {
  const next = theme === "dark" ? "dark" : "light";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("pals.theme", next);
  const button = document.querySelector("#themeToggle");
  if (button) {
    button.textContent = next === "dark" ? "☀" : "☾";
    button.setAttribute("aria-label", next === "dark" ? "Switch to light mode" : "Switch to dark mode");
    button.title = next === "dark" ? "Switch to light mode" : "Switch to dark mode";
  }
}

setPalsTheme(localStorage.getItem("pals.theme") || document.documentElement.dataset.theme || "dark");

document.querySelector("#themeToggle")?.addEventListener("click", () => {
  setPalsTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
});
