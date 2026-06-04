(function () {
    // Initialize tooltips only for elements that don't require class lock
    const tooltipTargets = document.querySelectorAll("[data-nav-tooltip]:not([data-student-class-required])");
    tooltipTargets.forEach(function (item) {
        new bootstrap.Tooltip(item, {
            placement: "right",
            trigger: "hover focus",
            container: "body"
        });
    });
})();

(function () {
    const collapseBtn = document.querySelector(".dashboard-sidebar [data-sidebar-collapse-btn]");
    if (!collapseBtn) {
        return;
    }

    const key = "pabasaSidebarCollapsed";

    function setCollapsed(collapsed) {
        document.body.classList.toggle("sidebar-collapsed", collapsed);
        collapseBtn.setAttribute("title", collapsed ? "Expand sidebar" : "Collapse sidebar");
        collapseBtn.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
        collapseBtn.innerHTML = collapsed
            ? '<i class="bi bi-chevron-right"></i>'
            : '<i class="bi bi-chevron-left"></i>';
    }

    setCollapsed(window.localStorage.getItem(key) === "1");

    collapseBtn.addEventListener("click", function () {
        const next = !document.body.classList.contains("sidebar-collapsed");
        setCollapsed(next);
        window.localStorage.setItem(key, next ? "1" : "0");
    });
})();

(function () {
    const helpToggleBtn = document.querySelector("[data-help-toggle]");
    const helpCloseBtn = document.querySelector("[data-help-close]");
    const helpPanel = document.getElementById("helpPanel");

    if (!helpToggleBtn || !helpPanel) {
        return;
    }

    function setHelpPanel(open) {
        document.body.classList.toggle("help-panel-open", open);
        helpPanel.setAttribute("aria-hidden", open ? "false" : "true");
        helpToggleBtn.setAttribute("aria-expanded", open ? "true" : "false");
    }

    helpToggleBtn.addEventListener("click", function () {
        const next = !document.body.classList.contains("help-panel-open");
        setHelpPanel(next);
    });

    if (helpCloseBtn) {
        helpCloseBtn.addEventListener("click", function () {
            setHelpPanel(false);
        });
    }

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && document.body.classList.contains("help-panel-open")) {
            setHelpPanel(false);
        }
    });
})();

(function () {
    const lockedLinks = document.querySelectorAll("[data-student-class-required]");
    if (!lockedLinks.length) {
        return;
    }

    const classJoinedKey = "pabasaStudentClassJoined";

    function classIsJoined() {
        return window.localStorage.getItem(classJoinedKey) === "1";
    }

    // Store locked title and unlocked title from data attributes FIRST
    lockedLinks.forEach(function (link) {
        link.dataset.lockedTitle = link.getAttribute("title");
        link.dataset.unlockedTitle = link.getAttribute("data-unlocked-title");
    });

    function reinitializeTooltips() {
        // Dispose all existing tooltips
        lockedLinks.forEach(function (link) {
            const existingTooltip = bootstrap.Tooltip.getInstance(link);
            if (existingTooltip) {
                existingTooltip.hide();
                existingTooltip.dispose();
            }
        });
        
        // Remove all tooltip popper elements from the DOM
        document.querySelectorAll('[role="tooltip"]').forEach(function(el) {
            el.remove();
        });
        
        // Longer delay and then recreate
        setTimeout(function() {
            lockedLinks.forEach(function (link) {
                new bootstrap.Tooltip(link, {
                    placement: "right",
                    trigger: "hover focus",
                    container: "body"
                });
            });
        }, 150);
    }

    function updateLockedLinks() {
        const isJoined = classIsJoined();

        lockedLinks.forEach(function (link) {
            if (!link.dataset.lockedHref && link.getAttribute("href")) {
                link.dataset.lockedHref = link.getAttribute("href");
            }

            link.classList.toggle("is-locked", !isJoined);
            link.setAttribute("aria-disabled", isJoined ? "false" : "true");
            
            // Get the appropriate title based on join state
            const newTitle = isJoined ? link.dataset.unlockedTitle : link.dataset.lockedTitle;
            link.setAttribute("title", newTitle);

            if (isJoined) {
                link.setAttribute("href", link.dataset.lockedHref);
                link.removeAttribute("tabindex");
            } else {
                link.removeAttribute("href");
                link.setAttribute("tabindex", "-1");
            }
        });

        // Reinitialize tooltips after updating titles
        reinitializeTooltips();
    }

    // Setup click prevention for locked links
    lockedLinks.forEach(function (link) {
        link.addEventListener("click", function (event) {
            if (classIsJoined()) {
                return;
            }

            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
        }, true);
    });

    // Initial update
    updateLockedLinks();

    window.addEventListener("storage", function (event) {
        if (event.key === classJoinedKey) {
            updateLockedLinks();
        }
    });

    window.addEventListener("pabasa:student-class-updated", updateLockedLinks);
})();
