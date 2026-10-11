/* Only the menu scrolls; branding and account controls stay in place. */
(() => {
    const heroes = ['aguinaldo', 'alonzo', 'aquino', 'balagtas', 'baltazar', 'bonifacio',
        'dagohoy', 'delpilar', 'escoda', 'jacinto', 'lapulapu', 'luna', 'mabini',
        'magsaysay', 'malvar', 'ricarte', 'rizal', 'sakay'];
    document.querySelectorAll('.signature-profile[data-section-name]').forEach(card => {
        const section = card.dataset.sectionName.normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
            .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
            .replace(/\bdel pilar\b/g, 'delpilar').replace(/\blapu lapu\b/g, 'lapulapu');
        const matches = heroes.filter(hero => section.split(' ').includes(hero));
        if (matches.length === 1) {
            // Use only known asset names, never a URL derived from a section name.
            card.style.setProperty('--section-portrait', `url("${card.dataset.heroAssets}${matches[0]}bg.webp")`);
        }
    });

    document.querySelectorAll('[data-sidebar-nav-frame]').forEach((frame, index) => {
        const menu = frame.querySelector('[data-sidebar-nav-scroll]');
        const up = frame.querySelector('[data-sidebar-scroll="up"]');
        const down = frame.querySelector('[data-sidebar-scroll="down"]');
        menu.id = `signature-menu-${index}`;
        [up, down].forEach(button => button.setAttribute('aria-controls', menu.id));
        let pending = false;
        function update() {
            pending = false;
            if (!menu.clientHeight) return;
            // Measure the content rather than the viewport after adding arrow rows.
            // This avoids toggling the arrows repeatedly near the overflow boundary.
            const contentHeight = [...menu.children].reduce((height, child) =>
                Math.max(height, child.offsetTop + child.offsetHeight + 2), 0);
            const reservedRows = parseFloat(getComputedStyle(frame).getPropertyValue('--signature-reserved-arrows')) || 0;
            const needsArrows = contentHeight > frame.clientHeight - reservedRows + 1;
            frame.classList.toggle('has-overflow', needsArrows);
            const max = menu.scrollHeight - menu.clientHeight;
            up.disabled = menu.scrollTop <= 1;
            down.disabled = menu.scrollTop >= max - 1;
            [up, down].forEach(button => { button.tabIndex = needsArrows ? 0 : -1; });
        }
        function scheduleUpdate() {
            if (!pending) { pending = true; requestAnimationFrame(update); }
        }
        [up, down].forEach(button => button.addEventListener('click', () => {
            const distance = Math.max(52, menu.clientHeight * 0.75);
            menu.scrollBy({ top: button === up ? -distance : distance,
                behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
        }));
        menu.addEventListener('scroll', scheduleUpdate, { passive: true });
        menu.addEventListener('keydown', event => {
            if (event.target !== menu) return;
            const actions = { ArrowUp: -52, ArrowDown: 52, PageUp: -menu.clientHeight, PageDown: menu.clientHeight };
            if (Object.hasOwn(actions, event.key)) {
                event.preventDefault(); menu.scrollBy({ top: actions[event.key] });
            } else if (event.key === 'Home' || event.key === 'End') {
                event.preventDefault(); menu.scrollTo({ top: event.key === 'Home' ? 0 : menu.scrollHeight });
            }
        });
        const observer = new ResizeObserver(scheduleUpdate);
        observer.observe(frame);
        observer.observe(menu);
        [...menu.children].forEach(child => observer.observe(child));
        document.addEventListener('shown.bs.offcanvas', scheduleUpdate);
        document.fonts?.ready.then(scheduleUpdate);
        scheduleUpdate();
    });
})();
