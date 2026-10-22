/* Optional journey orientation. Content and anchor navigation work without JavaScript. */
(() => {
    'use strict';
    const journey = document.querySelector('.pabasa-journey');
    if (!journey || !('IntersectionObserver' in window)) return;
    const stops = [...journey.querySelectorAll('.pabasa-journey-stops > li')];
    const links = [...document.querySelectorAll('.pabasa-journey-nav a')];
    const visible = new Set();
    const markCurrent = stop => {
        stops.forEach(item => item.classList.toggle('is-current', item === stop));
        links.forEach(link => {
            if (stop && link.hash === `#${stop.id}`) link.setAttribute('aria-current', 'step');
            else link.removeAttribute('aria-current');
        });
    };
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) visible.add(entry.target);
            else visible.delete(entry.target);
        });
        // Keep document order on wide screens where several stages share the viewport.
        markCurrent(stops.find(stop => visible.has(stop)));
    }, {rootMargin: '-18% 0px -25% 0px', threshold: 0.05});
    stops.forEach(stop => observer.observe(stop));
    links.forEach(link => link.addEventListener('click', () => {
        markCurrent(stops.find(stop => `#${stop.id}` === link.hash));
    }));
})();
