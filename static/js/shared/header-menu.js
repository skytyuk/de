(() => {
    const navigation = document.querySelector("[data-header-navigation]");
    const toggle = document.querySelector("[data-header-menu-toggle]");
    const menu = document.querySelector("[data-header-menu]");

    if (!navigation || !toggle || !menu) return;

    const closeMenu = () => {
        navigation.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
    };

    toggle.addEventListener("click", () => {
        const isOpen = navigation.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", String(isOpen));
    });

    document.addEventListener("click", (event) => {
        if (!navigation.contains(event.target)) closeMenu();
    });

    window.addEventListener("resize", () => {
        if (window.innerWidth > 840) closeMenu();
    });
})();
