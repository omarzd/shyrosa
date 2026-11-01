// Inline in each generated board so opening the file needs no other assets.
(() => {
  const storageKey = "shyrosa-board-theme";
  const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
  let savedTheme;
  try {
    const stored = window.localStorage.getItem(storageKey);
    if (stored === "light" || stored === "dark") savedTheme = stored;
  } catch {
    // Some browsers deny storage for local files; the toggle still works.
  }

  function applyTheme() {
    const theme = savedTheme || (systemTheme.matches ? "dark" : "light");
    document.documentElement.dataset.theme = theme;
    const button = document.getElementById("theme-toggle");
    if (button) button.setAttribute("aria-pressed", String(theme === "dark"));
  }

  // Set the palette before the body paints, then connect the control once parsed.
  applyTheme();
  systemTheme.addEventListener("change", applyTheme);
  document.addEventListener("DOMContentLoaded", () => {
    applyTheme();
    document.getElementById("theme-toggle").addEventListener("click", () => {
      savedTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      applyTheme();
      try {
        window.localStorage.setItem(storageKey, savedTheme);
      } catch {
        // A denied write must not prevent switching this page's palette.
      }
    });
  });
})();
