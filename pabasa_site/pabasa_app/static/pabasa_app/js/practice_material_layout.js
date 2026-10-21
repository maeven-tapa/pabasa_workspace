/* Presentation only: fit the existing material and reflect the existing Skip state. */
(() => {
    const shell = document.querySelector('.practice-scrolls-shell, .practice-color');
    if (!shell) return;
    const free = shell.classList.contains('practice-scrolls-shell');
    const feed = shell.querySelector('.scrolls-feed');
    const stage = shell.querySelector('.practice-stage');
    const skip = document.getElementById('scrollSkipBtn');
    const hint = document.getElementById('scrollsProgressMeta');
    let frame = null;

    function contentSize(element) {
        const style = getComputedStyle(element);
        return {
            width: element.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
            height: element.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom),
        };
    }

    function fit(text, width, height, minimum) {
        text.style.removeProperty('font-size');
        let size = parseFloat(getComputedStyle(text).fontSize);
        if (width <= 0 || height <= 0) return;
        while (size > minimum && (text.scrollWidth > width + 1 || text.scrollHeight > height + 1)) {
            size = Math.max(minimum, size - 1);
            text.style.setProperty('font-size', `${size}px`, 'important');
        }
    }

    function refresh() {
        frame = null;
        if (shell.classList.contains('is-complete')) return;
        if (free) {
            shell.querySelectorAll('.scrolls-card').forEach(card => {
                const text = card.querySelector('.scrolls-card-text');
                if (!text) return;
                const box = contentSize(card);
                fit(text, box.width, box.height, card.classList.contains('practice-word') ? 24 : 16);
            });
            if (hint && skip) {
                const read = document.getElementById('scrollRecordBtn')?.classList.contains('is-read');
                const message = read ? 'Moving to the next card…' : skip.disabled ? 'Skip is paused' : 'Swipe up to skip';
                if (hint.textContent !== message) hint.textContent = message;
            }
        } else if (stage) {
            const text = document.getElementById('colorPracticeText');
            const bubble = shell.querySelector('.color-dialogue');
            if (!text || !bubble) return;
            text.style.removeProperty('font-size');
            const area = contentSize(stage);
            const bubbleBox = contentSize(bubble);
            const bubblePadding = bubble.offsetHeight - bubbleBox.height;
            fit(text, bubbleBox.width, area.height - bubblePadding, 16);
        }
    }

    function schedule() {
        if (frame === null) frame = requestAnimationFrame(refresh);
    }

    // Text, feedback and disabled states change through the existing reader.
    new MutationObserver(schedule).observe(shell, {subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['disabled', 'class']});
    if (window.ResizeObserver) {
        const observer = new ResizeObserver(schedule);
        if (feed) observer.observe(feed);
        if (stage) observer.observe(stage);
    }
    window.addEventListener('resize', schedule);
    document.fonts?.ready.then(schedule);
    schedule();
})();
