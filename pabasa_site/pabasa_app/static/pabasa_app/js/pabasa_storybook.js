/* Keep public-page anchor offsets aligned with the responsive navigation. */
(() => {
    'use strict';
    const book = document.querySelector('.pabasa-storybook');
    if (!book) return;
    const navigation = document.querySelector('.modern-nav-wrap');
    const syncNavigation = () => {
        if (navigation) book.style.setProperty('--story-nav-height', `${navigation.getBoundingClientRect().height}px`);
    };
    syncNavigation();
    if (navigation && 'ResizeObserver' in window) new ResizeObserver(syncNavigation).observe(navigation);
    else window.addEventListener('resize', syncNavigation, {passive: true});
})();
