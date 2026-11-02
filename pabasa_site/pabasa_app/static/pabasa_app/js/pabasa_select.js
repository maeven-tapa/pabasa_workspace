/* Established Admin select interaction; optional auto-submit remains page-owned. */
        (function() {
            const enhancedSelects = new WeakMap();
            const openDropdowns = new Set();

            function shouldEnhanceSelect(select) {
                if (!select || enhancedSelects.has(select)) return false;
                if (!select.classList.contains('form-select')) return false;
                if (select.classList.contains('d-none')) return false;
                if (select.closest('.custom-device-dropdown')) return false;
                if (select.dataset.adminNativeSelect === 'true') return false;
                return true;
            }

            function setDropdownOpen(state, isOpen) {
                if (!state || (isOpen && state.trigger.disabled)) return;
                state.wrapper.classList.toggle('is-open', Boolean(isOpen));
                state.trigger.setAttribute('aria-expanded', Boolean(isOpen));
                if (isOpen) {
                    openDropdowns.forEach(function(openState) {
                        if (openState !== state) setDropdownOpen(openState, false);
                    });
                    openDropdowns.add(state);
                    state.wrapper.closest('.admin-panel, .card, .modal-content, .practice-filter-bar, .principal-table-card, form')?.classList.add('admin-custom-select-active');
                } else {
                    openDropdowns.delete(state);
                    state.wrapper.closest('.admin-panel, .card, .modal-content, .practice-filter-bar, .principal-table-card, form')?.classList.remove('admin-custom-select-active');
                }
            }

            function getSelectLabel(select) {
                const label = select.id ? document.querySelector(`label[for="${CSS.escape(select.id)}"]`) : null;
                return label ? label.textContent.trim() : (select.getAttribute('aria-label') || 'Select option');
            }

            function getSelectedOption(select) {
                return Array.from(select.options || []).find(function(option) {
                    return option.value === select.value;
                }) || select.options[select.selectedIndex] || select.options[0] || null;
            }

            function syncSelectState(state) {
                const selectedOption = getSelectedOption(state.select);
                const label = selectedOption ? (selectedOption.textContent || selectedOption.label || 'Select option').trim() : 'Select option';
                state.value.textContent = label;
                state.value.title = label;
                state.trigger.disabled = state.select.disabled;
                state.wrapper.classList.toggle('is-disabled', state.select.disabled);
                state.wrapper.classList.toggle('is-invalid', state.select.classList.contains('is-invalid'));
                state.options.forEach(function(button) {
                    const isSelected = button.dataset.value === state.select.value;
                    button.classList.toggle('is-selected', isSelected);
                    button.setAttribute('aria-selected', isSelected ? 'true' : 'false');
                });
                if (state.select.disabled) {
                    setDropdownOpen(state, false);
                }
            }

            function focusOptionByOffset(options, currentButton, offset) {
                const enabled = options.filter(function(option) { return !option.disabled; });
                if (!enabled.length) return;
                const currentIndex = Math.max(0, enabled.indexOf(currentButton));
                const nextIndex = (currentIndex + offset + enabled.length) % enabled.length;
                enabled[nextIndex]?.focus();
            }

            function rebuildOptions(state) {
                state.menu.replaceChildren();
                state.options = Array.from(state.select.options || []).map(function(option, index) {
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.className = 'custom-device-option';
                    button.setAttribute('role', 'option');
                    button.dataset.value = option.value || '';
                    button.dataset.index = String(index);
                    button.disabled = option.disabled;

                    const textWrap = document.createElement('span');
                    textWrap.className = 'custom-device-option-text';

                    const title = document.createElement('span');
                    title.className = 'custom-device-option-title';
                    title.textContent = (option.textContent || option.label || 'Select option').trim();
                    title.title = title.textContent;

                    const subtitle = document.createElement('span');
                    subtitle.className = 'custom-device-option-subtitle';
                    subtitle.textContent = option.disabled ? 'Unavailable' : 'Choose this option';

                    const check = document.createElement('i');
                    check.className = 'bi bi-check2 custom-device-check';
                    check.setAttribute('aria-hidden', 'true');

                    textWrap.append(title, subtitle);
                    button.append(textWrap, check);
                    state.menu.appendChild(button);
                    return button;
                });
                syncSelectState(state);
            }

            function enhanceSelect(select) {
                if (!shouldEnhanceSelect(select)) return;

                const wrapper = document.createElement('div');
                wrapper.className = 'custom-device-dropdown';
                wrapper.dataset.adminCustomSelect = 'true';
                wrapper.style.cssText = select.style.cssText || '';
                wrapper.style.pointerEvents = '';

                const trigger = document.createElement('button');
                trigger.type = 'button';
                trigger.className = 'custom-device-trigger';
                trigger.setAttribute('aria-haspopup', 'listbox');
                trigger.setAttribute('aria-expanded', 'false');
                trigger.setAttribute('aria-label', getSelectLabel(select));

                const textWrap = document.createElement('span');
                textWrap.className = 'custom-device-trigger-text';
                const value = document.createElement('span');
                value.className = 'custom-device-value';
                const icon = document.createElement('i');
                icon.className = 'bi bi-chevron-down';
                icon.setAttribute('aria-hidden', 'true');
                textWrap.appendChild(value);
                trigger.append(textWrap, icon);

                const menu = document.createElement('div');
                menu.className = 'custom-device-menu';
                menu.setAttribute('role', 'listbox');
                menu.setAttribute('aria-label', getSelectLabel(select));

                select.parentNode.insertBefore(wrapper, select);
                wrapper.append(trigger, select, menu);
                select.classList.add('custom-device-select');

                const state = { wrapper, trigger, value, menu, select, options: [], observer: null };
                enhancedSelects.set(select, state);
                rebuildOptions(state);

                trigger.addEventListener('click', function() {
                    setDropdownOpen(state, !wrapper.classList.contains('is-open'));
                    if (wrapper.classList.contains('is-open')) {
                        const target = state.options.find(function(option) { return option.classList.contains('is-selected') && !option.disabled; })
                            || state.options.find(function(option) { return !option.disabled; });
                        target?.focus();
                    }
                });

                trigger.addEventListener('keydown', function(event) {
                    if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        setDropdownOpen(state, true);
                        const target = state.options.find(function(option) { return option.classList.contains('is-selected') && !option.disabled; })
                            || state.options.find(function(option) { return !option.disabled; });
                        target?.focus();
                    } else if (event.key === 'Escape') {
                        setDropdownOpen(state, false);
                    }
                });

                menu.addEventListener('click', function(event) {
                    const button = event.target.closest('.custom-device-option');
                    if (!button || button.disabled || select.disabled) return;
                    select.value = button.dataset.value || '';
                    select.dispatchEvent(new Event('change', { bubbles: true }));
                    syncSelectState(state);
                    setDropdownOpen(state, false);
                    trigger.focus();
                });

                menu.addEventListener('keydown', function(event) {
                    const current = document.activeElement?.closest?.('.custom-device-option');
                    if (event.key === 'ArrowDown') {
                        event.preventDefault();
                        focusOptionByOffset(state.options, current, 1);
                    } else if (event.key === 'ArrowUp') {
                        event.preventDefault();
                        focusOptionByOffset(state.options, current, -1);
                    } else if (event.key === 'Home') {
                        event.preventDefault();
                        state.options.find(function(option) { return !option.disabled; })?.focus();
                    } else if (event.key === 'End') {
                        event.preventDefault();
                        state.options.slice().reverse().find(function(option) { return !option.disabled; })?.focus();
                    } else if (event.key === 'Escape') {
                        setDropdownOpen(state, false);
                        trigger.focus();
                    } else if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        current?.click();
                    }
                });

                select.addEventListener('change', function() {
                    syncSelectState(state);
                });

                select.addEventListener('invalid', function() {
                    trigger.focus();
                });

                state.observer = new MutationObserver(function() {
                    rebuildOptions(state);
                });
                state.observer.observe(select, {
                    attributes: true,
                    attributeFilter: ['disabled', 'class'],
                    childList: true,
                    subtree: true,
                    characterData: true
                });
            }

            function initAdminCustomSelects(root) {
                (root || document).querySelectorAll('select.form-select').forEach(enhanceSelect);
            }

            document.addEventListener('click', function(event) {
                openDropdowns.forEach(function(state) {
                    if (!state.wrapper.contains(event.target)) setDropdownOpen(state, false);
                });
            });

            window.pabasaInitAdminCustomSelects = initAdminCustomSelects;
            initAdminCustomSelects(document);

})();
