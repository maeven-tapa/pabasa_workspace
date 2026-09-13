(() => {
    // Retain the original selects for validation, option updates and submission.
    const selects = document.querySelectorAll('#teacherSignupForm select, #studentSignupForm select');
    let current = null;

    const close = () => {
        if (!current) return;
        current.select.setAttribute('aria-expanded', 'false');
        current.select.removeAttribute('aria-activedescendant');
        current.select.removeAttribute('aria-controls');
        current.menu.remove();
        current = null;
    };

    const activate = (index) => {
        if (index < 0) return;
        current.active = index;
        current.rows.forEach((row, i) => row.classList.toggle('is-active', i === index));
        const row = current.rows[index];
        current.select.setAttribute('aria-activedescendant', row.id);
        const top = row.offsetTop;
        const bottom = top + row.offsetHeight;
        if (top < current.menu.scrollTop) current.menu.scrollTop = top;
        else if (bottom > current.menu.scrollTop + current.menu.clientHeight) {
            current.menu.scrollTop = bottom - current.menu.clientHeight;
        }
    };

    const choose = (index) => {
        const option = current.options[index];
        if (!option || option.disabled || current.select.disabled) return;
        const select = current.select;
        const changed = select.selectedIndex !== option.index;
        select.selectedIndex = option.index;
        close();
        select.focus({ preventScroll: true });
        if (changed) {
            select.dispatchEvent(new Event('input', { bubbles: true }));
            select.dispatchEvent(new Event('change', { bubbles: true }));
        }
    };

    const open = (select, id) => {
        close();
        if (select.disabled) return;
        // A disabled empty prompt is not a selectable option; keep "None".
        const options = Array.from(select.options).filter(option => !option.hidden && !(option.disabled && option.value === ''));
        if (!options.length) return;
        const menu = document.createElement('div');
        menu.id = id;
        menu.className = 'signup-dropdown-menu';
        menu.setAttribute('role', 'listbox');
        menu.setAttribute('aria-label', select.getAttribute('aria-label') || select.parentElement.querySelector('label')?.textContent || select.name);
        const style = getComputedStyle(select);
        menu.style.font = style.font;
        menu.style.color = style.color;
        const rows = options.map((option, index) => {
            const row = document.createElement('div');
            row.id = `${id}-${index}`;
            row.className = `signup-dropdown-option ${option.className}`;
            row.textContent = option.textContent;
            row.title = option.textContent;
            row.setAttribute('role', 'option');
            row.setAttribute('aria-selected', String(option.selected));
            row.setAttribute('aria-disabled', String(option.disabled));
            if (option.hasAttribute('aria-label')) row.setAttribute('aria-label', option.getAttribute('aria-label'));
            row.addEventListener('click', () => choose(index));
            menu.append(row);
            return row;
        });
        // Mount outside the cards so their overflow cannot clip the menu.
        document.body.append(menu);
        const rect = select.getBoundingClientRect();
        menu.style.left = `${rect.left}px`;
        menu.style.top = `${rect.bottom}px`;
        menu.style.width = `${rect.width}px`;
        menu.style.maxHeight = `${Math.min(rows[0].offsetHeight * 5 + 2, Math.max(0, window.innerHeight - rect.bottom))}px`;
        menu.addEventListener('pointerdown', event => {
            if (event.target.closest('.signup-dropdown-option')) event.preventDefault();
        });
        current = { select, menu, options, rows, active: -1, search: '', searchTime: 0 };
        select.setAttribute('aria-expanded', 'true');
        select.setAttribute('aria-controls', id);
        activate(options.findIndex(option => option.selected && !option.disabled));
        if (current.active < 0) activate(options.findIndex(option => !option.disabled));
    };

    selects.forEach((select, index) => {
        const id = `signup-dropdown-${index}`;
        select.setAttribute('aria-haspopup', 'listbox');
        select.setAttribute('aria-expanded', 'false');
        select.addEventListener('pointerdown', event => {
            if (event.button !== 0 || select.disabled) return;
            event.preventDefault();
            select.focus({ preventScroll: true });
            if (current?.select === select) close();
            else open(select, id);
        });
        // Also support activation dispatched by assistive technology.
        select.addEventListener('click', event => {
            event.preventDefault();
            if (event.detail === 0 && !current) open(select, id);
        });
        select.addEventListener('keydown', event => {
            if (event.key === 'Tab' || event.key === 'Escape') {
                if (event.key === 'Escape' && current) event.preventDefault();
                close();
                return;
            }
            const navigation = ['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', ' '];
            const typing = event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey;
            if (!navigation.includes(event.key) && !typing) return;
            event.preventDefault();
            const wasOpen = current?.select === select;
            if (!wasOpen) open(select, id);
            if (!current) return;
            if (event.key === 'Enter' || event.key === ' ') {
                if (wasOpen) choose(current.active);
            } else if (navigation.includes(event.key)) {
                const enabled = current.options.map((option, i) => option.disabled ? -1 : i).filter(i => i >= 0);
                let position = enabled.indexOf(current.active);
                if (event.key === 'Home') position = 0;
                else if (event.key === 'End') position = enabled.length - 1;
                else if (wasOpen) position += event.key === 'ArrowDown' ? 1 : -1;
                activate(enabled[Math.max(0, Math.min(enabled.length - 1, position))] ?? -1);
            } else {
                const now = Date.now();
                current.search = (now - current.searchTime < 700 ? current.search : '') + event.key.toLowerCase();
                current.searchTime = now;
                activate(current.options.findIndex(option => !option.disabled && option.textContent.trim().toLowerCase().startsWith(current.search)));
            }
        });
        select.addEventListener('blur', close);
        select.addEventListener('change', close);
        new MutationObserver(() => {
            if (current?.select === select) close();
        }).observe(select, { childList: true, subtree: true, attributes: true, attributeFilter: ['disabled', 'label', 'value', 'selected', 'hidden'] });
    });

    document.addEventListener('pointerdown', event => {
        if (current && event.target !== current.select && !current.menu.contains(event.target)) close();
    });
    window.addEventListener('resize', close);
    document.addEventListener('scroll', event => {
        if (current && event.target !== current.menu) close();
    }, true);
})();
