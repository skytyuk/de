(() => {
    const url = document.body.dataset.notificationCountsUrl;
    const badges = Array.from(document.querySelectorAll("[data-notification-badge]"));

    if (!url || !badges.length) {
        return;
    }

    const updateBadges = (count) => {
        badges.forEach((badge) => {
            if (count > 0) {
                badge.textContent = String(count);
                badge.hidden = false;
            } else {
                badge.textContent = "0";
                badge.hidden = true;
            }
        });
    };

    const refresh = async () => {
        try {
            const response = await fetch(url, {
                credentials: "same-origin",
                headers: {"Accept": "application/json"},
            });
            if (!response.ok) {
                return;
            }
            const data = await response.json();
            updateBadges(Number(data.unread) || 0);
        } catch (error) {
            // The badge is non-critical UI, so a temporary network error is ignored.
        }
    };

    refresh();
    setInterval(refresh, 10000);
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            refresh();
        }
    });
})();
