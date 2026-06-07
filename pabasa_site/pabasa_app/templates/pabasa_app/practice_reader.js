(function () {
    const shell = document.querySelector(".practice-shell");
    if (!shell) { console.warn("PABASA: .practice-shell not found"); return; }

    const mode = shell.dataset.practiceMode;
    const practiceText = document.getElementById("practiceText");
    const practiceCounter = document.getElementById("practiceCounter");
    const practiceProgress = document.getElementById("practiceProgress");
    const practiceFeedback = document.getElementById("practiceFeedback");
    const listenBtn = document.getElementById("listenBtn");
    const skipBtn = document.getElementById("skipBtn");
    const recordBtn = document.getElementById("recordBtn");
    const practiceNextBtn = document.getElementById("practiceNextBtn");
    const practiceAgainBtn = document.getElementById("practiceAgainBtn");
    const starCountDisplay = document.getElementById("starCount");
    
    const completeStars = document.getElementById("completeStars");
    const completeItems = document.getElementById("completeItems");
    console.log("PABASA: Practice reader initialized in mode:", mode);

    let items = [];
    let currentIndex = 0;
    let starsEarned = 0;

    const studentClassCodesKey = "pabasaStudentClassCodes";
    const legacyStudentClassCodeKey = "pabasaStudentClassCode";
    const readingsStorageKey = "pabasa_class_readings";

    function getStoredArray(key) {
        try {
            const parsed = JSON.parse(localStorage.getItem(key) || "[]");
            return Array.isArray(parsed) ? parsed : [];
        } catch (e) { return []; }
    }

    function getStoredObject(key) {
        try {
            const parsed = JSON.parse(localStorage.getItem(key) || "{}");
            return (parsed && typeof parsed === "object" && !Array.isArray(parsed)) ? parsed : {};
        } catch (e) { return {}; }
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
        
        let aggregatedItems = [];
        const storageKeys = [mode, mode === 'paragraph' ? 'paragraph' : mode + 's'];

        codes.forEach(code => {
            const upperCode = String(code).toUpperCase();
            const classReadings = readings[upperCode];
            if (!classReadings) return;

            storageKeys.forEach(m => {
                if (Array.isArray(classReadings[m])) {
                    classReadings[m].forEach(material => {
                        if (typeof material === 'string') {
                            aggregatedItems.push(material);
                        } else if (material && (material.type === "practice" || material.type === "both")) {
                            aggregatedItems = aggregatedItems.concat(parseItems(material, mode));
                        }
                    });
                }
            });
        });

        items = aggregatedItems;
        console.log("PABASA: Found total items for practice:", items.length);

        if (items.length === 0) {
            practiceText.textContent = "No materials available.";
            if (practiceNextBtn) practiceNextBtn.disabled = true;
            return;
        }

        currentIndex = 0;
        updateUI();
    }

    function updateUI() {
        if (currentIndex >= items.length) {
            showCompletion();
            return;
        }

        practiceText.textContent = items[currentIndex];
        const label = mode.charAt(0).toUpperCase() + mode.slice(1);
        practiceCounter.textContent = `${label} ${currentIndex + 1}/${items.length}`;
        practiceProgress.style.width = `${((currentIndex + 1) / items.length) * 100}%`;
        practiceFeedback.textContent = "Ready when you are.";
        practiceFeedback.style.color = "";
        if (starCountDisplay) starCountDisplay.textContent = `${starsEarned} stars`;
    }

    function showCompletion() {
        shell.classList.add("is-complete");
        if (completeStars) completeStars.textContent = starsEarned;
        if (completeItems) completeItems.textContent = items.length;

        // Persist stars to total progress
        const currentTotal = parseInt(localStorage.getItem("pabasa_total_stars") || "0");
        localStorage.setItem("pabasa_total_stars", currentTotal + starsEarned);
    }

    listenBtn?.addEventListener("click", () => {
        if (!items[currentIndex]) return;
        const utterance = new SpeechSynthesisUtterance(items[currentIndex]);
        utterance.lang = 'tl-PH';
        window.speechSynthesis.speak(utterance);
        practiceFeedback.textContent = "Listening...";
    });

    skipBtn?.addEventListener("click", () => {
        starsEarned = Math.max(0, starsEarned - 5);
        practiceFeedback.textContent = "Word skipped. -5 stars deducted.";
        practiceFeedback.style.color = "#b95f44";
        updateUI();
    });

    recordBtn?.addEventListener("click", () => {
        starsEarned += 10;
        practiceFeedback.textContent = "Great job! +10 stars earned.";
        practiceFeedback.style.color = "#16a34a";
        if (starCountDisplay) starCountDisplay.textContent = `${starsEarned} stars`;
    });

    practiceNextBtn?.addEventListener("click", () => { currentIndex++; updateUI(); });
    practiceAgainBtn?.addEventListener("click", () => { location.reload(); });
    loadItems();
})();