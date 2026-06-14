function initProfilePage() {
    // Ensure a minimal pabasaStore API exists to avoid runtime errors
    if (!window.pabasaStore || typeof window.pabasaStore.get !== 'function') {
        window.pabasaStore = {
            get: function (key, fallback) {
                try {
                    const v = localStorage.getItem(key);
                    if (v === null || v === undefined) return fallback;
                    return JSON.parse(v);
                } catch (e) {
                    try { return localStorage.getItem(key) || fallback; } catch (e2) { return fallback; }
                }
            },
            set: function (key, value) {
                try {
                    localStorage.setItem(key, JSON.stringify(value));
                } catch (e) {
                    try { localStorage.setItem(key, String(value)); } catch (e2) { /* ignore */ }
                }
            },
            remove: function (key) {
                try { localStorage.removeItem(key); } catch (e) { /* ignore */ }
            }
        };
    }
    const form = document.getElementById("accountDetailsForm");
    const editBtn = document.getElementById("editAccountDetailsBtn");
    const actions = document.getElementById("accountDetailsActions");
    const profilePhotoInput = document.getElementById("profilePhoto");
    const uploadPhotoBtn = document.getElementById("uploadPhotoBtn");
    const removePhotoBtn = document.getElementById("removePhotoBtn");
    const profileUsername = JSON.parse(document.getElementById("profileUsername")?.textContent || "\"user\"");
    const profileFullName = JSON.parse(document.getElementById("profileFullName")?.textContent || '""');
    const profileEmail = JSON.parse(document.getElementById("profileEmail")?.textContent || "\"\"");
    const profilePabasaId = JSON.parse(document.getElementById("profilePabasaId")?.textContent || "\"\"");
    const profileRoleDisplay = JSON.parse(document.getElementById("profileRoleDisplay")?.textContent || "\"\"");
    const profileStorageKey = "pabasa_profile_settings_" + profileUsername;

    const accountFields = form ? form.querySelectorAll("[data-account-details-field]") : [];

    // Theme Toggle Logic
    const themeToggle = document.getElementById("themeToggle");
    if (themeToggle) {
        const themeIcon = themeToggle.querySelector("i");
        const themeKey = "pabasa_theme";
        const updateThemeUI = (theme) => {
            if (theme === "dark") {
                document.documentElement.classList.add("dark-theme");
                document.body.classList.add("dark-theme");
                themeIcon.className = "bi bi-moon-stars";
            } else {
                document.documentElement.classList.remove("dark-theme");
                document.body.classList.remove("dark-theme");
                themeIcon.className = "bi bi-sun";
            }
        };
        updateThemeUI(window.pabasaStore.get(themeKey, "light"));
        themeToggle.addEventListener("click", () => {
            const isDark = document.body.classList.contains("dark-theme");
            const newTheme = isDark ? "light" : "dark";
            window.pabasaStore.set(themeKey, newTheme);
            updateThemeUI(newTheme);
            // Dispatch event so the assessment reader knows to adapt immediately
            window.dispatchEvent(new CustomEvent('pabasa:preferences-updated', { detail: { theme: newTheme } }));
        });
    }

    function setEditMode(editing) {
        accountFields.forEach(function (field) {
            field.disabled = !editing;
        });
        editBtn.classList.toggle("d-none", editing);
        actions.classList.toggle("d-none", !editing);
    }

    if (form && editBtn && actions) {
        setEditMode(false);

        editBtn.addEventListener("click", function () {
            setEditMode(true);
            const firstField = form.querySelector("[data-account-details-field]");
            if (firstField) {
                firstField.focus();
            }
        });

        form.addEventListener("reset", function () {
            setTimeout(function () {
                setEditMode(false);
            }, 0);
        });

        form.addEventListener("submit", function (event) {
            event.preventDefault();
            const submitBtn = form.querySelector("button[type='submit']");
            const originalText = submitBtn ? submitBtn.textContent : "";
            
            if (submitBtn) {
                submitBtn.textContent = "Saving...";
                submitBtn.disabled = true;
            }

            const fields = {
                first_name: document.getElementById("firstName")?.value || "",
                last_name: document.getElementById("lastName")?.value || "",
                middle_initial: document.getElementById("middleInitial")?.value || "",
                suffix: document.getElementById("suffix")?.value || "",
                email: document.getElementById("email")?.value || "",
                bio: document.getElementById("bio")?.value || ""
            };

            postProfileAction("save_account_details", fields).then(function (data) {
                if (!data.success) {
                    showToast(data.error || "Could not update profile", "error");
                    return;
                }

                showToast(data.message || "Profile updated successfully", "success");
                setEditMode(false);
                form.reset();
                
                // Update the display with new values
                const fullNameDisplay = document.querySelector(".profile-main-content h2");
                if (fullNameDisplay && data.full_name) {
                    fullNameDisplay.textContent = data.full_name;
                }
            }).catch(function (error) {
                showToast("Error updating profile: " + error.message, "error");
            }).finally(function () {
                if (submitBtn) {
                    submitBtn.textContent = originalText;
                    submitBtn.disabled = false;
                }
            });
        });
    }

    function showToast(message, type = "success") {
        let toastContainer = document.getElementById("pabasaToastContainer");
        if (!toastContainer) {
            toastContainer = document.createElement("div");
            toastContainer.id = "pabasaToastContainer";
            toastContainer.className = "toast-container position-fixed top-0 end-0 p-3";
            toastContainer.style.zIndex = "1090";
            document.body.appendChild(toastContainer);
        }

        const toastId = "toast-" + Date.now();
        const bgClass = type === "success" ? "bg-success" : type === "error" ? "bg-danger" : "bg-primary";
        const iconClass = type === "success" ? "bi-check-circle" : type === "error" ? "bi-exclamation-circle" : "bi-info-circle";
        
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
            const bsToast = new bootstrap.Toast(toastEl, { delay: 3000 });
            bsToast.show();
            toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
        } else {
            toastEl.classList.add('show');
            setTimeout(() => toastEl.remove(), 3000);
        }
    }

    function showProfileSuccessModal(title, message, type = "success") {
        const modalEl = document.getElementById("profileSuccessModal");
        const titleEl = document.getElementById("profileSuccessTitle");
        const messageEl = document.getElementById("profileSuccessMessage");
        const iconContainer = document.getElementById("profileModalIcon");
        const btnEl = document.getElementById("profileModalBtn");
        
        if (modalEl && titleEl && messageEl && iconContainer) {
            titleEl.textContent = title;
            messageEl.textContent = message;

            // Set icon and color based on type
            if (type === "success") {
                iconContainer.style.color = "#16a34a";
                iconContainer.innerHTML = '<i class="bi bi-check-circle-fill"></i>';
                if (btnEl) btnEl.textContent = "Perfect, thanks!";
            } else if (type === "info") {
                iconContainer.style.color = "#1fb6ff";
                iconContainer.innerHTML = '<i class="bi bi-info-circle-fill"></i>';
                if (btnEl) btnEl.textContent = "Got it";
            } else if (type === "error") {
                iconContainer.style.color = "#dc3545";
                iconContainer.innerHTML = '<i class="bi bi-exclamation-circle-fill"></i>';
                if (btnEl) btnEl.textContent = "Try again";
            }

            const modal = new bootstrap.Modal(modalEl);
            modal.show();
        } else {
            alert(message);
        }
    }

    function showProfileConfirmModal(title, message, confirmText, onConfirm) {
        const modalEl = document.getElementById("profileConfirmModal");
        const titleEl = document.getElementById("profileConfirmTitle");
        const messageEl = document.getElementById("profileConfirmMessage");
        const btnEl = document.getElementById("profileConfirmBtn");
        
        if (modalEl && titleEl && messageEl && btnEl) {
            titleEl.textContent = title;
            messageEl.textContent = message;
            btnEl.textContent = confirmText;
            
            // Clean up previous listeners and attach new one
            const newBtn = btnEl.cloneNode(true);
            btnEl.parentNode.replaceChild(newBtn, btnEl);
            
            newBtn.addEventListener("click", function() {
                bootstrap.Modal.getInstance(modalEl)?.hide();
                if (typeof onConfirm === "function") onConfirm();
            });

            const modal = new bootstrap.Modal(modalEl);
            modal.show();
        } else {
            if (confirm(message)) {
                if (typeof onConfirm === "function") onConfirm();
            }
        }
    }

    function getCsrfToken() {
        return document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
    }

    function postProfileAction(actionName, fields) {
        const formData = new FormData();
        formData.append(actionName, "true");
        formData.append("csrfmiddlewaretoken", getCsrfToken());
        Object.entries(fields || {}).forEach(function ([key, value]) {
            formData.append(key, value);
        });

        return fetch(window.location.pathname, {
            method: "POST",
            body: formData,
            credentials: "same-origin",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": getCsrfToken()
            }
        }).then(function (response) {
            return response.json();
        });
    }

    function getStoredValue(key, fallback) {
        return window.pabasaStore.get(key, fallback);
    }

    function getStoredArray(key) {
        const value = window.pabasaStore.get(key, []);
        return Array.isArray(value) ? value : [];
    }

    function countStoredCollection(key) {
        const value = window.pabasaStore.get(key, []);
        if (Array.isArray(value)) {
            return value.length;
        }
        if (value && typeof value === "object") {
            return Object.values(value).reduce(function (total, item) {
                return total + (Array.isArray(item) ? item.length : 1);
            }, 0);
        }
        return 0;
    }

    function countClassReadings() {
        const readingsByClass = getStoredValue("pabasa_class_readings", {});
        if (!readingsByClass || typeof readingsByClass !== "object" || Array.isArray(readingsByClass)) {
            return 0;
        }

        // Only count readings for classes that still appear in stored teacher classes
        const activeClassCodes = getStoredArray("pabasa_teacher_classes").map(function(c){
            try { return (c.code || c.class_code || "").toString().toUpperCase(); } catch (e) { return ""; }
        }).filter(Boolean);

        return Object.keys(readingsByClass).reduce(function (total, classCodeKey) {
            if (activeClassCodes.length > 0 && !activeClassCodes.includes(classCodeKey.toUpperCase())) {
                // skip readings for classes that are no longer active
                return total;
            }
            const readings = readingsByClass[classCodeKey];
            if (!readings || typeof readings !== "object") {
                return total;
            }
            return total + ["word", "sentence", "paragraph", "story"].reduce(function (typeTotal, type) {
                const sing = Array.isArray(readings[type]) ? readings[type].length : 0;
                const plur = Array.isArray(readings[type + "s"]) ? readings[type + "s"].length : 0;
                return typeTotal + sing + plur;
            }, 0);
        }, 0);
    }

    function getTeacherOverviewStats() {
        const sampleClassCodes = ["RRG-9154", "AFC-7302", "ESL-5601"];
        // Aggregate teacher classes from any pabasa_teacher_classes_{email} key for robustness
        const classes = (function() {
            try {
                const out = [];
                Object.keys(localStorage).forEach(function(key) {
                    if (!key || typeof key !== 'string') return;
                    if (key.startsWith('pabasa_teacher_classes')) {
                        try {
                            const parsed = JSON.parse(localStorage.getItem(key) || '[]');
                            if (Array.isArray(parsed)) {
                                parsed.forEach(function(c) { if (c && c.code && !sampleClassCodes.includes(c.code)) out.push(c); });
                            }
                        } catch (e) {
                            // ignore parse errors
                        }
                    }
                });
                return out;
            } catch (e) {

                const fieldMap = {
                    firstName: fields.first_name,
                    middleInitial: fields.middle_initial,
                    lastName: fields.last_name,
                    suffix: fields.suffix,
                    email: fields.email,
                    bio: fields.bio
                };

                Object.entries(fieldMap).forEach(function ([id, value]) {
                    if (value === undefined) return;
                    const element = document.getElementById(id);
                    if (!element) return;
                    element.value = value;
                    element.defaultValue = value;
                });

                return [];
            }
        })();
        const students = getStoredArray("pabasa_added_students").filter(function (student) {
            return student.name !== "Jay Park";
        });
        const storedStudentCount = students.length;
        const classStudentCount = classes.reduce(function (total, classData) {
            return total + (Number.parseInt(classData.students, 10) || 0);
        }, 0);
        const overviewStats = getStoredValue("pabasa_teacher_overview_stats", {});
        const storedMaterialsPosted = Number.parseInt(overviewStats.materialsPosted, 10) || 0;

        // Ensure flattened materials are also filtered to active classes
        const activeClassCodes = classes.map(function(c) { return (c.code || c.class_code || "").toString().toUpperCase(); }).filter(Boolean);
        const flattenedMaterials = getStoredArray("pabasa_materials").filter(function(m) {
            if (!m) return false;
            if (!m.classCode && !m.class) return true; // keep global materials
            const mCode = (m.classCode || m.class || "").toString().toUpperCase();
            return activeClassCodes.length === 0 || activeClassCodes.includes(mCode);
        });

        return {
            activeClasses: classes.length,
            totalStudents: Math.max(storedStudentCount, classStudentCount),
            materialsPosted: Math.max(countClassReadings(), countStoredCollection("pabasa_materials") /* fallback */, flattenedMaterials.length, storedMaterialsPosted),
            reportsGenerated: countStoredCollection("pabasa_parent_notice_history")
        };
    }

    function updateClassOverview() {
        const stats = getTeacherOverviewStats();
        const activeClassesCount = document.getElementById("profileActiveClassesCount");
        const totalStudentsCount = document.getElementById("profileTotalStudentsCount");
        const materialsPostedCount = document.getElementById("profileMaterialsPostedCount");
        const reportsGeneratedCount = document.getElementById("profileReportsGeneratedCount");

        if (activeClassesCount) activeClassesCount.textContent = String(stats.activeClasses);
        if (totalStudentsCount) totalStudentsCount.textContent = String(stats.totalStudents);
        if (materialsPostedCount) materialsPostedCount.textContent = String(stats.materialsPosted);
        if (reportsGeneratedCount) reportsGeneratedCount.textContent = String(stats.reportsGenerated);

        // If the current user is a teacher, request authoritative overview from the server
        try {
            const role = window.PABASA_USER_ROLE || window.localStorage.getItem('pabasaUserRole') || '';
            if (role === 'teacher') {
                fetch('/dashboard/teacher/overview/', {
                    method: 'GET',
                    credentials: 'same-origin',
                    headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
                }).then(function (r) {
                    if (!r.ok) {
                        console.warn('Teacher overview request failed', r.status, r.statusText);
                        return null;
                    }
                    const ct = r.headers.get('content-type') || '';
                    if (!ct.includes('application/json')) {
                        // Possibly redirected to login or an HTML error page
                        r.text().then(function (body) {
                            console.warn('Teacher overview returned non-JSON response', ct, body.substring(0, 200));
                        });
                        return null;
                    }
                    return r.json();
                }).then(function (data) {
                    if (!data) return;
                    if (!data.success) {
                        console.warn('Teacher overview returned error', data.error || data);
                        return;
                    }
                    if (activeClassesCount) activeClassesCount.textContent = String(data.classes_count || stats.activeClasses);
                    if (totalStudentsCount) totalStudentsCount.textContent = String(data.total_students || stats.totalStudents);
                    if (materialsPostedCount) materialsPostedCount.textContent = String(data.materials_posted || stats.materialsPosted);
                    if (reportsGeneratedCount) reportsGeneratedCount.textContent = String(data.reports_generated || stats.reportsGenerated);
                }).catch(function (err) {
                    console.warn('Network error fetching teacher overview', err);
                });
            }
        } catch (e) {
            // ignore
        }

        // Update Activity Status (Active, Inactive) for Teachers
        const teacherStatusDisplay = document.getElementById("profileTeacherStatus"); // Assuming this ID exists in HTML for teacher status
        if (teacherStatusDisplay) {
            const notifications = getStoredValue("pabasa_notifications", []);
            const lastActivity = notifications
                .filter(n => n.role === 'teacher') // Filter for teacher notifications
                .reduce((max, n) => Math.max(max, n.timestamp), 0); // Get the most recent timestamp

            let statusText = "Inactive";
            let statusClass = "bg-danger"; // Default for Inactive

            if (lastActivity > 0) {
                const diffDays = (Date.now() - lastActivity) / (1000 * 60 * 60 * 24);
                if (diffDays <= 7) {
                    statusText = "Active";
                    statusClass = "bg-success";
                }
            }
            teacherStatusDisplay.textContent = statusText;
            teacherStatusDisplay.className = "badge rounded-pill " + statusClass;
        }
    }

    function updateStudentProgress() {
        try {
            // Get class codes with case-insensitive deduplication
            const codesArray = getStoredArray("pabasaStudentClassCodes").map(c => String(c).toUpperCase());
            const legacyCode = window.pabasaStore.get("pabasaStudentClassCode");
            if (legacyCode && !codesArray.includes(legacyCode.toUpperCase())) {
                codesArray.push(legacyCode.toUpperCase());
            }
            const studentCodes = codesArray.filter(Boolean);

            const seenIds = getStoredArray("pabasa_seen_material_ids").map(id => String(id).trim());
            const readings = getStoredValue("pabasa_class_readings", {});
            
            // Build a normalized lookup map
            const readingsMap = {};
            Object.keys(readings).forEach(k => readingsMap[k.toUpperCase()] = readings[k]);

            let totalAvailable = 0;
            let completedCount = 0;

            studentCodes.forEach(code => {
                const classData = readingsMap[code];
                if (!classData) return;

                // Scan all possible material categories
                ['word', 'sentence', 'paragraph', 'story', 'all'].forEach(type => {
                    // Support both singular and plural keys
                    [type, type + 's'].forEach(key => {
                        const list = classData[key];
                        if (Array.isArray(list)) {
                            list.forEach(m => {
                                if (!m) return;
                                
                                // Check if material is live (published or scheduled time passed)
                                let isLive = !m.status || m.status === 'published';
                                if (m.status === 'scheduled' && m.schedule) {
                                    isLive = new Date(m.schedule).getTime() <= Date.now();
                                }
                                if (!isLive) return;

                                totalAvailable++;
                                const mId = (m.id !== undefined && m.id !== null) ? String(m.id).trim() : null;
                                if (mId && seenIds.includes(mId)) {
                                    completedCount++;
                                }
                            });
                        }
                    });
                });
            });

            const percentage = totalAvailable > 0 ? Math.min(100, Math.round((completedCount / totalAvailable) * 100)) : 0;

            // Update the UI elements
            const classesEl = document.getElementById("profileStudentClassesCount");
            const completedEl = document.getElementById("profileStudentCompletedCount");
            const percentEl = document.getElementById("profileStudentProgressPercent");

            // Correctly show the count of joined classes
            if (classesEl) classesEl.textContent = studentCodes.length;
            if (completedEl) completedEl.textContent = completedCount;
            if (percentEl) percentEl.textContent = percentage + "%";

            // Update level and other persistent stats
            const totalStars = parseInt(window.pabasaStore.get("pabasa_total_stars", "0"), 10);
            const assessmentsCompleted = parseInt(window.pabasaStore.get("pabasa_assessments_completed", "0"), 10);
            
            const progressBar = document.getElementById("profileStudentProgressBar");
            if (progressBar) {
                progressBar.style.width = percentage + "%";
                progressBar.setAttribute("aria-valuenow", percentage);
            }

            const levelDisplay = document.getElementById("profileStudentLevel");
            if (levelDisplay) {
                // Level logic based on total progress
                let level = "Novice";
                if (completedCount >= 50 || totalStars >= 500 || assessmentsCompleted >= 10) level = "Expert Reader";
                else if (completedCount >= 20 || totalStars >= 200 || assessmentsCompleted >= 5) level = "Advanced";
                else if (completedCount >= 10 || totalStars >= 100 || assessmentsCompleted >= 2) level = "Intermediate";
                else if (completedCount > 0 || totalStars > 0) level = "Developing";
                
                levelDisplay.textContent = level;
            }

        // Update Activity Status (Active, Pending, Inactive)
        const statusDisplay = document.getElementById("profileStudentStatus");
        if (statusDisplay) {
            const notifications = getStoredValue("pabasa_notifications", []);
            const lastActivity = notifications
                .filter(n => n.title === "Activity Update")
                .reduce((max, n) => Math.max(max, n.timestamp), 0);

            let statusText = "Pending";
            let statusClass = "bg-warning text-dark"; // Default for Pending

            if (completedCount === 0 && lastActivity === 0) {
                statusText = "Pending";
                statusClass = "bg-info text-dark";
            } else {
                const diffDays = (Date.now() - lastActivity) / (1000 * 60 * 60 * 24);
                if (lastActivity > 0 && diffDays <= 7) {
                    statusText = "Active";
                    statusClass = "bg-success";
                } else {
                    statusText = "Inactive";
                    statusClass = "bg-danger";
                }
            }
            statusDisplay.textContent = statusText;
            statusDisplay.className = "badge rounded-pill " + statusClass;
        }

            console.log("PABASA Progress Sync:", { lessons: totalAvailable, completed: completedCount, progress: percentage + "%" });
        } catch (e) {
            console.error("PABASA: Error updating student progress", e);
        }
    }

    function updateDashboardClassStats() {
        const readings = getStoredValue("pabasa_class_readings", {});
        
        // Normalize readings map for case-insensitive class code lookups
        const readingsMap = {};
        Object.keys(readings).forEach(key => {
            readingsMap[key.toUpperCase()] = readings[key];
        });

        const seenIds = getStoredArray("pabasa_seen_material_ids").map(id => String(id).trim());

        const cards = document.querySelectorAll("[data-class-card-code]");
        
        cards.forEach(card => {
            const rawCode = card.getAttribute("data-class-card-code");
            if (!rawCode) return;
            
            const code = rawCode.toUpperCase();
            const classData = readingsMap[code];
            
            let practiceCount = 0;
            let assessmentCount = 0;
            
            if (classData) {
                ['word', 'sentence', 'paragraph', 'story'].forEach(type => {
                    const keys = [type, type + 's', type === 'story' ? 'stories' : null].filter(Boolean);
                    keys.forEach(key => {
                        const materials = classData[key];
                        if (Array.isArray(materials)) {
                            materials.forEach(m => {
                                if (!m) return;

                                // Check if material is live (published or scheduled time passed)
                                let isLive = !m.status || m.status === 'published';
                                if (m.status === 'scheduled' && m.schedule) {
                                    isLive = new Date(m.schedule).getTime() <= Date.now();
                                }
                                if (!isLive) return;

                                const mId = (m.id !== undefined && m.id !== null) ? String(m.id).trim() : null;
                                if (mId && seenIds.includes(mId)) return;

                                const mType = (m.type || "").toLowerCase();
                                if (mType === 'assessment' || mType === 'both') assessmentCount++;
                                if (mType === 'practice' || mType === 'both') practiceCount++;
                            });
                        }
                    });
                });
            }
            
            const pEl = card.querySelector(".practice-count");
            const aEl = card.querySelector(".assessment-count");
            if (pEl) pEl.textContent = `${practiceCount} set${practiceCount !== 1 ? 's' : ''}`;
            if (aEl) aEl.textContent = String(assessmentCount);

            // Update View Details link to point to the real student course view
            const viewBtn = card.querySelector(".view-details-btn") || card.querySelector(".view-class-btn") || card.querySelector("a.btn-primary");
            if (viewBtn) {
                viewBtn.setAttribute("href", `/dashboard/courses/student-view/?code=${code}`);
            }
        });
    }

    function loadProfileSettings() {
        try {
            const stored = window.pabasaStore.get(profileStorageKey, null);
            if (stored && typeof stored === 'object') return stored;
            if (stored !== null && stored !== undefined) return stored;
        } catch (e) {
            // ignore
        }
        try {
            const raw = localStorage.getItem(profileStorageKey) || "{}";
            return JSON.parse(raw || "{}") || {};
        } catch (e) {
            return {};
        }
    }

    function saveProfileSettings(settings) {
        try {
            window.pabasaStore.set(profileStorageKey, settings);
        } catch (e) {
            try { localStorage.setItem(profileStorageKey, JSON.stringify(settings)); } catch (e2) { /* ignore */ }
        }
        try { window.dispatchEvent(new CustomEvent('pabasa:preferences-updated', { detail: settings })); } catch (e) {}
    }

    function updatePreferenceState(toggle, isEnabled) {
        if (!toggle) return;
        try { toggle.checked = !!isEnabled; } catch (e) {}
        try { toggle.setAttribute('aria-pressed', !!isEnabled); } catch (e) {}
    }

    const savedSettings = loadProfileSettings();
    const emailNotifToggle = document.getElementById("emailNotifToggle");
    const pushNotifToggle = document.getElementById("pushNotifToggle");
    const digestToggle = document.getElementById("digestToggle");
    const passwordLastChanged = document.getElementById("passwordLastChanged");

    updatePreferenceState(emailNotifToggle, savedSettings.emailNotifications !== false);
    updatePreferenceState(pushNotifToggle, savedSettings.pushNotifications !== false);
    updatePreferenceState(digestToggle, savedSettings.weeklyDigest === true);

    if (passwordLastChanged) {
        passwordLastChanged.textContent = (savedSettings.passwordLastChanged && savedSettings.passwordLastChanged !== "Just now") 
            ? savedSettings.passwordLastChanged 
            : "Not changed yet";
    }
    
    // Only run overview if we find teacher stats containers
    if (document.getElementById("profileActiveClassesCount")) {
        updateClassOverview();
    }
    updateStudentProgress();
    updateDashboardClassStats();

    [emailNotifToggle, pushNotifToggle, digestToggle].forEach(function (toggle) {
        if (!toggle) return;
        toggle.addEventListener("change", function () {
            const isEnabled = toggle.checked;
            const settings = loadProfileSettings();
            
            if (toggle === emailNotifToggle) settings.emailNotifications = isEnabled;
            if (toggle === pushNotifToggle) settings.pushNotifications = isEnabled;
            if (toggle === digestToggle) settings.weeklyDigest = isEnabled;

            saveProfileSettings(settings);
            updatePreferenceState(toggle, isEnabled);

            // Logic for "In-App Alerts" (Push Notifications)
            if (toggle === pushNotifToggle && isEnabled) {
                if ("Notification" in window) {
                    if (Notification.permission !== "granted") {
                        Notification.requestPermission().then(permission => {
                            if (permission === "granted") {
                                new Notification("PABASA", { body: "In-app alerts are enabled! You will now receive dashboard updates." });
                            } else {
                                showToast("Notification access denied. Check browser settings.", "info");
                            }
                        });
                    } else {
                        new Notification("PABASA", { body: "In-app alerts are active." });
                    }
                }
            }

            // Logic for "Email Alerts"
            if (toggle === emailNotifToggle && isEnabled && (!profileEmail || profileEmail === '""')) {
                showToast("Email alerts enabled, but no email address is set.", "info");
            }

            const label = toggle.closest(".profile-info-row")?.querySelector("strong")?.textContent || "Setting";
            showToast(`${label} successfully ${isEnabled ? 'enabled' : 'disabled'}.`);
            
            // Sync state globally
            window.dispatchEvent(new CustomEvent('pabasa:preferences-updated', { detail: settings }));
        });
    });

    const changePasswordForm = document.getElementById("changePasswordForm");
    if (changePasswordForm) {
        changePasswordForm.addEventListener("submit", function (event) {
            event.preventDefault();
            const submitBtn = changePasswordForm.querySelector("button[type='submit']");
            const originalText = submitBtn ? submitBtn.textContent : "";
            if (submitBtn) {
                submitBtn.textContent = "Saving...";
                submitBtn.disabled = true;
            }

            postProfileAction("change_password", {
                current_password: document.getElementById("currentPassword")?.value || "",
                new_password: document.getElementById("newPassword")?.value || "",
                confirm_password: document.getElementById("confirmPassword")?.value || ""
            }).then(function (data) {
                if (!data.success) {
                    alert(data.error || "Could not change password");
                    return;
                }

                const settings = loadProfileSettings();
                const now = new Date();
                const timestamp = now.toLocaleString('en-US', { 
                    month: 'short', 
                    day: 'numeric', 
                    year: 'numeric', 
                    hour: 'numeric', 
                    minute: '2-digit',
                    hour12: true
                });

                settings.passwordLastChanged = timestamp;
                saveProfileSettings(settings);

                if (passwordLastChanged) passwordLastChanged.textContent = timestamp;
                const modalEl = document.getElementById("changePasswordModal");
                if (changePasswordForm) changePasswordForm.reset();
                if (modalEl) {
                    bootstrap.Modal.getInstance(modalEl)?.hide();
                }
                showProfileSuccessModal("Password Changed", "Your password has been updated successfully.");
            }).catch(function (error) {
                alert("Error changing password: " + error.message);
            }).finally(function () {
                if (submitBtn) {
                    submitBtn.textContent = originalText;
                    submitBtn.disabled = false;
                }
            });
        });
    }

    const downloadDataBtn = document.getElementById("downloadDataBtn");
    if (downloadDataBtn) {
        downloadDataBtn.addEventListener("click", function () {
            const data = {
                name: profileFullName,
                username: profileUsername,
                email: profileEmail,
                pabasa_id: profilePabasaId,
                role: profileRoleDisplay,
                preferences: loadProfileSettings(),
                exported_at: new Date().toISOString()
            };
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = "pabasa-profile-data.json";
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
        });
    }

    const deactivateAccountBtn = document.getElementById("deactivateAccountBtn");
    if (deactivateAccountBtn) {
        deactivateAccountBtn.addEventListener("click", function () {
            showProfileConfirmModal(
                "Deactivate Account?",
                "Are you sure you want to deactivate your account? You will be signed out immediately.",
                "Yes, Deactivate",
                executeDeactivate
            );
        });

        function executeDeactivate() {
            const originalText = deactivateAccountBtn.textContent;
            deactivateAccountBtn.textContent = "Deactivating...";
            deactivateAccountBtn.disabled = true;
            postProfileAction("deactivate_account").then(function (data) {
                if (!data.success) {
                    showToast(data.error || "Could not deactivate account", "error");
                    return;
                }
                window.location.href = data.redirect_url || "/";
            }).catch(function (error) {
                showToast("Error deactivating account: " + error.message, "error");
            }).finally(function () {
                deactivateAccountBtn.textContent = originalText;
                deactivateAccountBtn.disabled = false;
            });
        }
    }

    const deleteAccountBtn = document.getElementById("deleteAccountBtn");
    const deleteModalEl = document.getElementById("profileDeleteModal");
    const deleteConfirmInput = document.getElementById("deleteConfirmInput");
    const deleteFinalBtn = document.getElementById("profileDeleteFinalBtn");

    if (deleteAccountBtn && deleteModalEl && deleteConfirmInput && deleteFinalBtn) {
        deleteAccountBtn.addEventListener("click", function () {
            deleteConfirmInput.value = "";
            deleteFinalBtn.disabled = true;
            new bootstrap.Modal(deleteModalEl).show();
        });

        deleteConfirmInput.addEventListener("input", function() {
            deleteFinalBtn.disabled = this.value !== "DELETE";
        });

        deleteFinalBtn.addEventListener("click", function() {
            const originalText = deleteFinalBtn.textContent;
            deleteFinalBtn.textContent = "Deleting...";
            deleteFinalBtn.disabled = true;
            
            postProfileAction("delete_account").then(function (data) {
                if (!data.success) {
                    showToast(data.error || "Could not delete account", "error");
                    bootstrap.Modal.getInstance(deleteModalEl)?.hide();
                    return;
                }
                localStorage.removeItem(profileStorageKey);
                window.location.href = data.redirect_url || "/";
            }).catch(function (error) {
                showToast("Error deleting account: " + error.message, "error");
                bootstrap.Modal.getInstance(deleteModalEl)?.hide();
            }).finally(function () {
                if (deleteFinalBtn) {
                    deleteFinalBtn.textContent = originalText;
                }
            });
        });
    }

    window.addEventListener("storage", function (event) {
        try {
            const k = event.key || "";
            // Trigger overview updates when any teacher classes key or related collections change
            if (
                k === "pabasa_teacher_classes" ||
                k.startsWith && typeof k.startsWith === 'function' && k.startsWith('pabasa_teacher_classes') ||
                k === "pabasa_added_students" ||
                k === "pabasa_class_readings" ||
                k === "pabasa_materials" ||
                k === "pabasa_teacher_overview_stats" || // This key is for overall stats, not individual reports
                k === "pabasa_parent_notice_history" || // Listen for changes in report history
                k === "pabasa_notifications"
            ) {
                updateClassOverview();
            }

            // Student progress and dashboard stats react to these keys
            if (
                k === "pabasa_seen_material_ids" ||
                k === "pabasa_class_readings" ||
                k === "pabasaStudentClassCodes" ||
                k === "pabasaStudentClassCode" ||
                k === "pabasa_total_stars" ||
                k === "pabasa_assessments_completed" ||
                k === "pabasa_notifications"
            ) {
                updateStudentProgress();
                updateDashboardClassStats();
            }
        } catch (e) {
            console.warn('Error handling storage event in profile.js', e);
        }
    });

    // React to in-app custom events that signal data changes
    window.addEventListener("pabasa:notifications-updated", function () {
        updateClassOverview();
        updateStudentProgress();
        updateDashboardClassStats();
    });

    window.addEventListener("pabasa:preferences-updated", function () {
        updateClassOverview();
        updateStudentProgress();
    });

    window.addEventListener("pabasa:teacher-classes-updated", function () {
        updateClassOverview();
    });

    // Periodic refresh to keep status chips current (handles cases where other tabs or server updates don't emit events)
    setInterval(function () {
        updateClassOverview();
        updateStudentProgress();
    }, 60 * 1000); // every 60s
    
    window.addEventListener("pabasa:student-class-updated", function() {
        updateStudentProgress();
        updateDashboardClassStats();
    });

    // Photo upload and remove logic
    if (profilePhotoInput && uploadPhotoBtn && removePhotoBtn) {
        // Handle file selection
        profilePhotoInput.addEventListener("change", function () {
            const file = this.files[0];
            if (file) {
                // Show file preview
                const reader = new FileReader();
                reader.onload = function (e) {
                    const profileAvatarDisplay = document.getElementById("profileAvatarDisplay");
                    if (profileAvatarDisplay) {
                        profileAvatarDisplay.textContent = "";
                        profileAvatarDisplay.style.backgroundImage = "url('" + e.target.result + "')";
                        profileAvatarDisplay.style.backgroundSize = "cover";
                        profileAvatarDisplay.style.backgroundPosition = "center";
                    }
                };
                reader.readAsDataURL(file);
            }
        });

        // Handle upload photo button
        uploadPhotoBtn.addEventListener("click", function () {
            const file = profilePhotoInput.files[0];
            if (!file) {
                showProfileSuccessModal("Action Required", "Please select a photo first.", "info");
                return;
            }

            const formData = new FormData();
            formData.append("profile_photo", file);
            formData.append("csrfmiddlewaretoken", getCsrfToken());

            // Show loading state
            const originalText = uploadPhotoBtn.textContent;
            uploadPhotoBtn.textContent = "Uploading...";
            uploadPhotoBtn.disabled = true;

            fetch(window.location.pathname, {
                method: "POST",
                body: formData,
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showProfileSuccessModal("Photo Updated", "Your profile picture has been successfully updated.");
                    // Update avatar display with the new photo URL
                    const profileAvatarDisplay = document.getElementById("profileAvatarDisplay");
                    if (profileAvatarDisplay && data.photo_url) {
                        profileAvatarDisplay.textContent = "";
                        const photoUrl = data.photo_url + "?t=" + Date.now();
                        profileAvatarDisplay.style.background = "none";
                        profileAvatarDisplay.style.backgroundImage = "url('" + photoUrl + "')";
                        profileAvatarDisplay.style.backgroundSize = "cover";
                        profileAvatarDisplay.style.backgroundPosition = "center";
                    }
                    setEditMode(false);
                    profilePhotoInput.value = "";
                } else {
                    showProfileSuccessModal("Upload Failed", data.error || "Could not upload photo.", "error");
                }
            })
            .catch(error => {
                alert("Error uploading photo: " + error.message);
            })
            .finally(() => {
                uploadPhotoBtn.textContent = originalText;
                uploadPhotoBtn.disabled = false;
            });
        });

        // Handle remove photo button
        removePhotoBtn.addEventListener("click", function () {
            showProfileConfirmModal(
                "Remove Photo?",
                "Are you sure you want to remove your profile photo? This will reset your avatar to your initials.",
                "Yes, Remove Photo",
                executeRemovePhoto
            );
        });

        function executeRemovePhoto() {
            const formData = new FormData();
            formData.append("remove_photo", "true");
            
            // Get CSRF token from the form
            const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
            if (csrfToken) {
                formData.append("csrfmiddlewaretoken", csrfToken);
            }

            // Show loading state
            const originalText = removePhotoBtn.textContent;
            removePhotoBtn.textContent = "Removing...";
            removePhotoBtn.disabled = true;

            fetch(window.location.pathname, {
                method: "POST",
                body: formData,
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showProfileSuccessModal("Photo Removed", "Your profile picture has been removed.");
                    // Reset avatar to initials
                    const profileAvatarDisplay = document.getElementById("profileAvatarDisplay");
                    if (profileAvatarDisplay) {
                        profileAvatarDisplay.textContent = profileAvatarDisplay.getAttribute("data-initials") || "";
                        profileAvatarDisplay.style.background = "";
                        profileAvatarDisplay.style.backgroundImage = "";
                        profileAvatarDisplay.style.backgroundSize = "";
                        profileAvatarDisplay.style.backgroundPosition = "";
                    }
                    setEditMode(false);
                    profilePhotoInput.value = "";
                } else {
                    alert("Error removing photo: " + (data.error || "Unknown error"));
                }
            })
            .catch(error => {
                alert("Error removing photo: " + error.message);
            })
            .finally(() => {
                removePhotoBtn.textContent = originalText;
                removePhotoBtn.disabled = false;
            });
        }
    }

    function initMicSettings() {
        const btnRequestMic = document.getElementById("btnRequestMic");
        const btnTestMic = document.getElementById("btnTestMic");
        const micStatusBadge = document.getElementById("micStatusBadge");
        const micDeviceSelect = document.getElementById("micDeviceSelect");
        const speakerDeviceSelect = document.getElementById("speakerDeviceSelect");
        const speakerVolumeInput = document.getElementById("speakerVolumeInput");
        const volumeValueDisplay = document.getElementById("volumeValue");
        const micVisualizerBar = document.getElementById("micVisualizerBar");
        
        let audioContext;
        let analyser;
        let microphone;
        let isTesting = false;
        let animationId;

        async function updateDeviceList() {
            try {
                const devices = await navigator.mediaDevices.enumerateDevices();
                const audioInputs = devices.filter(device => device.kind === 'audioinput');
                const audioOutputs = devices.filter(device => device.kind === 'audiooutput');
                
                if (micDeviceSelect) {
                    const savedMic = localStorage.getItem("pabasa_mic_device_id");
                    micDeviceSelect.innerHTML = audioInputs.map(device => 
                        `<option value="${device.deviceId}" ${device.deviceId === savedMic ? 'selected' : ''}>${device.label || 'Microphone ' + device.deviceId.slice(0, 5)}</option>`
                    ).join('') || '<option value="">No microphone detected</option>';
                }

                if (speakerDeviceSelect) {
                    const savedSpeaker = localStorage.getItem("pabasa_speaker_device_id");
                    speakerDeviceSelect.innerHTML = audioOutputs.map(device => 
                        `<option value="${device.deviceId}" ${device.deviceId === savedSpeaker ? 'selected' : ''}>${device.label || 'Speaker ' + device.deviceId.slice(0, 5)}</option>` // This is still direct localStorage
                    ).join('') || '<option value="">No speaker detected</option>';
                }
            } catch (err) {
                console.error("Error listing devices:", err);
            }
        }
        function updateMicStatus(state) {
            if (!micStatusBadge) return;
            micStatusBadge.textContent = state.charAt(0).toUpperCase() + state.slice(1);
            micStatusBadge.className = 'badge ' + (state === 'granted' ? 'bg-success' : state === 'denied' ? 'bg-danger' : 'bg-secondary');
            if (state === 'granted') updateDeviceList();
        }
        async function checkPermission() {
            try {
                const result = await navigator.permissions.query({ name: 'microphone' });
                updateMicStatus(result.state);
                result.onchange = () => updateMicStatus(result.state);
            } catch (err) {
                console.warn("Permissions API check failed for microphone");
            }
        }
        function draw() {
            if (!isTesting) return;
            const array = new Uint8Array(analyser.frequencyBinCount);
            analyser.getByteFrequencyData(array);
            let values = 0;
            for (let i = 0; i < array.length; i++) {
                values += array[i];
            }
            const average = values / array.length;
            if (micVisualizerBar) {
                micVisualizerBar.style.width = Math.min(100, average * 1.5) + "%";
            }
            animationId = requestAnimationFrame(draw);
        }
        async function startMicTest() {
            if (isTesting) return stopMicTest();

            try {
                const constraints = {
                    audio: micDeviceSelect.value ? { deviceId: { exact: micDeviceSelect.value } } : true
                };
                const stream = await navigator.mediaDevices.getUserMedia(constraints);
                
                updateMicStatus('granted');
                isTesting = true;
                if (btnTestMic) {
                    btnTestMic.innerHTML = '<i class="bi bi-stop-fill"></i> Stop Test';
                    btnTestMic.classList.replace('btn-outline-primary', 'btn-danger');
                }

                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                analyser = audioContext.createAnalyser();
                microphone = audioContext.createMediaStreamSource(stream);
                analyser.smoothingTimeConstant = 0.8;
                analyser.fftSize = 1024;
                microphone.connect(analyser);
                
                window._micStream = stream;
                draw();
            } catch (err) {
                alert("Could not access microphone: " + err.message);
                updateMicStatus('denied');
            }
            }
        function stopMicTest() {
            isTesting = false;
            cancelAnimationFrame(animationId);
            if (btnTestMic) {
                btnTestMic.innerHTML = '<i class="bi bi-play-fill"></i> Test Mic';
                btnTestMic.classList.replace('btn-danger', 'btn-outline-primary');
            }
            if (micVisualizerBar) micVisualizerBar.style.width = "0%";
            if (window._micStream) window._micStream.getTracks().forEach(t => t.stop());
            if (audioContext) audioContext.close();
        }
        btnRequestMic?.addEventListener("click", () => {
            navigator.mediaDevices.getUserMedia({ audio: true })
                .then(stream => {
                    stream.getTracks().forEach(t => t.stop());
                    updateMicStatus('granted');
                })
                .catch(err => {
                    alert("Permission denied: " + err.message);
                    updateMicStatus('denied');
                });
        });
        speakerDeviceSelect?.addEventListener("change", () => {
            window.pabasaStore.set("pabasa_speaker_device_id", speakerDeviceSelect.value);
        });

        micDeviceSelect?.addEventListener("change", () => {
            window.pabasaStore.set("pabasa_mic_device_id", micDeviceSelect.value);
        });

        speakerVolumeInput?.addEventListener("input", function() {
            if (volumeValueDisplay) volumeValueDisplay.textContent = this.value + "%";
            window.pabasaStore.set("pabasa_speaker_volume", this.value);
        });

        // Load initial volume
        (function loadInitialSpeakerSettings() {
            const savedVolume = window.pabasaStore.get("pabasa_speaker_volume");
            if (savedVolume && speakerVolumeInput) {
                speakerVolumeInput.value = savedVolume;
                if (volumeValueDisplay) volumeValueDisplay.textContent = savedVolume + "%";
            }
        })();

        btnTestMic?.addEventListener("click", startMicTest);
        checkPermission();
        updateDeviceList();
    }

    initMicSettings();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initProfilePage);
} else {
    initProfilePage();
}
