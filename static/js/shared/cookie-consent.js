(() => {
    const modal = document.querySelector("[data-cookie-modal]");
    if (!modal) {
        return;
    }

    const cookieName = "cookie_consent";
    const cookieLifetimeSeconds = 60 * 60 * 24 * 365;

    function getCookie(name) {
        return document.cookie
            .split("; ")
            .some((cookie) => cookie.startsWith(`${name}=`));
    }

    function closeModal() {
        modal.classList.remove("is-open");
        modal.hidden = true;
    }

    function saveChoice(choice) {
        document.cookie = `${cookieName}=${encodeURIComponent(choice)}; Max-Age=${cookieLifetimeSeconds}; Path=/; SameSite=Lax`;
        closeModal();
    }

    if (getCookie(cookieName)) {
        return;
    }

    modal.hidden = false;
    window.requestAnimationFrame(() => {
        modal.classList.add("is-open");
    });

    modal.querySelectorAll("[data-cookie-choice]").forEach((button) => {
        button.addEventListener("click", () => {
            saveChoice(button.dataset.cookieChoice);
        });
    });
})();
