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
    const shell = document.querySelector(".reader-shell");
    const completionCount = document.getElementById("completionCount");
    const completionLevel = document.getElementById("completionLevel");
    const reviewBtn = document.getElementById("reviewBtn");
    const finishBtn = document.getElementById("finishBtn");

    const studentClassCodesKey = "pabasaStudentClassCodes";
    const legacyStudentClassCodeKey = "pabasaStudentClassCode";
    const readingsStorageKey = "pabasa_class_readings";
    const mode = 'paragraph';

    const params = new URLSearchParams(window.location.search);
    const testTitle = params.get("test") || "Assessment";
    const testCode = params.get("code") || "TST-000";
    const materialId = params.get("id");
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
        // Use only the specific code from the URL if available to avoid mixing materials
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
                            
                            if (isAssessment && (material.title === testTitle || (!testTitle && aggregatedItems.length === 0))) {
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
        if (counter) counter.textContent = "Paragraph " + (currentIndex + 1) + "/" + words.length;
        if (progressFill) progressFill.style.width = ((currentIndex + 1) / words.length) * 100 + "%";
        if (prevBtn) prevBtn.disabled = currentIndex === 0;
        if (nextBtn) nextBtn.disabled = false;
        if (nextBtn) nextBtn.textContent = currentIndex === words.length - 1 ? "Finish" : "Next";
        if (completionCount) {
            completionCount.textContent = words.length;
        }
        if (completionLevel) {
            completionLevel.textContent = "Paragraph";
        }
    }

    function showCompletion() {
        if (!shell) {
            return;
        }
        shell.classList.add("is-complete");
        closePauseMenu();

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
    }

    function restartAssessment() {
        if (!shell) {
            return;
        }
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
        if (shell) {
            shell.classList.remove("is-complete");
        }
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

    document.addEventListener("click", function (event) {
        if (pauseMenu && pauseBtn && typeof pauseMenu.contains === 'function' && !pauseMenu.contains(event.target) && !pauseBtn.contains(event.target)) {
            closePauseMenu();
        }
    });

    loadItems();
    renderWord();
})();
