(function () {
    const shell = document.querySelector(".practice-shell") || document.querySelector("[data-practice-mode]");
    if (!shell) return;

    const mode = shell.dataset.practiceMode || shell.getAttribute("data-practice-mode") || "word";
    let items = [];
    let currentIndex = 0;
    let starsEarned = 0;

    const practiceText = document.getElementById("practiceText");
    const practiceCounter = document.getElementById("practiceCounter");
    const practiceProgress = document.getElementById("practiceProgress");
    const practiceFeedback = document.getElementById("practiceFeedback");
    const starCount = document.getElementById("starCount");
    const skipBtn = document.getElementById("skipBtn");
    const recordBtn = document.getElementById("recordBtn");
    const nextBtn = document.getElementById("practiceNextBtn");
    const completeStars = document.getElementById("completeStars");
    const completeItems = document.getElementById("completeItems");
    const practiceAgainBtn = document.getElementById("practiceAgainBtn");

    const studentClassCodesKey = "pabasaStudentClassCodes";
    const legacyStudentClassCodeKey = "pabasaStudentClassCode";
    const readingsStorageKey = "pabasa_class_readings";

    const urlParams = new URLSearchParams(window.location.search);
    const materialId = urlParams.get("id");
    const viewMode = urlParams.get("viewMode");

    function getStoredArray(key) {
        try { return JSON.parse(localStorage.getItem(key) || "[]"); } catch (e) { return []; }
    }

    function getStoredObject(key) {
        try { return JSON.parse(localStorage.getItem(key) || "{}"); } catch (e) { return {}; }
    }

    function parseItems(material, currentMode) {
        if (Array.isArray(material.items) && material.items.length > 0) return material.items;
        if (material.content && typeof material.content === 'string') {
            if (currentMode === 'paragraph' || currentMode === 'story' || currentMode === 'sentence') {
                return material.content.split(/\n/).map(i => i.trim()).filter(Boolean);
            }
            return material.content.split(/[,\n]/).map(i => i.trim()).filter(Boolean);
        }
        return [];
    }

    function loadItems() {
        const params = new URLSearchParams(window.location.search);
        const urlCode = params.get("code");

        let codes = urlCode 
            ? [urlCode.toUpperCase()] 
            : getStoredArray(studentClassCodesKey).filter(Boolean);

        const legacyCode = localStorage.getItem(legacyStudentClassCodeKey);
        if (!urlCode && codes.length === 0 && legacyCode) {
            codes.push(legacyCode);
        }

        const readings = getStoredObject(readingsStorageKey);
        console.log(`PABASA [Practice]: Loading for codes:`, codes);
        
        let aggregatedItems = [];
        const storageKeys = [mode, mode + 's'];

        codes.forEach(code => {
            const classReadings = readings[code.toUpperCase()];
            if (!classReadings) {
                console.warn(`PABASA: No practice readings for code: ${code}`);
                return;
            }

            storageKeys.forEach(m => {
                if (Array.isArray(classReadings[m])) {
                    classReadings[m].forEach(material => {
                        if (typeof material === 'string') {
                            aggregatedItems.push(material);
                        } else if (material && material.type) {
                            const type = material.type.toLowerCase();
                            if (type.includes("practice") || type === "both") {
                                aggregatedItems = aggregatedItems.concat(parseItems(material, mode));
                            }
                        }
                    });
                }
            });
        });

        items = aggregatedItems;
        console.log(`PABASA [Practice]: Found ${items.length} items.`);

        if (items.length === 0) {
            if (practiceText) practiceText.textContent = "No materials available.";
            if (nextBtn) nextBtn.disabled = true;
            return;
        }

        currentIndex = 0;
        render();
    }

    function render() {
        if (currentIndex >= items.length) {
            showCompletion();
            return;
        }

        practiceText.textContent = items[currentIndex];
        const label = mode.charAt(0).toUpperCase() + mode.slice(1);
        practiceCounter.textContent = `${label} ${currentIndex + 1}/${items.length}`;
        practiceProgress.style.width = `${((currentIndex + 1) / items.length) * 100}%`;
        if (starCount) starCount.textContent = `${starsEarned} stars`;
        if (nextBtn) {
            nextBtn.textContent = currentIndex === items.length - 1 ? (viewMode === 'view' ? "Exit" : "Finish") : "Next";
            nextBtn.disabled = false;
        }
    }

    function showCompletion() {
        shell.classList.add("is-complete");
        if (completeStars) completeStars.textContent = starsEarned;
        if (completeItems) completeItems.textContent = items.length;

        // Skip updating stats if in view mode
        if (viewMode === 'view') return;

        // Persist stars to total progress
        const currentTotal = parseInt(localStorage.getItem("pabasa_total_stars") || "0");
        localStorage.setItem("pabasa_total_stars", currentTotal + starsEarned);

        // Mark material as seen
        if (materialId) {
            const seenIds = JSON.parse(localStorage.getItem("pabasa_seen_material_ids") || "[]").map(id => String(id).trim());
            const mId = String(materialId).trim();
            
            if (!seenIds.includes(mId)) {
                seenIds.push(mId);
                localStorage.setItem("pabasa_seen_material_ids", JSON.stringify(seenIds));
                window.dispatchEvent(new CustomEvent('pabasa:student-class-updated'));
            }
        }
    }

    function restartPractice() {
        shell.classList.remove("is-complete");
        currentIndex = 0;
        starsEarned = 0;
        practiceFeedback.textContent = "Ready when you are.";
        render();
    }

    skipBtn?.addEventListener("click", function () {
        starsEarned = Math.max(0, starsEarned - 5);
        practiceFeedback.textContent = "Word skipped. -5 stars deducted.";
        practiceFeedback.style.color = "#b95f44";
        render();
    });

    recordBtn?.addEventListener("click", function () {
        starsEarned += 10;
        practiceFeedback.textContent = "Nice reading. You earned a practice star.";
        render();
    });

    nextBtn?.addEventListener("click", function () {
        if (currentIndex < items.length - 1) {
            currentIndex += 1;
            practiceFeedback.textContent = "New item ready. Take your time.";
            render();
            return;
        }

        showCompletion();
    });

    practiceAgainBtn?.addEventListener("click", restartPractice);

    if (viewMode === 'view') {
        if (skipBtn) skipBtn.classList.add("d-none");
        if (recordBtn) recordBtn.classList.add("d-none");
        if (starCount) starCount.classList.add("d-none");
        if (practiceFeedback) practiceFeedback.textContent = "Reviewing completed content.";
    }

    loadItems();
})();
