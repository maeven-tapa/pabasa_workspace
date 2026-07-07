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
    const isFreeMode = shell.getAttribute("data-free-mode") === "true";
    const scrollsTrack = document.getElementById("scrollsTrack");
    const scrollsDots = document.getElementById("scrollsDots");
    const scrollsProgressBarFill = document.getElementById("scrollsProgressBarFill");
    const scrollsProgressMeta = document.getElementById("scrollsProgressMeta");
    const scrollsFeedback = document.getElementById("scrollsFeedback");
    const scrollsAppTitle = document.getElementById("scrollsAppTitle");
    const scrollsDifficultyPill = document.getElementById("scrollsDifficultyPill");
    const scrollsLevelPill = document.getElementById("scrollsLevelPill");
    const scrollsProgressPill = document.getElementById("scrollsProgressPill");
    const scrollsStatusPill = document.getElementById("scrollsStatusPill");
    const scrollRecordBtn = document.getElementById("scrollRecordBtn");
    let scrollCurrentIndex = 0;
    let scrollTouchStartY = 0;
    let scrollTouchEndY = 0;
    let freeModeGestureLocked = false;
    let freeModeGestureTimer = null;
    const coachAnimationPlayerActive = document.getElementById("coachAnimationPlayerActive");
    const coachAnimationPlayerBuffer = document.getElementById("coachAnimationPlayerBuffer");
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
    const selectedGameMode = (urlParams.get("game") || "free").trim().toLowerCase();
    const selectedProgressLevel = (urlParams.get("level") || "level_1").trim().toLowerCase();
    const practiceProgressStorageKey = "pabasa_practice_progress_v1";
    const practiceProgressLevelSequence = Object.freeze([
        ['easy', 'level_1'],
        ['easy', 'level_2'],
        ['easy', 'level_3'],
        ['easy', 'level_4'],
        ['easy', 'level_5'],
        ['medium', 'level_1'],
        ['medium', 'level_2'],
        ['medium', 'level_3'],
        ['medium', 'level_4'],
        ['medium', 'level_5'],
        ['hard', 'level_1'],
        ['hard', 'level_2'],
        ['hard', 'level_3'],
        ['hard', 'level_4'],
        ['hard', 'level_5'],
    ]);

    function getPracticeProgressState() {
        try {
            const parsed = JSON.parse(localStorage.getItem(practiceProgressStorageKey) || "{}");
            return parsed && typeof parsed === "object" ? parsed : {};
        } catch (error) {
            console.warn("PABASA [Practice]: Unable to read local progress state.", error);
            return {};
        }
    }

    function savePracticeProgressState(progressState) {
        localStorage.setItem(practiceProgressStorageKey, JSON.stringify(progressState));
        window.dispatchEvent(new CustomEvent("pabasa:practice-progress-updated", { detail: progressState }));
        try {
            window.dispatchEvent(new StorageEvent("storage", { key: practiceProgressStorageKey }));
        } catch (error) {
            window.dispatchEvent(new Event("storage"));
        }
    }

    function getLevelProgressContext() {
        return {
            mode: selectedGameMode || "free",
            difficulty: (selectedDifficulty || "easy").toLowerCase(),
            level: (selectedProgressLevel || "level_1").toLowerCase(),
        };
    }

    function getStoredLevelEntry(progressState, mode, difficulty, level) {
        const modeState = progressState[mode] && typeof progressState[mode] === "object" ? progressState[mode] : {};
        const difficultyState = modeState[difficulty] && typeof modeState[difficulty] === "object" ? modeState[difficulty] : {};
        const existingEntry = difficultyState[level] && typeof difficultyState[level] === "object" ? difficultyState[level] : {};
        return existingEntry;
    }

    function ensureLevelProgressEntry(progressState, mode, difficulty, level) {
        if (!progressState[mode] || typeof progressState[mode] !== "object") {
            progressState[mode] = {};
        }
        if (!progressState[mode][difficulty] || typeof progressState[mode][difficulty] !== "object") {
            progressState[mode][difficulty] = {};
        }

        const entry = progressState[mode][difficulty][level] && typeof progressState[mode][difficulty][level] === "object"
            ? progressState[mode][difficulty][level]
            : {};

        const sequenceIndex = practiceProgressLevelSequence.findIndex((candidate) => candidate[0] === difficulty && candidate[1] === level);
        const isFirstLevel = sequenceIndex === 0;
        const unlocked = entry.unlocked !== undefined
            ? Boolean(entry.unlocked)
            : (isFirstLevel || (() => {
                for (let index = 0; index < sequenceIndex; index += 1) {
                    const [previousDifficulty, previousLevel] = practiceProgressLevelSequence[index];
                    const previousEntry = getStoredLevelEntry(progressState, mode, previousDifficulty, previousLevel);
                    if (previousEntry?.completed) {
                        return true;
                    }
                }
                return false;
            })());

        entry.completed = Boolean(entry.completed);
        entry.unlocked = unlocked;
        entry.cards_completed = Number(entry.cards_completed || 0) || 0;
        entry.completed_cards = Array.isArray(entry.completed_cards) ? entry.completed_cards : [];
        entry.stars_earned = Number(entry.stars_earned || 0) || 0;

        progressState[mode][difficulty][level] = entry;
        return entry;
    }

    function saveLevelProgressEntry(mode, difficulty, level, updates) {
        const progressState = getPracticeProgressState();
        const entry = ensureLevelProgressEntry(progressState, mode, difficulty, level);
        Object.assign(entry, updates);
        progressState[mode][difficulty][level] = entry;
        savePracticeProgressState(progressState);
        return entry;
    }

    function getNextLevelContext(currentMode, currentDifficulty, currentLevel) {
        const currentIndex = practiceProgressLevelSequence.findIndex((candidate) => candidate[0] === currentDifficulty && candidate[1] === currentLevel);
        if (currentIndex < 0 || currentIndex === practiceProgressLevelSequence.length - 1) {
            return null;
        }
        const [nextDifficulty, nextLevel] = practiceProgressLevelSequence[currentIndex + 1];
        return { mode: currentMode, difficulty: nextDifficulty, level: nextLevel };
    }

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

    function normalizeMaterialValue(value) {
        return String(value || "").trim();
    }

    function matchesMaterial(material) {
        if (!material) return false;
        const mItemType = material.item_type || material.type;
        if (mItemType !== mode) return false;

        const materialDifficulty = normalizeMaterialValue(material.difficulty || material.difficulty_level || selectedDifficulty || "").toLowerCase();
        const requestedDifficulty = normalizeMaterialValue(selectedDifficulty).toLowerCase();
        if (requestedDifficulty && materialDifficulty && materialDifficulty !== requestedDifficulty) return false;

        const mId = (material.id !== undefined && material.id !== null) ? String(material.id).trim() : null;
        return !materialId && !testTitle
            || (materialId && mId === String(materialId).trim())
            || (testTitle && material.title === testTitle);
    }

    function getActiveMaterialMeta() {
        const serverMaterials = getServerPracticeMaterials();
        return serverMaterials.find(matchesMaterial) || null;
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
            if (!material || !matchesMaterial(material)) return aggregatedItems;
            aggregatedItems.push(...parseItems(material, mode));
            return aggregatedItems;
        }, []);
    }

    const coachVideoBase = window.PABASA_COACH_VIDEO_BASE || "/static/pabasa_app/videos/";
    const coachAnimationFiles = {
        read: 'Greetings.mp4',
        next: 'Excited Win.mp4',
        skip: 'Deep Thinker.mp4'
    };
    const initialCoachAnimation = 'Explaining.mp4';
    const coachAnimationStartTime = 4;
    let currentCoachAnimation = null;

    function setCoachAnimationSource(filename) {
        if (!coachAnimationPlayerActive || !coachAnimationPlayerBuffer || !filename) return;
        const videoUrl = coachVideoBase + encodeURIComponent(filename);

        if (currentCoachAnimation === filename) {
            coachAnimationPlayerActive.currentTime = coachAnimationStartTime;
            coachAnimationPlayerActive.play().catch(() => {});
            return;
        }

        currentCoachAnimation = filename;
        const activePlayer = coachAnimationPlayerActive.classList.contains('visible') ? coachAnimationPlayerActive : coachAnimationPlayerBuffer;
        const bufferPlayer = activePlayer === coachAnimationPlayerActive ? coachAnimationPlayerBuffer : coachAnimationPlayerActive;

        bufferPlayer.pause();
        bufferPlayer.removeAttribute('src');
        bufferPlayer.muted = true;
        bufferPlayer.playsInline = true;
        bufferPlayer.setAttribute('playsinline', '');
        bufferPlayer.setAttribute('webkit-playsinline', '');
        bufferPlayer.loop = false;
        bufferPlayer.classList.remove('visible');
        bufferPlayer.src = videoUrl;

        const onLoadedMetadata = () => {
            try {
                bufferPlayer.currentTime = coachAnimationStartTime;
            } catch (err) {
                // ignore invalid seek if time not ready
            }
        };

        const onCanPlay = () => {
            try {
                bufferPlayer.currentTime = coachAnimationStartTime;
            } catch (err) {
                // ignore invalid seek if time not ready
            }
            bufferPlayer.play().catch(() => {});
            bufferPlayer.classList.add('visible');
            activePlayer.classList.remove('visible');
            activePlayer.pause();
            bufferPlayer.removeEventListener('loadedmetadata', onLoadedMetadata);
            bufferPlayer.removeEventListener('canplay', onCanPlay);
        };

        bufferPlayer.addEventListener('loadedmetadata', onLoadedMetadata, { once: true });
        bufferPlayer.addEventListener('canplay', onCanPlay, { once: true });
        bufferPlayer.addEventListener('error', () => {
            // Keep the current active player visible if the new video cannot load.
            bufferPlayer.classList.remove('visible');
            activePlayer.classList.add('visible');
        }, { once: true });
        bufferPlayer.load();
    }

    function playCoachAnimation(action) {
        setCoachAnimationSource(coachAnimationFiles[action]);
    }

    function loadItems() {
        const serverItems = loadServerPracticeItems();
        if (serverItems.length > 0) {
            items = serverItems.slice();
            currentIndex = 0;
            itemOutcomes = Array(items.length).fill(null);
            if (isFreeMode) {
                renderFreeMode();
            } else {
                render();
            }
            setCoachAnimationSource(initialCoachAnimation);
            return;
        }

        items = [];
        itemOutcomes = [];
        if (practiceText) practiceText.textContent = "No materials available.";
        if (practiceCounter) practiceCounter.textContent = "No items";
        if (practiceProgress) practiceProgress.style.width = "0%";
        if (nextBtn) nextBtn.disabled = true;
        setCoachAnimationSource(initialCoachAnimation);
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

    function renderFreeMode() {
        if (!scrollsTrack) return;
        if (!items.length) {
            scrollsTrack.innerHTML = '<div class="scrolls-card"><div class="scrolls-card-badge"><i class="bi bi-journal-text"></i> No cards yet</div><p class="scrolls-card-text">No reading cards are available right now.</p></div>';
            return;
        }

        const currentLevelContext = getLevelProgressContext();
        const levelEntry = ensureLevelProgressEntry(getPracticeProgressState(), currentLevelContext.mode, currentLevelContext.difficulty, currentLevelContext.level);
        const completedCards = new Set(levelEntry.completed_cards || []);

        const cardMarkup = items.map((item, index) => {
            const illustration = index % 2 === 0 ? '📖' : '✨';
            const badge = index === 0 ? 'New card' : `Card ${index + 1}`;
            const isComplete = completedCards.has(index);
            return `
                <section class="scrolls-card${isComplete ? ' is-complete' : ''}" data-index="${index}">
                    <span class="scrolls-card-badge"><i class="bi bi-stars"></i> ${badge}</span>
                    <div class="scrolls-illustration" aria-hidden="true">${illustration}</div>
                    <h2 class="scrolls-card-text">${escapeHtml(item)}</h2>
                    <p class="scrolls-card-note">Read slowly, then tap the mic to record your voice.</p>
                    <p class="scrolls-hint">Swipe up for the next challenge</p>
                    <div class="scrolls-card-actions">
                        <button class="scrolls-record-btn${isComplete ? ' is-read' : ''}" type="button"><i class="bi bi-${isComplete ? 'check-circle-fill' : 'mic-fill'}"></i> ${isComplete ? 'Completed' : 'Read aloud'}</button>
                    </div>
                </section>`;
        }).join('');

        scrollsTrack.innerHTML = cardMarkup;
        scrollsTrack.style.transform = `translateY(-${scrollCurrentIndex * 100}%)`;
        updateFreeModeProgress();
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function updateFreeModeProgress() {
        if (!items.length) return;
        const current = Math.min(items.length - 1, Math.max(0, scrollCurrentIndex));
        const progressPercent = ((current + 1) / items.length) * 100;
        const activeMaterial = getActiveMaterialMeta();
        const difficultyLabelText = normalizeMaterialValue(activeMaterial?.difficulty_label || activeMaterial?.difficulty || selectedDifficulty || 'Easy');
        const levelLabelText = normalizeMaterialValue(activeMaterial?.level_label || activeMaterial?.level || 'Level 2');
        const titleText = normalizeMaterialValue(activeMaterial?.title || 'PABASA Scrolls');
        const currentLevelContext = getLevelProgressContext();
        const levelEntry = ensureLevelProgressEntry(getPracticeProgressState(), currentLevelContext.mode, currentLevelContext.difficulty, currentLevelContext.level);
        const completedCards = Array.isArray(levelEntry.completed_cards) ? levelEntry.completed_cards.length : 0;

        if (scrollsProgressBarFill) scrollsProgressBarFill.style.width = `${progressPercent}%`;
        if (scrollsProgressMeta) scrollsProgressMeta.textContent = levelEntry.completed ? 'Level complete! The next challenge is unlocked.' : current === items.length - 1 ? 'You reached the end of this level' : 'Swipe up for the next challenge';
        if (scrollsAppTitle) scrollsAppTitle.textContent = titleText;
        if (scrollsDifficultyPill) scrollsDifficultyPill.textContent = difficultyLabelText || 'Easy';
        if (scrollsLevelPill) scrollsLevelPill.textContent = levelLabelText || 'Level 2';
        if (scrollsProgressPill) scrollsProgressPill.textContent = `Card ${current + 1} of ${items.length}`;
        if (scrollsStatusPill) scrollsStatusPill.textContent = levelEntry.completed ? 'Level complete' : completedCards > 0 ? `${completedCards} completed` : 'Ready';
        if (scrollsDots) {
            scrollsDots.innerHTML = items.map((_, index) => `<span class="${index === current ? 'is-active' : ''}"></span>`).join('');
        }
    }

    function lockFreeModeGesture() {
        if (freeModeGestureLocked) return false;
        freeModeGestureLocked = true;
        if (freeModeGestureTimer) {
            window.clearTimeout(freeModeGestureTimer);
        }
        freeModeGestureTimer = window.setTimeout(() => {
            freeModeGestureLocked = false;
        }, 450);
        return true;
    }

    function persistFreeModeCardProgress(cardIndex) {
        if (!Number.isInteger(cardIndex) || cardIndex < 0 || cardIndex >= items.length) return null;

        const levelContext = getLevelProgressContext();
        const progressState = getPracticeProgressState();
        const entry = ensureLevelProgressEntry(progressState, levelContext.mode, levelContext.difficulty, levelContext.level);
        const completedCards = Array.isArray(entry.completed_cards) ? entry.completed_cards : [];
        if (!completedCards.includes(cardIndex)) {
            entry.completed_cards = [...completedCards, cardIndex];
            entry.cards_completed = entry.completed_cards.length;
            entry.unlocked = true;
            entry.completed = entry.cards_completed >= items.length;
            progressState[levelContext.mode][levelContext.difficulty][levelContext.level] = entry;
            savePracticeProgressState(progressState);
        }
        return entry;
    }

    function completeFreeModeLevel() {
        const levelContext = getLevelProgressContext();
        const progressState = getPracticeProgressState();
        const entry = ensureLevelProgressEntry(progressState, levelContext.mode, levelContext.difficulty, levelContext.level);
        entry.cards_completed = Math.max(entry.cards_completed || 0, items.length);
        entry.completed_cards = Array.isArray(entry.completed_cards) ? Array.from(new Set(entry.completed_cards)) : [];
        entry.unlocked = true;
        entry.completed = true;
        progressState[levelContext.mode][levelContext.difficulty][levelContext.level] = entry;
        savePracticeProgressState(progressState);

        const nextLevel = getNextLevelContext(levelContext.mode, levelContext.difficulty, levelContext.level);
        if (nextLevel) {
            saveLevelProgressEntry(nextLevel.mode, nextLevel.difficulty, nextLevel.level, { unlocked: true });
        }

        showLevelCompleteOverlay();
        return submitPracticeCompletion().then((saved) => {
            if (saved) {
                window.location.assign(`/dashboard/practice/progression/${selectedGameMode}/`);
            }
            return saved;
        }).catch(() => {
            window.location.assign(`/dashboard/practice/progression/${selectedGameMode}/`);
            return false;
        });
    }

    function goToFreeModeCard(nextIndex) {
        if (!items.length) return false;
        const safeIndex = Math.max(0, Math.min(items.length - 1, nextIndex));
        const movedForward = safeIndex > scrollCurrentIndex;
        if (movedForward) {
            persistFreeModeCardProgress(scrollCurrentIndex);
        }

        scrollCurrentIndex = safeIndex;
        if (scrollsTrack) scrollsTrack.style.transform = `translateY(-${scrollCurrentIndex * 100}%)`;
        updateFreeModeProgress();

        if (scrollCurrentIndex >= items.length - 1) {
            const finalEntry = persistFreeModeCardProgress(scrollCurrentIndex);
            if (finalEntry?.completed || scrollCurrentIndex === items.length - 1) {
                completeFreeModeLevel();
                return true;
            }
        }

        return false;
    }

    function handleFreeModeSwipe(direction) {
        if (!items.length || !lockFreeModeGesture()) return;
        if (direction === 'up') {
            goToFreeModeCard(scrollCurrentIndex + 1);
        } else if (direction === 'down') {
            goToFreeModeCard(scrollCurrentIndex - 1);
        }
    }

    function handleFreeModeKeyboard(event) {
        if (!isFreeMode || !items.length) return false;
        const activeElement = document.activeElement;
        if (isInteractiveElement(activeElement)) return false;

        const isSpace = event.key === ' ' || event.key === 'Spacebar' || event.code === 'Space';
        if (isSpace) {
            event.preventDefault();
            if (!lockFreeModeGesture()) return true;
            goToFreeModeCard(scrollCurrentIndex + 1);
            return true;
        }

        if (event.key === 'Escape') {
            event.preventDefault();
            if (!lockFreeModeGesture()) return true;
            goToFreeModeCard(scrollCurrentIndex + 1);
            return true;
        }

        return false;
    }

    function hideLevelCompleteOverlay() {
        const overlay = document.getElementById("scrollsLevelOverlay");
        if (overlay) overlay.hidden = true;
    }

    function showLevelCompleteOverlay() {
        const overlay = document.getElementById("scrollsLevelOverlay");
        const title = document.getElementById("scrollsLevelOverlayTitle");
        const message = document.getElementById("scrollsLevelOverlayMessage");
        const action = document.getElementById("scrollsLevelOverlayAction");
        if (!overlay) return;

        const levelContext = getLevelProgressContext();
        const nextLevel = getNextLevelContext(levelContext.mode, levelContext.difficulty, levelContext.level);
        if (title) {
            title.textContent = 'Level Complete';
        }
        if (message) {
            message.textContent = nextLevel
                ? `You finished every card in this level. The next level will be available on the Adventure Map.`
                : 'You finished every card in this level. Great work!';
        }
        if (action) {
            action.href = `/dashboard/practice/progression/${selectedGameMode}/`;
            action.textContent = nextLevel ? 'View Adventure Map' : 'Back to Practice';
        }
        overlay.hidden = false;
    }

    function handleFreeModeReadAttempt() {
        const currentItem = items[scrollCurrentIndex];
        if (!currentItem) return false;

        if (scrollsFeedback) {
            scrollsFeedback.textContent = 'Nice work. Keep going to the next card.';
        }
        if (scrollsStatusPill) {
            scrollsStatusPill.textContent = 'Reading';
        }
        if (scrollRecordBtn) {
            scrollRecordBtn.classList.add('is-read');
        }

        const reachedEnd = goToFreeModeCard(scrollCurrentIndex + 1);
        if (!reachedEnd) {
            hideLevelCompleteOverlay();
        }
        return true;
    }

    function attachFreeModeInteractions() {
        if (!isFreeMode || !scrollsTrack) return;
        scrollsTrack.addEventListener('touchstart', (event) => {
            scrollTouchStartY = event.touches[0]?.clientY || 0;
        }, { passive: true });
        scrollsTrack.addEventListener('touchend', (event) => {
            scrollTouchEndY = event.changedTouches[0]?.clientY || 0;
            const delta = scrollTouchEndY - scrollTouchStartY;
            if (Math.abs(delta) > 110) {
                handleFreeModeSwipe(delta < 0 ? 'up' : 'down');
            }
        }, { passive: true });
        scrollsTrack.addEventListener('wheel', (event) => {
            if (Math.abs(event.deltaY) > 120) {
                event.preventDefault();
                handleFreeModeSwipe(event.deltaY > 0 ? 'up' : 'down');
            }
        }, { passive: false });
        scrollsTrack.addEventListener('click', (event) => {
            const card = event.target.closest('.scrolls-record-btn');
            if (!card) return;
            handleFreeModeReadAttempt();
        });
        if (scrollRecordBtn) {
            scrollRecordBtn.addEventListener('click', () => {
                handleFreeModeReadAttempt();
            });
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
        if (viewMode === 'view' || !materialId || completionSubmitted) return Promise.resolve(false);

        const token = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        if (!token) {
            console.warn("PABASA: Missing CSRF token; practice completion was not saved.");
            return Promise.resolve(false);
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

        return fetch('/record-assessment-completion/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
            body: JSON.stringify(completionPayload)
        })
            .then(response => response.json().then(data => ({ ok: response.ok, data })))
            .then(({ ok, data }) => {
                if (!ok || !data.success) {
                    completionSubmitted = false;
                    console.warn("PABASA: Practice completion was not saved.", data.error || data);
                    return false;
                }
                markMaterialSeen(data.material_id || materialId);
                return true;
            })
            .catch(e => {
                completionSubmitted = false;
                console.warn("PABASA: Practice completion API error", e);
                return false;
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
        // No deferred Done button to clear.
        practiceFeedback.textContent = "Ready when you are.";
        practiceFeedback.style.color = "";
        updateCompletionSummary();
        render();
    }

    skipBtn?.addEventListener("click", function () {
        setCurrentItemOutcome("skipped");
        practiceFeedback.textContent = "Skipped. That item will count as a chance to improve next time.";
        practiceFeedback.style.color = "#b95f44";
        playCoachAnimation('skip');
        updateCompletionSummary();
        render();
    });

    recordBtn?.addEventListener("click", function () {
        setCurrentItemOutcome("read");
        practiceFeedback.textContent = "Nice reading. You earned a practice star.";
        practiceFeedback.style.color = "#0f766e";
        playCoachAnimation('read');
        updateCompletionSummary();
        render();
    });

    nextBtn?.addEventListener("click", function () {
        if (currentIndex < items.length - 1) {
            currentIndex += 1;
            practiceFeedback.textContent = "New item ready. Take your time.";
            playCoachAnimation('next');
            render();
            return;
        }

        showCompletion();
    });

    function isInteractiveElement(element) {
        if (!element) return false;
        const tagName = element.tagName;
        if (!tagName) return false;
        if (["INPUT", "TEXTAREA", "SELECT", "BUTTON", "A"].includes(tagName)) return true;
        return element.isContentEditable;
    }

    document.addEventListener("keydown", function (event) {
        if (event.defaultPrevented) return;
        if (handleFreeModeKeyboard(event)) return;

        const activeElement = document.activeElement;
        if (isInteractiveElement(activeElement)) return;

        const isSpace = event.key === " " || event.key === "Spacebar" || event.code === "Space";
        if (isSpace) {
            if (nextBtn && !nextBtn.disabled) {
                nextBtn.click();
                event.preventDefault();
            }
            return;
        }

        if (event.key === "Escape") {
            if (!shell.classList.contains("is-complete")) {
                showCompletion();
                event.preventDefault();
            }
        }
    });

    practiceAgainBtn?.addEventListener("click", restartPractice);

    if (viewMode === 'view') {
        if (skipBtn) skipBtn.classList.add("d-none");
        if (recordBtn) recordBtn.classList.add("d-none");
        if (starCount) starCount.classList.add("d-none");
        if (practiceFeedback) practiceFeedback.textContent = "Reviewing completed content.";
    }

    if (isFreeMode) {
        attachFreeModeInteractions();
    }

    loadItems();
})();
