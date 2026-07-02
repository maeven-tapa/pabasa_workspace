(function () {
    const shell = document.querySelector(".practice-shell") || document.querySelector("[data-practice-mode]");
    if (!shell) return;

    const mode = shell.dataset.practiceMode || shell.getAttribute("data-practice-mode") || "word";
    let items = [];
    let currentIndex = 0;
    let starsEarned = 0;
    let correctResponses = 0;
    let incorrectResponses = 0;
    let itemOutcomes = [];
    let sessionStartedAt = Date.now();

    const practiceText = document.getElementById("practiceText");
    const practiceCounter = document.getElementById("practiceCounter");
    const practiceProgress = document.getElementById("practiceProgress");
    const practiceFeedback = document.getElementById("practiceFeedback");
    const starCount = document.getElementById("starCount");
    const skipBtn = document.getElementById("skipBtn");
    const recordBtn = document.getElementById("recordBtn");
    const nextBtn = document.getElementById("practiceNextBtn");
    const completeScore = document.getElementById("completeScore");
    const completeAccuracy = document.getElementById("completeAccuracy");
    const completeTotalPracticeItems = document.getElementById("completeTotalPracticeItems");
    const completeTotalReadWords = document.getElementById("completeTotalReadWords");
    const completeTotalSkippedWords = document.getElementById("completeTotalSkippedWords");
    const completePronunciation = document.getElementById("completePronunciation");
    const pronunciationMetricCard = document.getElementById("pronunciationMetricCard");
    const completeReadingTime = document.getElementById("completeReadingTime");
    const feedbackIcon = document.getElementById("feedbackIcon");
    const resultsSummaryText = document.getElementById("resultsSummaryText");
    const practiceAgainBtn = document.getElementById("practiceAgainBtn");
    let completionSubmitted = false;

    const PERFORMANCE_FEEDBACK_RULES = Object.freeze([
        { minScore: 90, icon: "🎉", description: "Excellent work! You're all ready for when an assessment comes. Keep up the amazing reading!" },
        { minScore: 80, icon: "🌟", description: "Great job! You're doing very well. A little more practice and you'll be assessment-ready!" },
        { minScore: 70, icon: "👏", description: "Good work! You're making great progress. Keep practicing to become an even stronger reader." },
        { minScore: 60, icon: "📖", description: "Nice effort! You're improving every time you practice. Keep reading and you'll continue to get better." },
        { minScore: 50, icon: "💪", description: "Keep going! You're learning with every practice session. Read carefully and don't give up!" },
        { minScore: 0, icon: "💙", description: "Don't worry! Every great reader starts with practice. Keep trying—you'll improve one word at a time!" }
    ]);

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
            itemOutcomes = Array(items.length).fill(null);
            render();
            return;
        }

        items = [];
        itemOutcomes = [];
        if (practiceText) practiceText.textContent = "No materials available.";
        if (practiceCounter) practiceCounter.textContent = "No items";
        if (practiceProgress) practiceProgress.style.width = "0%";
        if (nextBtn) nextBtn.disabled = true;
    }

    function countWords(value) {
        return String(value || "")
            .trim()
            .split(/\s+/)
            .filter(Boolean).length;
    }

    function getItemWordCount(index) {
        return Math.max(0, countWords(items[index]));
    }

    function setCurrentItemOutcome(status) {
        if (currentIndex < 0 || currentIndex >= items.length) return;
        itemOutcomes[currentIndex] = status;

        correctResponses = itemOutcomes.filter((outcome) => outcome === "read").length;
        incorrectResponses = itemOutcomes.filter((outcome) => outcome === "skipped").length;
        starsEarned = correctResponses * 10;
    }

    function getCompletionMetrics() {
        const totalItems = items.reduce((total, item) => total + countWords(item), 0);
        const totalReadWords = itemOutcomes.reduce((total, outcome, index) => {
            return outcome === "read" ? total + getItemWordCount(index) : total;
        }, 0);
        const totalSkippedWords = itemOutcomes.reduce((total, outcome, index) => {
            return outcome === "skipped" ? total + getItemWordCount(index) : total;
        }, 0);
        const totalAttempts = correctResponses + incorrectResponses;
        const accuracy = totalAttempts > 0 ? Math.round((correctResponses / totalAttempts) * 100) : 0;
        const score = totalAttempts > 0 ? accuracy : 0;
        const readingTimeSeconds = Math.max(0, Math.round((Date.now() - sessionStartedAt) / 1000));
        const earnedStars = correctResponses * 10;

        return {
            totalItems,
            totalReadWords,
            totalSkippedWords,
            correctResponses,
            incorrectResponses,
            accuracy,
            score,
            readingTimeSeconds,
            earnedStars,
        };
    }

    function getPerformanceFeedback(score) {
        const normalizedScore = Math.max(0, Math.min(100, Number(score) || 0));
        return PERFORMANCE_FEEDBACK_RULES.find((rule) => normalizedScore >= rule.minScore) || PERFORMANCE_FEEDBACK_RULES[PERFORMANCE_FEEDBACK_RULES.length - 1];
    }

    function formatReadingTime(seconds) {
        const safeSeconds = Math.max(0, Math.round(Number(seconds) || 0));
        const minutes = Math.floor(safeSeconds / 60);
        const remainingSeconds = safeSeconds % 60;
        return `${minutes}m ${remainingSeconds}s`;
    }

    function updateCompletionSummary() {
        const metrics = getCompletionMetrics();
        const pronunciationScore = Number(window.PABASA_PRACTICE_PRONUNCIATION_SCORE || 0);
        const hasPronunciationScore = Number.isFinite(pronunciationScore) && pronunciationScore > 0;
        const feedback = getPerformanceFeedback(metrics.score);

        if (completeScore) completeScore.textContent = `${metrics.score}%`;
        if (completeAccuracy) completeAccuracy.textContent = `${metrics.accuracy}%`;
        if (completeTotalPracticeItems) completeTotalPracticeItems.textContent = metrics.totalItems;
        if (completeTotalReadWords) completeTotalReadWords.textContent = metrics.totalReadWords;
        if (completeTotalSkippedWords) completeTotalSkippedWords.textContent = metrics.totalSkippedWords;
        if (completePronunciation) completePronunciation.textContent = hasPronunciationScore ? `${Math.round(pronunciationScore)}%` : "—";
        if (pronunciationMetricCard) {
            pronunciationMetricCard.hidden = !hasPronunciationScore;
            pronunciationMetricCard.classList.toggle("is-hidden", !hasPronunciationScore);
        }
        if (completeReadingTime) completeReadingTime.textContent = formatReadingTime(metrics.readingTimeSeconds);
        if (feedbackIcon) feedbackIcon.textContent = feedback.icon;
        if (resultsSummaryText) resultsSummaryText.textContent = feedback.description;
        if (starCount) starCount.textContent = `${metrics.earnedStars} stars`;
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
        updateCompletionSummary();
        if (nextBtn) {
            nextBtn.textContent = currentIndex === items.length - 1 ? (viewMode === 'view' ? "Exit" : "Finish") : "Next";
            nextBtn.disabled = false;
        }
    }

    function markMaterialSeen(completedId) {
        if (!completedId) return;
        const seenIds = JSON.parse(localStorage.getItem("pabasa_seen_material_ids") || "[]").map(id => String(id).trim());
        const mId = String(completedId).trim();

        if (!seenIds.includes(mId)) {
            seenIds.push(mId);
            localStorage.setItem("pabasa_seen_material_ids", JSON.stringify(seenIds));
        }
        window.dispatchEvent(new CustomEvent('pabasa:student-class-updated', { bubbles: true }));
        try {
            window.dispatchEvent(new StorageEvent('storage', { key: 'pabasa_seen_material_ids' }));
        } catch (e) {
            window.dispatchEvent(new Event('storage'));
        }
    }

    function submitPracticeCompletion() {
        if (viewMode === 'view' || !materialId || completionSubmitted) return;

        const token = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        if (!token) {
            console.warn("PABASA: Missing CSRF token; practice completion was not saved.");
            return;
        }

        const metrics = getCompletionMetrics();
        completionSubmitted = true;
        const completionPayload = {
            material_id: materialId,
            activity_type: 'practice',
            stars_earned: metrics.earnedStars,
            items_completed: items.length,
            total_practice_items: metrics.totalItems,
            total_read_words: metrics.totalReadWords,
            total_skipped_words: metrics.totalSkippedWords,
            correct_responses: metrics.correctResponses,
            incorrect_responses: metrics.incorrectResponses,
            reading_time_seconds: metrics.readingTimeSeconds,
            attempt_number: 1,
            score: metrics.score,
            accuracy: metrics.accuracy,
            wpm: metrics.correctResponses && metrics.readingTimeSeconds > 0
                ? Math.round(metrics.correctResponses / (metrics.readingTimeSeconds / 60))
                : 0,
        };

        fetch('/record-assessment-completion/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
            body: JSON.stringify(completionPayload)
        })
            .then(response => response.json().then(data => ({ ok: response.ok, data })))
            .then(({ ok, data }) => {
                if (!ok || !data.success) {
                    completionSubmitted = false;
                    console.warn("PABASA: Practice completion was not saved.", data.error || data);
                    return;
                }
                markMaterialSeen(data.material_id || materialId);
                if (data.redirect_url) {
                    window.location.href = data.redirect_url;
                }
            })
            .catch(e => {
                completionSubmitted = false;
                console.warn("PABASA: Practice completion API error", e);
            });
    }

    function showCompletion() {
        shell.classList.add("is-complete");
        updateCompletionSummary();

        // Skip updating stats if in view mode
        if (viewMode === 'view') return;

        const metrics = getCompletionMetrics();

        // Persist stars to total progress
        const currentTotal = parseInt(localStorage.getItem("pabasa_total_stars") || "0");
        localStorage.setItem("pabasa_total_stars", currentTotal + metrics.earnedStars);

        submitPracticeCompletion();

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
        
    }

    function restartPractice() {
        shell.classList.remove("is-complete");
        currentIndex = 0;
        starsEarned = 0;
        correctResponses = 0;
        incorrectResponses = 0;
        itemOutcomes = Array(items.length).fill(null);
        sessionStartedAt = Date.now();
        completionSubmitted = false;
        practiceFeedback.textContent = "Ready when you are.";
        practiceFeedback.style.color = "";
        updateCompletionSummary();
        render();
    }

    skipBtn?.addEventListener("click", function () {
        setCurrentItemOutcome("skipped");
        practiceFeedback.textContent = "Skipped. That item will count as a chance to improve next time.";
        practiceFeedback.style.color = "#b95f44";
        updateCompletionSummary();
        render();
    });

    recordBtn?.addEventListener("click", function () {
        setCurrentItemOutcome("read");
        practiceFeedback.textContent = "Nice reading. You earned a practice star.";
        practiceFeedback.style.color = "#0f766e";
        updateCompletionSummary();
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
