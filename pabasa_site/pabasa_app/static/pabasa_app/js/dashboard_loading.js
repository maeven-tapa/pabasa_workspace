(function () {
    "use strict";
    const pending = new Set();
    const callbacks = new Set();
    let loaded = document.readyState === "complete";
    let ready = false;
    let preparing = false;
    let revision = 0;

    function imageReady(image) {
        const decode = () => image.decode ? image.decode().catch(() => {}) : Promise.resolve();
        if (image.complete) return decode();
        return new Promise(resolve => {
            image.addEventListener("load", resolve, { once: true });
            image.addEventListener("error", resolve, { once: true });
        }).then(decode);
    }

    function prepareReveal() {
        if (ready || preparing || !loaded || pending.size) return;
        preparing = true;
        const currentRevision = revision;
        const images = Array.from(document.images).filter(image =>
            image.loading !== "lazy" && image.getClientRects().length > 0);
        const fonts = document.fonts?.ready || Promise.resolve();
        Promise.allSettled([fonts, ...images.map(imageReady)]).then(() => {
            // The content stays mounted behind the overlay while it is rendered.
            // Wait for layout and paint after the final data/image update.
            requestAnimationFrame(() => requestAnimationFrame(() => {
                preparing = false;
                if (pending.size || revision !== currentRevision) {
                    prepareReveal();
                    return;
                }
                ready = true;
                callbacks.forEach(callback => callback());
                callbacks.clear();
            }));
        });
    }

    function hold(label) {
        // Later polling and user actions should not restart initial-page loading.
        if (ready) return () => {};
        const task = Symbol(label);
        pending.add(task);
        revision += 1;
        return () => {
            if (!pending.delete(task)) return;
            revision += 1;
            prepareReveal();
        };
    }

    window.PabasaDashboardLoading = {
        hold,
        track(promise, label) {
            const release = hold(label);
            return Promise.resolve(promise).finally(release);
        },
        whenReady(callback) {
            if (ready) callback();
            else callbacks.add(callback);
            prepareReveal();
        },
    };
    window.addEventListener("load", () => {
        loaded = true;
        prepareReveal();
    }, { once: true });
})();
