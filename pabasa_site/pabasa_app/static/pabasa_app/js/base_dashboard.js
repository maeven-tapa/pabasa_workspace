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
                link.classList.remove("is-locked");
                let targetHref = link.dataset.lockedHref;
                
                // Automatically append class code for classroom-specific links
                if (link.hasAttribute('data-append-class-code')) {
                    let primaryCode = null;
                    try {
                        const codes = JSON.parse(localStorage.getItem("pabasaStudentClassCodes") || "[]");
                        primaryCode = codes[0] || localStorage.getItem("pabasaStudentClassCode");
                    } catch(e) {
                        primaryCode = localStorage.getItem("pabasaStudentClassCode");
                    }

                    if (primaryCode) {
                        const separator = targetHref.includes('?') ? '&' : '?';
                        targetHref = `${targetHref}${separator}code=${primaryCode}`;
                    } else {
                        console.warn("PABASA Sidebar: Link requires class code but none found in localStorage.");
                    }
                }
                
                link.setAttribute("href", targetHref);
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
        const classKeys = [classJoinedKey, "pabasaStudentClassCode", "pabasaStudentClassCodes"];
        if (classKeys.includes(event.key)) {
            updateLockedLinks();
        }
    });

    window.addEventListener("pabasa:student-class-updated", updateLockedLinks);
})();

(function () {
    // Sidebar Badge Logic for Reading Materials
    function updateSidebarBadges() {
        const isStudent = window.localStorage.getItem("pabasaStudentClassJoined") === "1";
        if (!isStudent) return;

        let studentCodes = [];
        try {
            studentCodes = JSON.parse(localStorage.getItem("pabasaStudentClassCodes") || "[]");
            const legacy = localStorage.getItem("pabasaStudentClassCode");
            if (legacy && !studentCodes.includes(legacy)) studentCodes.push(legacy);
        } catch(e) {}

        const readings = JSON.parse(localStorage.getItem("pabasa_class_readings") || "{}");
        // Normalize readings map for case-insensitive class code lookups
        const readingsMap = {};
        Object.keys(readings).forEach(key => {
            readingsMap[key.toUpperCase()] = readings[key];
        });

        const seenIds = JSON.parse(localStorage.getItem("pabasa_seen_material_ids") || "[]").map(String);

        let practiceCount = 0;
        let assessmentCount = 0;

        studentCodes.forEach(code => {
            const upperCode = String(code).toUpperCase();
            const classData = readingsMap[upperCode];
            if (!classData) return;

            ['word', 'sentence', 'paragraph', 'story'].forEach(type => {
                // Check both singular and plural keys (e.g., 'word' and 'words')
                [type, type + 's'].forEach(key => {
                    (classData[key] || []).forEach(material => {
                        if (material && material.id && seenIds.includes(String(material.id))) return;

                        const mType = (material.type || "").toLowerCase();
                        if (mType === 'practice' || mType === 'both') practiceCount++;
                        if (mType === 'assessment' || mType === 'both') assessmentCount++;
                    });
                });
            });
        });

        updateLinkBadge('/dashboard/practice/', practiceCount);
        updateLinkBadge('/dashboard/assessment/', assessmentCount);
    }

    function updateLinkBadge(pathPart, count) {
        const link = document.querySelector(`.dashboard-sidebar .nav-link[href*="${pathPart}"], .dashboard-sidebar .nav-link[data-locked-href*="${pathPart}"]`);
        if (!link) return;

        let badge = link.querySelector('.badge-notif');
        if (count > 0) {
            if (!badge) {
                badge = document.createElement('span');
                badge.className = 'badge rounded-pill bg-danger badge-notif ms-auto';
                badge.style.fontSize = '0.65rem';
                link.appendChild(badge);
            }
            badge.textContent = count > 99 ? '99+' : count;
        } else if (badge) {
            badge.remove();
        }
    }

    updateSidebarBadges();

    window.addEventListener("storage", function (event) {
        const badgeKeys = ['pabasa_class_readings', 'pabasa_seen_material_ids', 'pabasaStudentClassCodes'];
        if (badgeKeys.includes(event.key)) {
            updateSidebarBadges();
        }
    });

    window.addEventListener("pabasa:student-class-updated", updateSidebarBadges);
})();
