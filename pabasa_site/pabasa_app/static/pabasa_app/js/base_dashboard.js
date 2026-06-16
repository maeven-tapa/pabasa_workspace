/**
 * GLOBAL UTILITIES
 * These are defined at the very top and attached to window to prevent ReferenceErrors 
 * in inline scripts (like the dashboard page).
 */
var getStudentClassData = window.getStudentClassData = function() {
    let codes = [];
    try {
        codes = JSON.parse(localStorage.getItem("pabasaStudentClassCodes") || "[]");
        const legacy = localStorage.getItem("pabasaStudentClassCode");
        if (legacy && !codes.some(c => String(c).toUpperCase() === String(legacy).toUpperCase())) codes.push(legacy);
    } catch(e) {
        const legacy = localStorage.getItem("pabasaStudentClassCode");
        if (legacy) codes = [legacy];
    }
    return [...new Set(codes.filter(Boolean).map(c => String(c).toUpperCase()))];
};

/**
 * THEME INITIALIZATION & READER STYLES
 * Ensures the dark theme is applied immediately to prevent UI flashing and 
 * provides robust styles for reading/practice interfaces.
 */
(function() {
    let theme = localStorage.getItem("pabasa_theme");
    try { theme = JSON.parse(theme); } catch(e) {}

    if (theme === "dark") {
        document.documentElement.classList.add("dark-theme");
    }

    const applyBodyTheme = () => {
        let t = localStorage.getItem("pabasa_theme");
        try { t = JSON.parse(t); } catch(e) {}
        if (t === "dark") {
            document.body.classList.add("dark-theme");
        }
    };

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", applyBodyTheme);
    else applyBodyTheme();

    // Global listener to sync theme changes across tabs and within the current page
    const syncTheme = () => {
        let currentTheme = localStorage.getItem("pabasa_theme");
        try { currentTheme = JSON.parse(currentTheme); } catch(e) {}
        const isDark = currentTheme === "dark";
        document.documentElement.classList.toggle("dark-theme", isDark);
        document.body.classList.toggle("dark-theme", isDark);
    };

    window.addEventListener("storage", (e) => {
        if (e.key === "pabasa_theme") syncTheme();
    });

    window.addEventListener("pabasa:preferences-updated", () => {
        syncTheme();
    });

    const style = document.createElement('style');
    style.textContent = `
        /* Global Dark Mode Overrides */
        body.dark-theme {
            background-color: #0f172a !important;
            background-image: none !important;
            color: #f8fafc !important;
        }
        /* Specialized Reader UI (Word, Sentence, Paragraph) Overrides */
        body.dark-theme .reader-shell, 
        body.dark-theme .practice-shell,
        body.dark-theme .reader-background,
        body.dark-theme .reader-container {
            background: #0f172a !important;
            background-image: none !important;
            color: #f8fafc !important;
        }
        body.dark-theme .reader-card, 
        body.dark-theme .completion-card, 
        body.dark-theme .practice-card,
        body.dark-theme .reader-start-screen {
            background: #1e293b !important;
            border-color: rgba(255, 255, 255, 0.1) !important;
            backdrop-filter: blur(12px) !important;
            color: #f8fafc !important;
        }
        body.dark-theme #readingWord, 
        body.dark-theme #practiceText, 
        body.dark-theme .reading-text-display, 
        body.dark-theme .word-display {
            color: #ffffff !important;
        }
        body.dark-theme .pause-menu-content, 
        body.dark-theme .reader-pause-menu,
        body.dark-theme .pause-menu {
            background: #1e293b !important;
            color: #f8fafc !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
        }
        body.dark-theme .modal-content {
            background-color: #1e293b !important;
            color: #f8fafc !important;
        }
        body.dark-theme .reader-controls, 
        body.dark-theme .reader-footer,
        body.dark-theme .reader-header {
            background: #0f172a !important;
            border-top: 1px solid rgba(255, 255, 255, 0.1) !important;
        }
        body.dark-theme .btn-outline-dark {
            border-color: rgba(255, 255, 255, 0.2) !important;
            color: #f1f5f9 !important;
        }
        body.dark-theme .btn-outline-dark:hover {
            background: rgba(255, 255, 255, 0.05) !important;
            color: #fff !important;
        }
        body.dark-theme .progress {
            background-color: rgba(255, 255, 255, 0.1) !important;
        }
        body.dark-theme .text-secondary, body.dark-theme .text-muted {
            color: #94a3b8 !important;
        }
        body.dark-theme #testMeta, 
        body.dark-theme #counter, 
        body.dark-theme #practiceCounter,
        body.dark-theme .reader-meta {
            color: #cbd5e1 !important;
        }
        body.dark-theme #pauseOverlay {
            background: rgba(0, 0, 0, 0.7) !important;
        }
        body.dark-theme .completion-card h1, body.dark-theme .completion-card h2 {
            color: #f8fafc !important;
        }
    `;
    document.head.appendChild(style);
})();

