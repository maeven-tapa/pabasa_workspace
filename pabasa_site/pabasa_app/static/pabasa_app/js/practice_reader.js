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

    const urlParams = new URLSearchParams(window.location.search);
    const materialId = urlParams.get("id");
    const testTitle = urlParams.get("test");
    const viewMode = urlParams.get("viewMode");
    const selectedDifficulty = (urlParams.get("difficulty") || "").trim().toLowerCase();

    function getServerPracticeMaterials() {
        const dataElement = document.getElementById("practiceMaterialsData");
        if (!dataElement) return [];

        try {
            return JSON.parse(dataElement.textContent || "[]");
        } catch (e) {
            console.warn("PABASA [Practice]: Unable to parse server practice materials.", e);
            return [];
        }
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

    function loadServerPracticeItems() {
        const serverMaterials = getServerPracticeMaterials();
        if (!serverMaterials.length) return [];

        return serverMaterials.reduce((aggregatedItems, material) => {
            // Fix: Check item_type (word/sentence/para) and type (practice/both)
            const mItemType = material.item_type || material.type; // Fallback for various JSON structures
            if (!material || mItemType !== mode) return aggregatedItems;
            if (selectedDifficulty && material.difficulty !== selectedDifficulty) return aggregatedItems;

            const mId = (material.id !== undefined && material.id !== null) ? String(material.id).trim() : null;
            const matchesTarget = !materialId && !testTitle
                || (materialId && mId === String(materialId).trim())
                || (testTitle && material.title === testTitle);

            if (matchesTarget) {
                aggregatedItems.push(...parseItems(material, mode));
            }

            return aggregatedItems;
        }, []);
    }

    function loadItems() {
        const serverItems = loadServerPracticeItems();
        if (serverItems.length > 0) {
            items = serverItems.slice();
            currentIndex = 0;
            render();
            return;
        }

        items = [];
        if (practiceText) practiceText.textContent = "No materials available.";
        if (practiceCounter) practiceCounter.textContent = "No items";
        if (practiceProgress) practiceProgress.style.width = "0%";
        if (nextBtn) nextBtn.disabled = true;
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
                window.dispatchEvent(new Event('storage')); // Sync sidebar badges immediately
            }
        }

        // Notify admin that practice activity finished
        const studentName = window.PABASA_USER_NAME || window.localStorage.getItem("pabasaUserName") || "A student";
        const fallbackTitle = urlParams.get("test") || "Practice Material";
        const serverMaterials = getServerPracticeMaterials();
        const matchingMaterial = serverMaterials.find((material) => {
            const mId = (material.id !== undefined && material.id !== null) ? String(material.id).trim() : null;
            const normalizedTitle = typeof material.title === 'string' ? material.title.trim() : '';
            const normalizedTestTitle = typeof testTitle === 'string' ? testTitle.trim() : '';
            return (materialId && mId && String(materialId).trim() === mId)
                || (normalizedTestTitle && normalizedTitle && normalizedTitle === normalizedTestTitle)
                || (!materialId && !normalizedTestTitle && normalizedTitle);
        });
        const practiceTitle = (matchingMaterial && matchingMaterial.title) || fallbackTitle;
        const tCode = urlParams.get("code") || "GENERAL";
        
        const metadata = JSON.parse(localStorage.getItem("pabasa_class_metadata") || "{}");
        const classInfo = metadata[tCode.toUpperCase()] || {};
        const className = classInfo.name || "your class";

        let notifications = JSON.parse(localStorage.getItem('pabasa_notifications') || '[]');
        notifications.unshift({
            id: Date.now() + Math.random(),
            classCode: tCode,
            title: 'Practice Material Completed',
            message: `${studentName} finished reading Practice Material: ${practiceTitle}`,
            timestamp: Date.now(),
            read: false,
            role: 'admin',
            recipientEmail: null
        });
        localStorage.setItem('pabasa_notifications', JSON.stringify(notifications.slice(0, 100)));
        window.dispatchEvent(new Event('pabasa:notifications-updated'));
        
        // Notify via API as well
        const token = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        if (materialId && token) {
            fetch('/record-assessment-completion/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
                body: JSON.stringify({ material_id: materialId, activity_type: 'practice' })
            }).catch(e => console.warn("PABASA: Practice completion API error", e));
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
