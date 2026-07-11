(function () {
    const shell = document.querySelector(".practice-shell");
    if (!shell) { console.warn("PABASA: .practice-shell not found"); return; }

    const mode = shell.dataset.practiceMode;
    const practiceDifficulty = String(shell.dataset.practiceDifficulty || "easy").trim().toLowerCase();
    const practiceText = document.getElementById("practiceText");
    const practiceCounter = document.getElementById("practiceCounter");
    const practiceProgress = document.getElementById("practiceProgress");
    const practiceFeedback = document.getElementById("practiceFeedback");
    const colorPracticeText = document.getElementById("colorPracticeText");
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

    const urlParams = new URLSearchParams(window.location.search);
    const materialId = urlParams.get("id");
    const testTitle = urlParams.get("test");

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

    function normalizeReadingType(material, currentMode) {
        const rawType = String(material?.type || material?.item_type || currentMode || 'word').trim().toLowerCase();
        if (rawType === 'story') return 'paragraph';
        if (rawType === 'sent') return 'sentence';
        if (rawType === 'para') return 'paragraph';
        if (rawType === 'word' || rawType === 'sentence' || rawType === 'paragraph') return rawType;
        return currentMode === 'story' ? 'paragraph' : (currentMode || 'word');
    }

    function getCounterLabel(difficulty) {
        if (difficulty === 'medium') return 'Sentence';
        if (difficulty === 'hard') return 'Paragraph';
        return 'Word';
    }

    function parseItems(material, currentMode) {
        const readingType = normalizeReadingType(material, currentMode);
        if (Array.isArray(material.items) && material.items.length > 0) {
            return material.items.map(item => String(item).trim()).filter(Boolean);
        }
        if (typeof material.content === 'string' && material.content.trim()) {
            const content = material.content.trim();
            if (readingType === 'word') {
                return content.split(/[,\n]+/).map(i => i.trim()).filter(Boolean);
            }
            if (readingType === 'sentence') {
                return [content.replace(/\s+/g, ' ').trim()];
            }
            if (readingType === 'paragraph') {
                return [content.replace(/\n{2,}/g, '\n\n').trim()];
            }
        }
        return [];
    }

    function fitPracticeText(content) {
        if (!practiceText || !content) return;
        const text = String(content).trim();
        const length = text.length;
        let fontSize = 1;
        if (mode === 'paragraph') {
            if (length > 220) fontSize = 0.38;
            else if (length > 180) fontSize = 0.44;
            else if (length > 120) fontSize = 0.52;
            else if (length > 80) fontSize = 0.6;
            else fontSize = 0.68;
        } else if (mode === 'sentence') {
            if (length > 80) fontSize = 0.62;
            else if (length > 60) fontSize = 0.7;
            else if (length > 40) fontSize = 0.8;
            else fontSize = 0.9;
        } else {
            if (length > 14) fontSize = 2.0;
            else if (length > 10) fontSize = 2.35;
            else fontSize = 4.5;
        }
        practiceText.style.fontSize = `clamp(${fontSize * 0.86}rem, ${fontSize}rem, ${fontSize * 1.06}rem)`;
        practiceText.style.lineHeight = mode === 'paragraph' ? '1.18' : (mode === 'sentence' ? '1.08' : '1.12');
        practiceText.style.wordBreak = 'break-word';
        practiceText.style.overflowWrap = 'anywhere';
    }

    function fitColorGuideText(content) {
        if (!colorPracticeText || !content || mode !== 'color') return;
        const text = String(content).trim();
        const length = text.length;
        let fontSize = 1;
        if (practiceDifficulty === 'hard') {
            if (length > 220) fontSize = 0.44;
            else if (length > 160) fontSize = 0.5;
            else fontSize = 0.58;
        } else if (practiceDifficulty === 'medium') {
            if (length > 80) fontSize = 0.92;
            else if (length > 50) fontSize = 1.02;
            else fontSize = 1.12;
        } else {
            if (length > 14) fontSize = 2.35;
            else if (length > 10) fontSize = 2.75;
            else fontSize = 3.2;
        }
        colorPracticeText.style.fontSize = `clamp(${fontSize * 0.86}rem, ${fontSize}rem, ${fontSize * 1.1}rem)`;
        colorPracticeText.style.lineHeight = practiceDifficulty === 'hard' ? '1.08' : (practiceDifficulty === 'medium' ? '1.06' : '1.12');
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
                        if (typeof material === 'string' && !materialId && !testTitle) {
                            aggregatedItems.push(material);
                        } else if (material && (material.type === "practice" || material.type === "both")) {
                            const mId = (material.id !== undefined && material.id !== null) ? String(material.id).trim() : null;
                            const matchesTarget = (materialId && mId === String(materialId).trim()) || (testTitle && material.title === testTitle);
                            
                            if (matchesTarget) {
                                aggregatedItems = aggregatedItems.concat(parseItems(material, mode));
                            }
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
        fitPracticeText(items[currentIndex]);
        fitColorGuideText(items[currentIndex]);
        const label = mode === 'color' ? getCounterLabel(practiceDifficulty) : (mode.charAt(0).toUpperCase() + mode.slice(1));
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

        // Mark material as seen to sync with listing page UI and badges
        if (materialId) {
            const seenIds = JSON.parse(localStorage.getItem("pabasa_seen_material_ids") || "[]").map(id => String(id).trim());
            const mId = String(materialId).trim();
            
            if (!seenIds.includes(mId)) {
                seenIds.push(mId);
                localStorage.setItem("pabasa_seen_material_ids", JSON.stringify(seenIds));
                window.dispatchEvent(new CustomEvent('pabasa:student-class-updated', { bubbles: true }));
                window.dispatchEvent(new Event('storage')); // Trigger global badge/UI updates
            }
        }
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