(function () {
    function getRole() {
        let role = (window.PABASA_USER_ROLE || window.localStorage.getItem('pabasaUserRole') || '').toLowerCase();
        if (!role) {
            // Heuristic fallback: check the URL if variables haven't loaded yet
            const path = window.location.pathname;
            if (path.includes('/teacher/') || path.includes('/courses/')) role = 'teacher';
            else if (path.includes('/admin/')) role = 'admin';
        }
        // Persist found role for reliability on subsequent loads
        if (role && role !== window.localStorage.getItem('pabasaUserRole')) {
            window.localStorage.setItem('pabasaUserRole', role);
        }
        return role;
    }

    function updateTeacherSidebar(overrideCode = null) {
        const role = getRole();
        if (role !== 'teacher' && role !== 'admin') return;

        // Determine the best available class code
        let code = overrideCode || localStorage.getItem("pabasa_last_active_class_code");
        if (!code) {
            const activeCodeEl = document.getElementById('activeClassCode');
            if (activeCodeEl && activeCodeEl.textContent !== '—') code = activeCodeEl.textContent.trim();
        }

        if (!code || code === '—') return;

        // Target all possible management links (Sidebar, Quick Links, Workspace Buttons)
        const targets = document.querySelectorAll('#sidebarClassLink, #quickLinkClass, #manageClassLink, .btn-class-manage');
        targets.forEach(link => {
            link.href = `/dashboard/teacher/manage/?code=${code}`;
        });
    }

    // Ensure sidebar is updated on page load
    function initSidebarLink() {
        // Persist session-injected user info to localStorage for background scripts
        if (window.PABASA_USER_ROLE) localStorage.setItem("pabasaUserRole", window.PABASA_USER_ROLE);
        if (window.PABASA_USER_EMAIL) localStorage.setItem("pabasaUserEmail", window.PABASA_USER_EMAIL);
        if (window.PABASA_USER_NAME) localStorage.setItem("pabasaUserName", window.PABASA_USER_NAME);
        updateTeacherSidebar();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSidebarLink);
    } else {
        initSidebarLink();
    }

    // Listen for class selection events from other scripts
    window.addEventListener("pabasa:teacher-class-selected", function() {
        updateTeacherSidebar();
    });

    /**
     * Global Toast Notification Function
     * Displays a small, temporary notification at the top-right of the screen.
     * @param {string} message The message to display.
     * @param {'success'|'error'|'info'|'warning'} type The type of toast (determines color and icon).
     * @param {number} duration How long the toast should be visible in milliseconds.
     */
    window.showToast = function(message, type = "info", duration = 3000) {
        let toastContainer = document.getElementById("pabasaToastContainer");
        if (!toastContainer) {
            toastContainer = document.createElement("div");
            toastContainer.id = "pabasaToastContainer";
            toastContainer.className = "toast-container position-fixed top-0 end-0 p-3";
            toastContainer.style.zIndex = "9999";
            document.body.appendChild(toastContainer);
        }

        const toastId = "toast-" + Date.now();
        const bgClass = type === "success" ? "bg-success" : type === "error" ? "bg-danger" : type === "warning" ? "bg-warning text-dark" : "bg-info";
        const iconClass = type === "success" ? "bi-check-circle" : type === "error" ? "bi-exclamation-circle" : type === "warning" ? "bi-exclamation-triangle" : "bi-info-circle";
        
        const html = `
            <div id="${toastId}" class="toast align-items-center text-white ${bgClass} border-0 shadow" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="bi ${iconClass} me-2"></i>
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `;
        
        toastContainer.insertAdjacentHTML('beforeend', html);
        const toastEl = document.getElementById(toastId);
        
        if (window.bootstrap && bootstrap.Toast) {
            const bsToast = new bootstrap.Toast(toastEl, { delay: duration });
            bsToast.show();
            toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
        } else {
            toastEl.classList.add('show');
            setTimeout(() => toastEl.remove(), duration);
        }
    };

    /**
     * Global Dialog/Modal Function
     * Displays a centered acknowledgment modal with an icon and "OK" button.
     * @param {string} title The header of the dialog.
     * @param {string} message The body text (supports newlines).
     * @param {'success'|'error'|'info'|'warning'} type The type of dialog.
     */
    window.showDialog = function(title, message, type = "info") {
        if (!window.bootstrap || !bootstrap.Modal) {
            console.error("PABASA: Bootstrap Modal (bootstrap.Modal) not found. Cannot show custom dialog. Falling back to alert.");
            alert(title + "\n\n" + message);
            return;
        }
        const modalId = "dialog-" + Date.now();
        const iconMap = {
            success: "bi-check-circle-fill",
            error: "bi-exclamation-octagon-fill",
            info: "bi-info-circle-fill",
            warning: "bi-exclamation-triangle-fill"
        };
        const colorMap = {
            success: "#16a34a",
            error: "#dc3545",
            info: "#2ea8e5",
            warning: "#f59e0b"
        };
        
        const html = `
            <div class="modal fade" id="${modalId}" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog modal-dialog-centered" style="max-width: 400px;">
                    <div class="modal-content border-0 shadow-lg" style="border-radius: 28px; overflow: hidden;">
                        <div class="modal-body p-4 text-center">
                            <div class="mb-3" style="font-size: 3.5rem; color: ${colorMap[type] || colorMap.info};">
                                <i class="bi ${iconMap[type] || iconMap.info}"></i>
                            </div>
                            <h4 class="fw-bold mb-3" style="letter-spacing: -0.02em;">${title}</h4>
                            <div class="text-muted mb-4" style="font-size: 0.95rem; line-height: 1.6;">
                                ${message.replace(/\n/g, '<br>')}
                            </div>
                            <div class="d-grid">
                                <button type="button" class="btn btn-primary rounded-pill py-2 fw-bold" data-bs-dismiss="modal" style="letter-spacing: 0.02em;">OK</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', html);
        const modalEl = document.getElementById(modalId);
        const bsModal = new bootstrap.Modal(modalEl);
        bsModal.show();
        
        modalEl.addEventListener('hidden.bs.modal', () => modalEl.remove());
    };

    // Fetch authoritative stats and class info from server
    try {
        const role = getRole();
        if (role === 'teacher') {
            fetch('/dashboard/teacher/classes/', {
                method: 'GET',
                credentials: 'same-origin',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            }).then(async r => {
                if (!r.ok) {
                    const bodyText = await r.text();
                    console.error('Failed to fetch teacher classes, status', r.status, bodyText);
                    return;
                }

                // Read body once and attempt JSON.parse to avoid double-reading the stream
                const text = await r.text();
                let data = null;
                try {
                    data = JSON.parse(text || '{}');
                } catch (parseErr) {
                    console.error('Non-JSON response when fetching teacher classes (status ' + r.status + '):');
                    console.error(text);
                    return;
                }

                if (data && data.success && Array.isArray(data.classes)) {
                        const classCountEl = document.getElementById('classCount') || document.getElementById('classCountMirror');
                        if (classCountEl) classCountEl.textContent = String(data.classes.length);

                        // Update authoritative student count across all classes globally
                        const totalStudents = data.classes.reduce((sum, cls) => sum + (parseInt(cls.students) || 0), 0);
                        const studentCountEl = document.getElementById('studentCount') || document.getElementById('studentCountMirror') || document.getElementById('profileTotalStudentsCount') || document.getElementById('totalStudentsJoined');
                        if (studentCountEl) studentCountEl.textContent = String(totalStudents);

                        // If no class is currently active in storage, use the first one from the server
                        if (data.classes.length > 0 && !localStorage.getItem("pabasa_last_active_class_code")) {
                            localStorage.setItem("pabasa_last_active_class_code", data.classes[0].code);
                        }
                        updateTeacherSidebar(localStorage.getItem("pabasa_last_active_class_code"));

                        // Authoritative sync for stats cards
                        fetch('/dashboard/teacher/overview/')
                            .then(r => r.json())
                            .then(overviewData => {
                                if (overviewData.success) {
                                    const totalEl = document.getElementById('profileTotalStudentsCount') || document.getElementById('studentCountMirror') || document.getElementById('totalStudentsJoined');
                                    if (totalEl) totalEl.textContent = String(overviewData.total_students);
                                }
                            });
                    } else {
                        console.error('Unexpected JSON structure for teacher classes:', data);
                    }
            }).catch(function(error) {
                console.error('Error fetching teacher classes:', error);
            });
        } else if (role === 'student') {
            fetch('/api/student/classes/', {
                method: 'GET',
                credentials: 'same-origin',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            }).then(r => r.json()).then(async function(data) {
                if (data && data.success && Array.isArray(data.classes)) {
                    const studentClassCodes = data.classes.map(cls => cls.code);
                    localStorage.setItem("pabasaStudentClassCodes", JSON.stringify(studentClassCodes));
                    localStorage.setItem("pabasa_student_joined_classes", JSON.stringify(data.classes));
                    localStorage.setItem("pabasaStudentClassJoined", studentClassCodes.length > 0 ? "1" : "0");

                    // Update class metadata to ensure names are available for dynamic alerts
                    const metadata = JSON.parse(localStorage.getItem("pabasa_class_metadata") || "{}");
                    data.classes.forEach(cls => {
                        metadata[cls.code.toUpperCase()] = { 
                            name: cls.name || "Reading Class", 
                            subject: cls.subject || "Reading" 
                        };
                    });
                    localStorage.setItem("pabasa_class_metadata", JSON.stringify(metadata));

                    // Fetch materials for each joined class to keep pabasa_class_readings up-to-date
                    const readings = {};
                    for (const cls of data.classes) {
                        try {
                            const materialResponse = await fetch(`/api/class/materials/?class_code=${encodeURIComponent(cls.code)}`);
                            const materialData = await materialResponse.json();
                            if (materialData.success) {
                                readings[cls.code.toUpperCase()] = materialData.materials;
                            }
                        } catch (e) {
                            console.error(`Error fetching materials for class ${cls.code}:`, e);
                        }
                    }
                    localStorage.setItem("pabasa_class_readings", JSON.stringify(readings));
                    
                    // Trigger updates for any components relying on these local storage keys
                    window.dispatchEvent(new CustomEvent('pabasa:student-class-updated', { bubbles: true }));
                    window.dispatchEvent(new Event('storage')); // Simulate storage event for other listeners
                }
            }).catch(function() {
                // ignore
            });
        }
    } catch (e) {
        // ignore
    }
})();

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

    // Accordion behavior for help sections: Opening one closes others
    const helpLinkBtns = helpPanel.querySelectorAll(".help-link-btn");
    helpLinkBtns.forEach(btn => {
        btn.addEventListener("click", function () {
            const targetId = this.getAttribute("aria-controls");
            const targetContent = document.getElementById(targetId);
            if (!targetContent) return;
            
            const isCurrentlyOpen = targetContent.style.display === "block";

            // Mutually exclusive: Close all other sections first
            helpPanel.querySelectorAll(".help-content").forEach(content => {
                content.style.display = "none";
            });

            // If the clicked one was previously closed, open it now
            if (!isCurrentlyOpen) {
                targetContent.style.display = "block";
            }
        });
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && document.body.classList.contains("help-panel-open")) {
            setHelpPanel(false);
        }
    });

    // Global Fix for "Blocked aria-hidden on an element because its descendant retained focus"
    // This ensures that when a modal hides, focus is removed from its internal elements
    document.addEventListener('hide.bs.modal', function (event) {
        if (document.activeElement && event.target.contains(document.activeElement)) {
            document.activeElement.blur();
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
        // Teachers and Admins should always bypass the "student class required" lock
        const userRole = (window.PABASA_USER_ROLE || window.localStorage.getItem('pabasaUserRole') || '').toLowerCase();
        if (userRole === 'teacher' || userRole === 'admin') return true;

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
                
                // Only restore href from lockedHref for students. 
                // Teachers/Admins manage dynamic URLs (like class codes) in their own scripts,
                // so we don't want to overwrite their specific URLs.
                const userRole = (window.PABASA_USER_ROLE || window.localStorage.getItem('pabasaUserRole') || '').toLowerCase();
                const isStaff = userRole === 'teacher' || userRole === 'admin';
                if (!isStaff || !link.getAttribute("href") || link.getAttribute("href") === "#") {
                    link.setAttribute("href", targetHref);
                }
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
    /**
     * Checks for scheduled materials that have reached their scheduled time.
     * If a material just became active, it adds a notification for the student.
     */
    function checkScheduledNotifications() {
        const userRole = window.PABASA_USER_ROLE || window.localStorage.getItem("pabasaUserRole");
        if (userRole !== "student") return;

        const isJoined = window.localStorage.getItem("pabasaStudentClassJoined") === "1";
        if (!isJoined) return;

        const studentCodes = getStudentClassData();
        const readings = JSON.parse(localStorage.getItem("pabasa_class_readings") || "{}");
        const readingsMap = {};
        Object.keys(readings).forEach(key => readingsMap[key.toUpperCase()] = readings[key]);

        const metadata = JSON.parse(localStorage.getItem("pabasa_class_metadata") || "{}");
        const metadataMap = {};
        Object.keys(metadata).forEach(key => metadataMap[key.toUpperCase()] = metadata[key]);

        const notifiedIds = JSON.parse(localStorage.getItem("pabasa_notified_scheduled_ids") || "[]");
        let notificationsAdded = false;

        studentCodes.forEach(code => {
            const classData = readingsMap[code];
            if (!classData) return;

            const classInfo = metadataMap[code] || {};
            const className = classInfo.name || "Reading Class";

            ['word', 'sentence', 'paragraph', 'story'].forEach(type => {
                const keys = [type, type + 's', type === 'story' ? 'stories' : null].filter(Boolean);
                keys.forEach(key => {
                    (classData[key] || []).forEach(m => {
                        if (!m || m.status !== 'scheduled' || !m.schedule) return;
                        
                        const mId = (m.id !== undefined && m.id !== null) ? String(m.id).trim() : null;
                        if (!mId || notifiedIds.includes(mId)) return;

                        if (new Date(m.schedule).getTime() <= Date.now()) {
                            const studentName = window.PABASA_USER_NAME || window.localStorage.getItem("pabasaUserName") || "Student";
                            const notifications = JSON.parse(localStorage.getItem('pabasa_notifications') || '[]');
                            notifications.unshift({
                                id: Date.now() + Math.random(),
                                classCode: code,
                                title: `🔔 ${className} has a new reading: "${m.title || 'New Reading'}"`,
                                message: `Hello ${studentName},\n\nA new reading material has just been added to PABASA and is ready for you to explore!\n\nTitle: ${m.title || 'New Reading'}\n\nTake a few moments to log in and check it out. Every word you read helps you build confidence,\nimprove your skills, and discover something new.\n\nHappy reading, and enjoy learning with PABASA!\n\nWarm regards,\n\nThe PABASA Team`,
                                timestamp: Date.now(),
                                read: false,
                                role: 'student',
                                action_url: (m.type === 'assessment' || m.type === 'both') ? '/dashboard/assessment/' : '/dashboard/practice/'
                            });
                            localStorage.setItem('pabasa_notifications', JSON.stringify(notifications.slice(0, 100)));
                            notifiedIds.push(mId);
                            notificationsAdded = true;
                        }
                    });
                });
            });
        });

        if (notificationsAdded) {
            localStorage.setItem("pabasa_notified_scheduled_ids", JSON.stringify(notifiedIds));
            window.dispatchEvent(new Event('pabasa:notifications-updated'));
            // Real-time: trigger email sync immediately without waiting for interval
            if (typeof syncNotificationToEmail === 'function') syncNotificationToEmail();
        }
    }

    /**
     * Checks for new students who have joined a teacher's class.
     * If a new student is detected, it adds a notification for the teacher.
     */
    function checkStudentJoinNotifications() {
        const userRole = window.PABASA_USER_ROLE || window.localStorage.getItem("pabasaUserRole");
        if (userRole !== "teacher") return;

        const students = JSON.parse(localStorage.getItem("pabasa_added_students") || "[]");
        const notifiedStudentIds = JSON.parse(localStorage.getItem("pabasa_notified_student_ids") || "[]");
        let notificationsAdded = false;

        students.forEach(student => {
            const sId = student.id ? String(student.id) : null;
            if (!sId || notifiedStudentIds.includes(sId)) return;

            const notifications = JSON.parse(localStorage.getItem('pabasa_notifications') || '[]');
            notifications.unshift({
                id: Date.now() + Math.random(),
                classCode: student.class || "General",
                                title: "📚 Student Joined a Class",
                                message: `• ${student.name} joined ${student.class || "your class"}.`,
                timestamp: Date.now(),
                read: false,
                role: 'teacher'
            });
            localStorage.setItem('pabasa_notifications', JSON.stringify(notifications.slice(0, 100)));
            notifiedStudentIds.push(sId);
            notificationsAdded = true;
        });

        if (notificationsAdded) {
            localStorage.setItem("pabasa_notified_student_ids", JSON.stringify(notifiedStudentIds));
            window.dispatchEvent(new Event('pabasa:notifications-updated'));
            // Real-time: trigger email sync immediately
            if (typeof syncNotificationToEmail === 'function') syncNotificationToEmail();
        }
    }

    // Sidebar Badge Logic for Reading Materials
    function updateSidebarBadges() {
        // Preference Sync: Check if In-App alerts are enabled
        const username = (window.PABASA_USER_NAME || window.localStorage.getItem("pabasaUserName") || "user").toLowerCase().replace(/ /g, "_");
        const settings = JSON.parse(localStorage.getItem("pabasa_profile_settings_" + username) || "{}");
        const pushEnabled = settings.pushNotifications !== false;

        // If push is disabled, hide all notification markers immediately
        if (!pushEnabled) {
            updateLinkBadge('/dashboard/practice', 0);
            updateLinkBadge('/dashboard/assessment', 0);
            updateLinkBadge('/dashboard/notifications', 0);
            return;
        }

        checkScheduledNotifications();
        checkStudentJoinNotifications();

        const isStudent = window.localStorage.getItem("pabasaStudentClassJoined") === "1";
        if (!isStudent) return;

        const studentCodes = getStudentClassData();

        const readings = JSON.parse(localStorage.getItem("pabasa_class_readings") || "{}");
        // Normalize readings map for case-insensitive class code lookups
        const readingsMap = {};
        Object.keys(readings).forEach(key => {
            readingsMap[key.toUpperCase()] = readings[key];
        });

        const seenIds = JSON.parse(localStorage.getItem("pabasa_seen_material_ids") || "[]").map(id => String(id).trim());

        const unreadPractice = new Set();
        const unreadAssessment = new Set();
        const unreadGeneralNotifications = new Set(); // New set for general notifications

        studentCodes.forEach(code => {
            const upperCode = String(code).toUpperCase();
            const classData = readingsMap[upperCode];
            if (!classData) return;

            ['word', 'sentence', 'paragraph', 'story'].forEach(type => {
                // Check both singular and plural keys (e.g., 'word' and 'words')
                const keys = [type, type + 's', type === 'story' ? 'stories' : null, 'item_type'].filter(Boolean);
                keys.forEach(key => {
                    (classData[key] || []).forEach(m => {
                        if (!m) return;
                        // Filter by visibility/status
                        let isLive = !m.status || m.status === 'published';
                        if (m.status === 'scheduled' && m.schedule) {
                            isLive = new Date(m.schedule).getTime() <= Date.now();
                        }
                        if (!isLive) return;

                        const mId = (m.id !== undefined && m.id !== null) ? String(m.id).trim() : null;
                        if (mId && seenIds.includes(mId)) return;

                        const mType = (m.type || "").toLowerCase();
                        if (mType === 'practice' || mType === 'both') if (mId) unreadPractice.add(mId);
                        if (mType === 'assessment' || mType === 'both') if (mId) unreadAssessment.add(mId);
                    });
                });
            });
        });

        // Count unread general notifications for the current user's role
        const notifications = JSON.parse(localStorage.getItem('pabasa_notifications') || '[]');
        const currentUserRole = window.PABASA_USER_ROLE || window.localStorage.getItem("pabasaUserRole") || (isStudent ? 'student' : 'teacher'); 
        notifications.forEach(n => {
            if (!n.read && n.role === currentUserRole) {
                unreadGeneralNotifications.add(n.id);
            }
        });

        // Using robust path matching without trailing slashes
        updateLinkBadge('/dashboard/practice', unreadPractice.size);
        updateLinkBadge('/dashboard/assessment', unreadAssessment.size);
        updateLinkBadge('/dashboard/notifications', unreadGeneralNotifications.size); // Update badge for general notifications
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

    // REAL-TIME: Check for updates every 5 seconds
    setInterval(updateSidebarBadges, 5000);

    window.addEventListener("storage", function (event) {
        const badgeKeys = ['pabasa_class_readings', 'pabasa_seen_material_ids', 'pabasaStudentClassCodes'];
        if (badgeKeys.includes(event.key)) {
            updateSidebarBadges();
        }
        // Trigger email sync if notifications are updated from another tab
        if (event.key === 'pabasa_notifications') {
            window.dispatchEvent(new Event('pabasa:notifications-updated'));
        }
    });

    window.addEventListener("pabasa:student-class-updated", updateSidebarBadges);
    window.addEventListener("pabasa:notifications-updated", updateSidebarBadges); // Listen for general notification updates
    window.addEventListener("pabasa:preferences-updated", updateSidebarBadges); // Refresh badges when settings change
    window.addEventListener("studentAdded", checkStudentJoinNotifications); // Immediate check for teachers
})();

(function () {
    /**
     * GLOBAL MATERIAL STATUS SYNC
     * Automatically marks cards as "Done" across all student dashboards (Practice, Assessment, Course View)
     */
    function markCompletedMaterials() {
        const seenIds = JSON.parse(localStorage.getItem("pabasa_seen_material_ids") || "[]").map(id => String(id).trim());
        if (seenIds.length === 0) return;

        // Find any element with data-material-id (used in both practice and assessment cards)
        const cards = document.querySelectorAll('[data-material-id]');
        cards.forEach(card => {
            const mId = String(card.dataset.materialId).trim();
            if (seenIds.includes(mId)) {
                // Apply visual completion states
                card.classList.add('is-done', 'material-card-done');
                
                // Add "DONE" badge if heading exists and badge is missing
                const titleContainer = card.querySelector('h3, h4, h5, h6, strong, .type-info strong');
                if (titleContainer && !card.querySelector('.badge-done-marker')) {
                    const badge = document.createElement('span');
                    badge.className = 'badge bg-success ms-2 badge-done-marker';
                    badge.style.fontSize = '0.62rem';
                    badge.style.padding = '0.25em 0.5em';
                    badge.textContent = 'DONE';
                    titleContainer.appendChild(badge);
                }

                // Update icons and action buttons
                const icon = card.querySelector('.bi-play-circle-fill, .bi-play-fill, .bi-play');
                if (icon) {
                    icon.className = 'bi bi-check-circle-fill text-success ms-auto';
                }
                
                const btn = card.querySelector('button, .btn');
                if (btn && (btn.textContent.trim() === 'Start' || btn.textContent.trim() === 'Begin')) {
                    btn.textContent = 'Review';
                    btn.classList.replace('btn-primary', 'btn-outline-success');
                }
            }
        });
    }

    // Ensure "Done" styles are available globally
    function injectGlobalStyles() {
        if (document.getElementById('pabasa-global-done-css')) return;
        const style = document.createElement('style');
        style.id = 'pabasa-global-done-css';
        style.textContent = `
            .material-card-done, .assessment-type-link.is-done {
                background: #f0fdf4 !important;
                border-color: rgba(22, 163, 74, 0.2) !important;
                opacity: 0.95;
            }
            .material-card-done:hover, .assessment-type-link.is-done:hover {
                box-shadow: 0 4px 15px rgba(22, 163, 74, 0.1) !important;
            }
        `;
        document.head.appendChild(style);
    }

    // Initialize and listen for updates
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => { injectGlobalStyles(); markCompletedMaterials(); });
    } else {
        injectGlobalStyles();
        markCompletedMaterials();
    }
    window.addEventListener('focus', markCompletedMaterials);
    window.addEventListener('pabasa:student-class-updated', markCompletedMaterials);
    window.addEventListener('storage', (e) => { if (e.key === 'pabasa_seen_material_ids') markCompletedMaterials(); });
})();

(function () {
    /**
     * Notification to Email Sync
     * Monitors in-app alerts and mirrors them to the student's email if preferences allow.
     */
    async function syncNotificationToEmail() {
        const userRole = window.PABASA_USER_ROLE || window.localStorage.getItem("pabasaUserRole") || (window.localStorage.getItem("pabasaStudentClassJoined") === "1" ? 'student' : 'teacher');
        if (!userRole) return;

        const notifications = JSON.parse(localStorage.getItem('pabasa_notifications') || '[]');
        if (!notifications.length) return;

        // Filter for notifications meant for the current user OR notifications with an explicit recipientEmail
        const unsentNotifications = notifications.filter(n => (n.role === userRole || n.recipientEmail) && !n.emailSent);
        if (unsentNotifications.length === 0) return;

        // Check user preferences (works for both Teacher and Student)
        const username = (window.PABASA_USER_NAME || window.localStorage.getItem("pabasaUserName") || "user").toLowerCase().replace(/ /g, "_");
        const settings = JSON.parse(localStorage.getItem("pabasa_profile_settings_" + username) || "{}");
        if (settings.emailNotifications === false) return;

        const csrfToken =
            document.cookie
                .split('; ')
                .find(row => row.startsWith('csrftoken='))
                ?.split('=')[1];
        let notificationsUpdated = false;

        for (const notification of unsentNotifications) {
            const email = notification.recipientEmail || window.PABASA_USER_EMAIL || window.localStorage.getItem("pabasaUserEmail");
            if (!email) continue;

            try {
                // Always use the absolute path /students/send-email/ to avoid 404 relative path errors
                const response = await fetch('/students/send-email/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken || ""
                    },
                    body: JSON.stringify({
                        email: email,
                        subject: notification.title || "PABASA Alert",
                        message: notification.message
                    })
                });

                if (response.ok) {
                    notification.emailSent = true;
                    notificationsUpdated = true;
                    console.log(`PABASA: Email alert "${notification.title}" synced successfully.`);
                } else {
                    console.error("PABASA: Email sync failed for", notification.title, "Status:", response.status);
                }
            } catch (e) {
                console.error("PABASA: Network error syncing notification:", e);
            }
        }

        if (notificationsUpdated) {
            localStorage.setItem('pabasa_notifications', JSON.stringify(notifications));
        }
    }

    /**
     * Weekly Digest Sync
     * Compiles activity from the last 7 days and sends a summary email if preferences allow.
     */
    async function syncWeeklyDigest() {
        const userRole = window.PABASA_USER_ROLE || window.localStorage.getItem("pabasaUserRole") || (window.localStorage.getItem("pabasaStudentClassJoined") === "1" ? 'student' : 'teacher');
        if (!userRole) return;

        const username = (window.PABASA_USER_NAME || window.localStorage.getItem("pabasaUserName") || "user").toLowerCase().replace(/ /g, "_");
        const settings = JSON.parse(localStorage.getItem("pabasa_profile_settings_" + username) || "{}");
        
        // Only proceed if Weekly Digest is enabled in preferences
        if (settings.weeklyDigest !== true) return;

        const email = window.PABASA_USER_EMAIL || window.localStorage.getItem("pabasaUserEmail");
        if (!email) return;

        const lastSentKey = "pabasa_last_digest_sent_" + username;
        const lastSent = parseInt(localStorage.getItem(lastSentKey) || "0");
        const now = Date.now();
        const weekInMs = 7 * 24 * 60 * 60 * 1000;

        // Check if at least a week has passed since the last digest was sent
        if (now - lastSent < weekInMs) return;

        const notifications = JSON.parse(localStorage.getItem('pabasa_notifications') || '[]');
        // Filter notifications for the current user role from the past 7 days
        const weeklyNotifs = notifications.filter(n => n.role === userRole && n.timestamp > (now - weekInMs));

        if (weeklyNotifs.length === 0) return;

        const summaryList = weeklyNotifs.slice(0, 10).map(n => `- ${n.title}: ${n.message}`).join('\n');
        const message = `Hello ${window.PABASA_USER_NAME},\n\nHere is your PABASA weekly activity summary:\n\n${summaryList}${weeklyNotifs.length > 10 ? '\n... and more in your dashboard.' : ''}\n\nKeep up the great progress!\n\nThank you,\nThe PABASA Team`;

        try {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
            const response = await fetch('/students/send-email/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken || ""
                },
                body: JSON.stringify({
                    email: email,
                    subject: "Your Weekly PABASA Digest",
                    message: message
                })
            });

            if (response.ok) {
                localStorage.setItem(lastSentKey, now.toString());
                console.log("PABASA: Weekly digest sent successfully.");
            }
        } catch (e) {
            console.error("PABASA: Failed to sync weekly digest:", e);
        }
    }

    window.addEventListener('pabasa:notifications-updated', syncNotificationToEmail);
    window.addEventListener('pabasa:preferences-updated', syncNotificationToEmail); // Trigger immediate sync when settings change
    // Check on initial load
    syncNotificationToEmail();
    syncWeeklyDigest();
})();

/**
 * INPUT FORMATTING
 * Auto-dash for class code input (XXXX-000). 
 * Uses a ready-state check to ensure it attaches even if the page is already loaded.
 */
(function() {
    function initClassCodeInput() {
        const input = document.getElementById("classCode"); // Target the correct ID for the class code input
        if (!input || input.dataset.pabasaBound) return;
        
        input.dataset.pabasaBound = "true";
        let lastLen = 0;

        input.addEventListener("input", function (event) {
            let val = event.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
            let isDeleting = val.length < lastLen;
            lastLen = val.length;
            
            if (val.length > 4) {
                event.target.value = val.slice(0, 4) + '-' + val.slice(4, 7);
            } else if (val.length === 4 && !isDeleting) {
                event.target.value = val + '-';
            } else {
                event.target.value = val;
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initClassCodeInput);
    } else {
        initClassCodeInput();
    }
})();
