(() => {
    const previewSelector = "[data-resource-preview]";
    let modal;
    let titleNode;
    let bodyNode;
    let fallbackLink;

    const publicOfficeExtensions = [".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"];
    const videoExtensions = [".mp4", ".webm", ".ogg", ".mov"];
    const imageExtensions = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"];

    const getPath = (url) => {
        try {
            return new URL(url, window.location.href).pathname.toLowerCase();
        } catch (error) {
            return url.toLowerCase();
        }
    };

    const isLocalUrl = (url) => {
        try {
            const parsed = new URL(url, window.location.href);
            return ["localhost", "127.0.0.1", ""].includes(parsed.hostname);
        } catch (error) {
            return true;
        }
    };

    const hasExtension = (url, extensions) => extensions.some((extension) => getPath(url).endsWith(extension));

    const createModal = () => {
        modal = document.createElement("dialog");
        modal.className = "resource-preview-dialog";
        modal.innerHTML = `
            <div class="resource-preview-shell">
                <div class="resource-preview-header">
                    <strong data-resource-preview-title></strong>
                    <div class="resource-preview-actions">
                        <a class="button-link light" data-resource-preview-open target="_blank" rel="noopener">Открыть отдельно</a>
                        <button class="button-link light" type="button" data-resource-preview-close>Закрыть</button>
                    </div>
                </div>
                <div class="resource-preview-body" data-resource-preview-body></div>
            </div>
        `;
        document.body.appendChild(modal);
        titleNode = modal.querySelector("[data-resource-preview-title]");
        bodyNode = modal.querySelector("[data-resource-preview-body]");
        fallbackLink = modal.querySelector("[data-resource-preview-open]");
        modal.querySelector("[data-resource-preview-close]").addEventListener("click", () => modal.close());
        modal.addEventListener("click", (event) => {
            if (event.target === modal) modal.close();
        });
        modal.addEventListener("close", () => {
            bodyNode.replaceChildren();
        });
    };

    const renderPreview = (url, kind) => {
        bodyNode.replaceChildren();

        if (kind === "video" || hasExtension(url, videoExtensions)) {
            const video = document.createElement("video");
            video.src = url;
            video.controls = true;
            video.playsInline = true;
            bodyNode.appendChild(video);
            return;
        }

        if (hasExtension(url, imageExtensions)) {
            const image = document.createElement("img");
            image.src = url;
            image.alt = titleNode.textContent;
            bodyNode.appendChild(image);
            return;
        }

        const frame = document.createElement("iframe");
        let frameUrl = url;
        if (!isLocalUrl(url) && hasExtension(url, publicOfficeExtensions)) {
            frameUrl = `https://docs.google.com/gview?embedded=1&url=${encodeURIComponent(url)}`;
        }
        frame.src = frameUrl;
        frame.loading = "lazy";
        bodyNode.appendChild(frame);
    };

    document.addEventListener("click", (event) => {
        const trigger = event.target.closest(previewSelector);
        if (!trigger) return;

        const url = trigger.dataset.previewUrl || trigger.getAttribute("href");
        if (!url) return;

        event.preventDefault();
        if (!modal) createModal();

        titleNode.textContent = trigger.dataset.previewTitle || trigger.textContent.trim() || "Материал";
        fallbackLink.href = url;
        renderPreview(url, trigger.dataset.previewKind || "");
        modal.showModal();
    });
})();
