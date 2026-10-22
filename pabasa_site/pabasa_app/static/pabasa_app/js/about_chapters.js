/* Isolated enhancement for the four About chapters. */
(() => {
    'use strict';
    const journal = document.querySelector('.pabasa-journal');
    if (!journal) return;

    const lab = journal.querySelector('[data-pj-lab]');
    const tabs = [...lab.querySelectorAll('[data-pj-tab]')];
    const panels = [...lab.querySelectorAll('[data-pj-panel]')];
    const index = lab.querySelector('.pj-principles');
    index.setAttribute('role', 'tablist');
    const layout = window.matchMedia('(max-width: 699px)');
    const updateOrientation = () => index.setAttribute('aria-orientation', layout.matches ? 'horizontal' : 'vertical');
    updateOrientation();
    layout.addEventListener('change', updateOrientation);

    function select(tab, focus = false) {
        tabs.forEach(item => {
            const active = item === tab;
            item.setAttribute('aria-selected', String(active));
            item.tabIndex = active ? 0 : -1;
        });
        panels.forEach(panel => { panel.hidden = panel.dataset.pjPanel !== tab.dataset.pjTab; });
        if (focus) tab.focus({ preventScroll: true });
    }
    tabs.forEach((tab, i) => {
        tab.setAttribute('role', 'tab');
        tab.addEventListener('click', () => select(tab));
        tab.addEventListener('keydown', event => {
            const previous = layout.matches ? 'ArrowLeft' : 'ArrowUp';
            const next = layout.matches ? 'ArrowRight' : 'ArrowDown';
            let target;
            if (event.key === next) target = (i + 1) % tabs.length;
            if (event.key === previous) target = (i - 1 + tabs.length) % tabs.length;
            if (event.key === 'Home') target = 0;
            if (event.key === 'End') target = tabs.length - 1;
            if (target !== undefined) { event.preventDefault(); select(tabs[target], true); }
        });
    });
    panels.forEach(panel => { panel.setAttribute('role', 'tabpanel'); panel.tabIndex = 0; });
    select(tabs[0]);
    lab.dataset.enhanced = '';

    // Native dialogs provide inert background, focus containment, and Escape.
    let activeTrigger;
    let previousOverflow;
    journal.querySelectorAll('[data-pj-bio]').forEach(button => {
        button.addEventListener('click', () => {
            const dialog = journal.querySelector('#' + button.dataset.pjBio);
            if (!dialog || dialog.open) return;
            activeTrigger = button;
            previousOverflow = document.documentElement.style.overflow;
            dialog.showModal();
            dialog.scrollTop = 0;
            document.documentElement.style.overflow = 'hidden';
            dialog.querySelector('[data-pj-close]').focus({ preventScroll: true });
        });
    });
    journal.querySelectorAll('.pj-bio').forEach(dialog => {
        dialog.querySelector('[data-pj-close]').addEventListener('click', () => dialog.close());
        dialog.addEventListener('keydown', event => {
            if (event.key !== 'Tab') return;
            const controls = [...dialog.querySelectorAll('button, a[href], summary, [tabindex="0"]')]
                .filter(element => !element.disabled && element.getClientRects().length);
            const first = controls[0];
            const last = controls[controls.length - 1];
            if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {
                event.preventDefault();
                first.focus();
            }
        });
        dialog.addEventListener('click', event => {
            const bounds = dialog.getBoundingClientRect();
            if (event.target === dialog && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) dialog.close();
        });
        dialog.addEventListener('close', () => {
            document.documentElement.style.overflow = previousOverflow;
            activeTrigger?.focus({ preventScroll: true });
            activeTrigger = null;
        });
    });
})();
