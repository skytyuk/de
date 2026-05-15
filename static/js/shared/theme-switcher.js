(() => {
    const storageKey = "sae:theme";
    const root = document.documentElement;
    const toggle = document.querySelector("[data-theme-toggle]");

    function getSavedTheme() {
        try {
            return localStorage.getItem(storageKey) === "dark" ? "dark" : "light";
        } catch (error) {
            return root.classList.contains("dark") ? "dark" : "light";
        }
    }

    function updateToggle(theme) {
        if (!toggle) {
            return;
        }

        const isDark = theme === "dark";
        const label = isDark ? "Включить светлую тему" : "Включить темную тему";
        toggle.setAttribute("aria-label", label);
        toggle.title = label;
        toggle.setAttribute("aria-pressed", String(isDark));
    }

    function setTheme(theme) {
        root.classList.remove("light", "dark");
        root.classList.add(theme);

        try {
            localStorage.setItem(storageKey, theme);
        } catch (error) {
            // Theme still changes for the current page if storage is unavailable.
        }

        updateToggle(theme);
    }

    setTheme(getSavedTheme());

    if (toggle) {
        toggle.addEventListener("click", () => {
            setTheme(root.classList.contains("dark") ? "light" : "dark");
        });
    }
})();
