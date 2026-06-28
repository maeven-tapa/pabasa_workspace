(function () {
    let words = [];
    let currentIndex = 0;

    const readingWord = document.getElementById("readingWord");
    const counter = document.getElementById("counter");
    const progressFill = document.getElementById("progressFill");
    const prevBtn = document.getElementById("prevBtn");
    const nextBtn = document.getElementById("nextBtn");
    const testMeta = document.getElementById("testMeta");
    const pauseBtn = document.getElementById("pauseBtn");
    const pauseOverlay = document.getElementById("pauseOverlay");
    const pauseMenu = document.getElementById("pauseMenu");
    const resumeBtn = document.getElementById("resumeBtn");
    const retryBtn = document.getElementById("retryBtn");
    const quitBtn = document.getElementById("quitBtn");
    const btnToggleMic = document.getElementById("btnToggleMic");
    const btnTestMic = document.getElementById("btnTestMic") || document.getElementById("testMic");
    const shell = document.querySelector(".reader-shell");
    const completionCount = document.getElementById("completionCount");
    const reviewBtn = document.getElementById("reviewBtn");
    const finishBtn = document.getElementById("finishBtn");
    let isMuted = false;

    const studentClassCodesKey = "pabasaStudentClassCodes";
    const legacyStudentClassCodeKey = "pabasaStudentClassCode";
    const readingsStorageKey = "pabasa_class_readings";
    const mode = 'word';

    const params = new URLSearchParams(window.location.search);
    const testTitle = params.get("test") || "Assessment";
    const testCode = params.get("code") || "TST-000";
    const materialId = params.get("id");
    const viewMode = params.get("viewMode");
    if (testMeta) testMeta.textContent = testTitle + " - " + testCode;

    function getStoredArray(key) {
        try { return JSON.parse(localStorage.getItem(key) || "[]"); } catch (e) { return []; }
    }

    function getStoredObject(key) {
        try { return JSON.parse(localStorage.getItem(key) || "{}"); } catch (e) { return {}; }
    }

    function parseItems(material, currentMode) {
        let raw = [];
        if (Array.isArray(material.items)) raw = material.items;
        else if (material.content && typeof material.content === 'string') {
            if (currentMode === 'paragraph' || currentMode === 'story' || currentMode === 'sentence') {
                raw = material.content.split(/\n/).map(i => i.trim());
            }
            else raw = material.content.split(/[,\n]/).map(i => i.trim());
        }
        return raw.filter(Boolean);
    }

    function loadItems() {
        const targetCode = (testCode && testCode !== "TST-000") ? testCode.toUpperCase() : null;
        let codes = targetCode ? [targetCode] : getStoredArray(studentClassCodesKey).filter(Boolean).map(c => String(c).toUpperCase());

        const readings = getStoredObject(readingsStorageKey);

        // Normalize readings map for case-insensitive class code lookups
        const readingsMap = {};
        Object.keys(readings).forEach(key => {
            readingsMap[key.toUpperCase()] = readings[key];
        });

        let aggregatedItems = [];
        codes.forEach(code => {
            const upperCode = String(code).toUpperCase();
            const classReadings = readingsMap[upperCode];
            if (!classReadings) return;
            
            [mode, mode + 's'].forEach(m => {
                if (Array.isArray(classReadings[m])) {
                    classReadings[m].forEach(material => {
                        if (material && material.type) {
                            const type = String(material.type).toLowerCase();
                            const isAssessment = type.includes("assessment") || type.includes("both");
                            const mId = (material.id !== undefined && material.id !== null) ? String(material.id).trim() : null;

                            // Filter by ID (preferred) or Title
                            const matchesTarget = (materialId && mId === String(materialId).trim()) || (testTitle && material.title === testTitle);
                            
                            if (isAssessment && (matchesTarget || (!testTitle && !materialId && aggregatedItems.length === 0))) {
                                aggregatedItems = aggregatedItems.concat(parseItems(material, mode));
                            }
                        } else if (typeof material === 'string') {
                            aggregatedItems.push(material);
                        }
                    });
                }
            });
        });
        words = aggregatedItems;
    }

    function renderWord() {
        if (words.length === 0) {
            if (readingWord) readingWord.textContent = "No assessment items assigned.";
            if (nextBtn) nextBtn.disabled = true;
            return;
        }
        if (readingWord) readingWord.textContent = words[currentIndex];
        if (counter) counter.textContent = "Word " + (currentIndex + 1) + "/" + words.length;
        if (progressFill) progressFill.style.width = ((currentIndex + 1) / words.length) * 100 + "%";
        if (prevBtn) prevBtn.disabled = currentIndex === 0;
        if (nextBtn) nextBtn.disabled = false;
        if (nextBtn) nextBtn.textContent = currentIndex === words.length - 1 ? (viewMode === 'view' ? "Exit" : "Finish") : "Next";
        if (completionCount) {
            completionCount.textContent = words.length;
        }
    }

    function showCompletion() {
        shell.classList.add("is-complete");
        closePauseMenu();

        // Skip updating stats if in view mode
        if (viewMode === 'view') return;

        // Increment assessment completion count
        const count = parseInt(localStorage.getItem("pabasa_assessments_completed") || "0");
        localStorage.setItem("pabasa_assessments_completed", count + 1);

        // Explicitly mark this specific material as seen to decrease sidebar badges
        if (materialId) {
            const seenIds = getStoredArray("pabasa_seen_material_ids");
            if (!seenIds.map(String).includes(String(materialId))) {
                const idToSave = isNaN(materialId) ? materialId : Number(materialId);
                seenIds.push(idToSave);
                localStorage.setItem("pabasa_seen_material_ids", JSON.stringify(seenIds));
                window.dispatchEvent(new CustomEvent('pabasa:student-class-updated'));
            }
        }

        // Notify admin that activity finished
        const studentName = window.PABASA_USER_NAME || window.localStorage.getItem("pabasaUserName") || "A student";
        const metadata = JSON.parse(localStorage.getItem("pabasa_class_metadata") || "{}");
        const classInfo = metadata[testCode.toUpperCase()] || {};
        const className = classInfo.name || "your class";

        let notifications = JSON.parse(localStorage.getItem('pabasa_notifications') || '[]');
        notifications.unshift({
            id: Date.now() + Math.random(),
            classCode: testCode,
            title: "Student Completed an Assessment",
            message: `• ${studentName} completed the assessment "${testTitle}" in ${className}.`,
            timestamp: Date.now(),
            read: false,
            role: 'admin',
            recipientEmail: null
        });
        localStorage.setItem('pabasa_notifications', JSON.stringify(notifications.slice(0, 100)));
        window.dispatchEvent(new Event('pabasa:notifications-updated'));
        
        // Notify teacher via API for database and email alert
        const token = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        if (materialId && token) {
            fetch('/record-assessment-completion/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
                body: JSON.stringify({ material_id: materialId, activity_type: 'assessment' })
            }).catch(e => console.warn("PABASA: Assessment completion API error", e));
        }
    }

    function restartAssessment() {
        shell.classList.remove("is-complete");
        currentIndex = 0;
        renderWord();
    }

    prevBtn?.addEventListener("click", function () {
        if (currentIndex > 0) {
            currentIndex -= 1;
            renderWord();
        }
    });

    nextBtn?.addEventListener("click", function () {
        if (currentIndex < words.length - 1) {
            currentIndex += 1;
            renderWord();
            return;
        }

        showCompletion();
    });

    function closePauseMenu() {
        pauseMenu?.classList.add("d-none");
        pauseOverlay?.classList.add("d-none");
        pauseBtn?.setAttribute("aria-expanded", "false");
    }

    pauseBtn?.addEventListener("click", function () {
        const isHidden = pauseMenu?.classList.contains("d-none");
        pauseMenu?.classList.toggle("d-none", !isHidden);
        pauseOverlay?.classList.toggle("d-none", !isHidden);
        pauseBtn?.setAttribute("aria-expanded", isHidden ? "true" : "false");
    });

    pauseOverlay?.addEventListener("click", closePauseMenu);

    resumeBtn?.addEventListener("click", function () {
        closePauseMenu();
    });

    retryBtn?.addEventListener("click", function () {
        if (shell) shell.classList.remove("is-complete");
        currentIndex = 0;
        renderWord();
        closePauseMenu();
    });

    quitBtn?.addEventListener("click", function () {
        window.location.href = "/dashboard/assessment/";
    });

    reviewBtn?.addEventListener("click", restartAssessment);

    finishBtn?.addEventListener("click", function () {
        window.location.href = "/dashboard/assessment/";
    });

    btnToggleMic?.addEventListener("click", () => {
        isMuted = !isMuted;
        const icon = btnToggleMic.querySelector("i");
        if (icon) icon.className = isMuted ? "bi bi-mic-mute-fill" : "bi bi-mic-fill";
        btnToggleMic.classList.toggle("btn-outline-danger", isMuted);
        btnToggleMic.classList.toggle("btn-outline-dark", !isMuted);
    });

    if (btnTestMic) {
        btnTestMic.addEventListener("click", () => {
            const title = "Microphone Check";
            const msg = "Testing device audio input ...\n\nYour microphone is receiving signal clearly! You are ready to start reading.";
            
            // Use the refined global dialog or toast utilities from base_dashboard.js
            if (typeof window.showDialog === 'function') {
                window.showDialog(title, msg, "success");
            } else if (typeof window.showToast === 'function') {
                window.showToast(msg.replace(/\n\n/g, ' '), "success");
            } else {
                console.warn("PABASA: Notification utilities not found. Falling back to native alert.");
                alert(title + "\n\n" + msg);
            }
        });
    }

    document.addEventListener("click", function (event) {
        if (pauseMenu && pauseBtn && typeof pauseMenu.contains === 'function' && !pauseMenu.contains(event.target) && !pauseBtn.contains(event.target)) {
            closePauseMenu();
        }
    });

    if (viewMode === 'view') {
        if (pauseBtn) pauseBtn.classList.add("d-none");
        if (testMeta) testMeta.innerHTML += ' <span style="background: rgba(148, 163, 184, 0.2); color: var(--muted); padding: 2px 8px; border-radius: 6px; font-size: 0.6em; vertical-align: middle; margin-left: 8px;">Review Mode</span>';
    }

    // Function to ensure dark mode is applied to the body if the theme is dark
    function ensureDarkMode() {
        const theme = localStorage.getItem("pabasa_theme");
        if (theme === "dark") {
            if (!document.body.classList.contains("dark-theme")) {
                document.body.classList.add("dark-theme");
                console.log("PABASA: Applied dark-theme to body from reading_word_page.js");
            }
        } else {
            document.body.classList.remove("dark-theme");
        }
    }

    // Call on initial load
    ensureDarkMode();
    // Listen for global theme changes (e.g., from profile page)
    window.addEventListener("pabasa:preferences-updated", ensureDarkMode);

    loadItems();
    renderWord();
})();
