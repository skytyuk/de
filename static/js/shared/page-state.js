(() => {
    const storagePrefix = "sae:page-state:";

    function urlKey(url = window.location.href) {
        const parsedUrl = new URL(url, window.location.href);
        parsedUrl.searchParams.delete("notice");
        parsedUrl.searchParams.delete("error");
        parsedUrl.hash = "";
        return `${parsedUrl.pathname}${parsedUrl.search}`;
    }

    function savePageState(targetUrl = window.location.href) {
        const activeElement = document.activeElement;
        const focusSelector = activeElement && activeElement.id
            ? `#${CSS.escape(activeElement.id)}`
            : "";

        sessionStorage.setItem(
            `${storagePrefix}${urlKey(targetUrl)}`,
            JSON.stringify({
                x: window.scrollX,
                y: window.scrollY,
                focusSelector,
            })
        );
    }

    function restorePageState() {
        const key = `${storagePrefix}${urlKey()}`;
        const savedState = sessionStorage.getItem(key);

        if (!savedState) {
            return;
        }

        sessionStorage.removeItem(key);

        try {
            const state = JSON.parse(savedState);
            window.requestAnimationFrame(() => {
                window.scrollTo(state.x || 0, state.y || 0);
                if (state.focusSelector) {
                    document.querySelector(state.focusSelector)?.focus({ preventScroll: true });
                }
            });
        } catch (error) {
            sessionStorage.removeItem(key);
        }
    }

    function getGetFormTarget(form) {
        const targetUrl = new URL(form.action || window.location.href, window.location.href);
        const params = new URLSearchParams();
        const formData = new FormData(form);

        formData.forEach((value, key) => {
            if (value !== "") {
                params.append(key, value);
            }
        });

        targetUrl.search = params.toString();
        targetUrl.hash = "";
        return targetUrl.href;
    }

    document.addEventListener("submit", (event) => {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) {
            return;
        }

        const method = (form.method || "get").toLowerCase();
        if (method === "get") {
            event.preventDefault();
            const targetUrl = getGetFormTarget(form);
            savePageState(targetUrl);
            window.location.replace(targetUrl);
            return;
        }

        savePageState(window.location.href);
    });

    document.addEventListener("click", (event) => {
        const backLink = event.target.closest("[data-history-back]");
        if (backLink) {
            event.preventDefault();
            savePageState();
            if (window.history.length > 1) {
                window.history.back();
                return;
            }
            window.location.href = backLink.dataset.fallbackUrl || backLink.href || "/";
            return;
        }

        const link = event.target.closest("a[href]");
        if (!link || link.target || link.hasAttribute("download")) {
            return;
        }

        const targetUrl = new URL(link.href, window.location.href);
        if (targetUrl.origin !== window.location.origin) {
            return;
        }

        if (link.hasAttribute("data-preserve-page-state")) {
            savePageState(window.location.href);
            return;
        }

        if (targetUrl.pathname === window.location.pathname) {
            savePageState(targetUrl.href);
            event.preventDefault();
            window.location.replace(targetUrl.href);
        }
    });

    window.addEventListener("pageshow", restorePageState);
})();
