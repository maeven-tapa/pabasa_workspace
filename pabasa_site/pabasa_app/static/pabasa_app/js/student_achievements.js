(() => {
    const init = () => {
        const card = document.querySelector('[data-achievements]');
        if (!card) return;
        const badges = [...card.querySelectorAll('[data-achievement-id]')];
        const previous = card.querySelector('[data-achievement-prev]');
        const next = card.querySelector('[data-achievement-next]');
        const label = card.querySelector('[data-achievement-page]');
        const navigation = card.querySelector('[data-achievement-pagination]');
        if (!previous || !next || !label || !navigation) return;
        const pageSize = 6;
        const pages = Math.max(1, Math.ceil(badges.length / pageSize));
        let page = 0;
        const render = () => {
            badges.forEach((badge, index) => {
                badge.hidden = Math.floor(index / pageSize) !== page;
            });
            previous.disabled = page === 0;
            next.disabled = page === pages - 1;
            label.textContent = `${page + 1} / ${pages}`;
            label.setAttribute('aria-label', `Page ${page + 1} of ${pages}`);
            navigation.hidden = pages <= 1;
        };
        previous.addEventListener('click', () => {
            if (page > 0) { page--; render(); }
        });
        next.addEventListener('click', () => {
            if (page < pages - 1) { page++; render(); }
        });
        render();

        const details = document.getElementById('achievementDetailsModal');
        if (!details || !window.bootstrap?.Modal) return;
        // Keep the fixed dialog outside the dashboard's scaled card containers.
        document.body.appendChild(details);
        const modal = window.bootstrap.Modal.getOrCreateInstance(details);
        const title = details.querySelector('#achievementDetailsTitle');
        const requirement = details.querySelector('#achievementDetailsRequirement');
        const message = details.querySelector('#achievementDetailsMessage');
        const state = details.querySelector('[data-achievement-details-state]');
        const icon = details.querySelector('[data-achievement-details-icon]');
        let trigger = null;
        card.addEventListener('click', event => {
            const badge = event.target.closest('[data-achievement-id]');
            if (!badge || !card.contains(badge) || badge.hidden) return;
            trigger = badge;
            const earned = badge.classList.contains('unlocked');
            title.textContent = badge.querySelector('.achievement-name').textContent.trim();
            requirement.textContent = badge.title;
            state.textContent = earned ? 'Earned' : 'Locked';
            message.textContent = earned
                ? 'Well done! You have earned this achievement.'
                : 'Keep going! Complete this goal to unlock the badge.';
            details.classList.toggle('is-earned', earned);
            const badgeIcon = badge.querySelector('.achievement-icon i');
            icon.replaceChildren(...(badgeIcon ? [badgeIcon.cloneNode(true)] : []));
            modal.show(badge);
        });
        details.addEventListener('hidden.bs.modal', () => {
            if (trigger?.isConnected && !trigger.hidden) trigger.focus();
        });
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
    else init();
})();
