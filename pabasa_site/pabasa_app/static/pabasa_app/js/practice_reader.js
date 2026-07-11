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
    let freeModeReadSteps = 0;
    let freeModeSkipSteps = 0;

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
    const practiceNextLevelBtn = document.getElementById("practiceNextLevelBtn");
    const nextLevelAvailabilityMessage = document.getElementById("nextLevelAvailabilityMessage");
    let completionSubmitted = false;
    const practiceSessionCountStorageKey = "pabasa_practice_sessions_completed";

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
    const hasSelectedProgressLevel = urlParams.has("level");
    const selectedProgressLevel = (urlParams.get("level") || "level_1").trim().toLowerCase();
    const isColorMode = selectedGameMode === "color";
    const isHuntMode = selectedGameMode === "hunt";
    const huntFlightBird = document.getElementById("huntFlightBird");
    const huntProgressLabel = document.getElementById("huntProgressLabel");
    const huntDifficultyLabel = document.getElementById("huntDifficultyLabel");
    const huntLevelLabel = document.getElementById("huntLevelLabel");
    const huntReadingStatus = document.getElementById("huntReadingStatus");
    const huntGuideMessage = document.getElementById("huntGuideMessage");
    const huntMapPath = document.getElementById("huntMapPath");
    const huntCheckpoint = document.getElementById("huntCheckpoint");
    const huntCheckpointToast = document.getElementById("huntCheckpointToast");
    const huntWordArea = document.querySelector(".practice-hunt-shell .hunt-word-area");
    const huntWordPosition = document.getElementById("huntWordPosition");
    const colorModeStage = document.getElementById("colorModeStage");
    const colorPracticeText = document.getElementById("colorPracticeText");
    const colorScene = document.getElementById("colorScene");
    const colorSceneBackground = document.getElementById("colorSceneBackground");
    const colorCompleteBurst = document.getElementById("colorCompleteBurst");
    const mascotAnimationElement = document.querySelector("[data-mascot-anim]");
    const mascotAnimationConfig = window.PABASA_MASCOT_ANIMATION_FRAMES || {};
    const colorAssetBase = window.PABASA_COLOR_MODE_ASSET_BASE || "/static/pabasa_app/color_mode/";
    const colorModeScenes = Object.freeze({
        easy: {
            theme: "beach",
            objects: [
                { key: "sand", file: "sand.png", label: "Sand" },
                { key: "sea", file: "sea.png", label: "Sea" },
                { key: "palm_tree", file: "palm_tree.png", label: "Palm Tree" },
                { key: "umbrella", file: "umbrella.png", label: "Beach Umbrella" },
                { key: "clouds", file: "clouds.png", label: "Clouds" },
            ],
        },
        medium: {
            theme: "farm",
            objects: [
                { key: "grass", file: "grass.png", label: "Grass" },
                { key: "barn", file: "barn.png", label: "Barn" },
                { key: "sheep", file: "sheep.png", label: "Sheep" },
                { key: "fence", file: "fence.png", label: "Fence" },
                { key: "clouds", file: "clouds.png", label: "Clouds" },
            ],
        },
        hard: {
            theme: "zoo",
            objects: [
                { key: "pavement", file: "pavement.png", label: "Pavement" },
                { key: "vines", file: "vines.png", label: "Vines" },
                { key: "zookeeper", file: "zookeeper.png", label: "Zookeeper" },
                { key: "elephant", file: "elephant.png", label: "Elephant" },
                { key: "tiger", file: "tiger.png", label: "Tiger" },
            ],
        },
    });
    let colorRevealedCount = 0;
    let colorModeCompletionReady = false;
    let colorCompletionTimer = null;
    let colorNewStarsToCommit = null;
    let colorStarsCommitted = false;
    let colorFinalRevealTimer = null;
    let colorFinalRevealHold = null;
    let huntLevelTransitionInProgress = false;
    let huntAdvanceInProgress = false;
    let mascotAnimationState = "idle";
    let mascotAnimationVersion = 0;
    let mascotAnimationTimer = null;
    let mascotAnimationIdleHoldTimer = null;
    const mascotAnimationFrames = {
        idle: Array.isArray(mascotAnimationConfig.idle) ? mascotAnimationConfig.idle : [],
        reading: Array.isArray(mascotAnimationConfig.reading) ? mascotAnimationConfig.reading : [],
        next: Array.isArray(mascotAnimationConfig.next) ? mascotAnimationConfig.next : [],
        skip: Array.isArray(mascotAnimationConfig.skip) ? mascotAnimationConfig.skip : [],
    };
    const mascotAnimationPriority = {
        idle: 0,
        skip: 1,
        next: 2,
        reading: 3,
    };
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

    function toggleFreeModeBodyLock(enabled) {
        document.body.classList.toggle("practice-free-mode", Boolean(enabled));
    }

    function clearMascotAnimationTimer() {
        if (mascotAnimationTimer) {
            window.clearTimeout(mascotAnimationTimer);
            mascotAnimationTimer = null;
        }
    }

    function clearMascotAnimationIdleHold() {
        if (mascotAnimationIdleHoldTimer) {
            window.clearTimeout(mascotAnimationIdleHoldTimer);
            mascotAnimationIdleHoldTimer = null;
        }
    }

    function preloadMascotFrameSets() {
        Object.values(mascotAnimationFrames).flat().forEach((frameSrc) => {
            const image = new Image();
            image.decoding = "async";
            image.src = frameSrc;
        });
    }

    function playMascotFrameSet(state, options = {}) {
        if (!mascotAnimationElement) return;
        const frames = mascotAnimationFrames[state] || mascotAnimationFrames.idle;
        const { loop = true, holdIdle = false, duration = 220 } = options;
        if (!frames.length) return;

        mascotAnimationState = state;
        mascotAnimationVersion += 1;
        const version = mascotAnimationVersion;
        clearMascotAnimationTimer();

        let frameIndex = 0;
        const renderFrame = () => {
            if (!mascotAnimationElement || version !== mascotAnimationVersion) return;
            mascotAnimationElement.src = frames[frameIndex];
            frameIndex += 1;

            if (loop) {
                frameIndex %= frames.length;
            } else if (frameIndex >= frames.length) {
                if (holdIdle && state !== "idle") {
                    clearMascotAnimationIdleHold();
                    mascotAnimationIdleHoldTimer = window.setTimeout(() => {
                        mascotAnimationIdleHoldTimer = null;
                        if (version === mascotAnimationVersion) {
                            playMascotFrameSet("idle", { loop: true, duration: 220 });
                        }
                    }, 140);
                } else if (state !== "idle") {
                    playMascotFrameSet("idle", { loop: true, duration: 220 });
                }
                return;
            }

            mascotAnimationTimer = window.setTimeout(renderFrame, duration);
        };

        renderFrame();
    }

    function setMascotState(nextState, options = {}) {
        if (!mascotAnimationElement) return;
        const currentPriority = mascotAnimationPriority[mascotAnimationState] ?? 0;
        const nextPriority = mascotAnimationPriority[nextState] ?? 0;
        const force = Boolean(options.force);

        if (!force && nextPriority < currentPriority) {
            return;
        }

        clearMascotAnimationIdleHold();
        const duration = options.duration || (nextState === "idle" ? 220 : 160);
        playMascotFrameSet(nextState, {
            loop: options.loop !== undefined ? options.loop : nextState === "idle" || nextState === "reading",
            holdIdle: Boolean(options.holdIdle),
            duration,
        });
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

    function formatHuntLabel(value, fallback) {
        return String(value || fallback || "")
            .replace(/_/g, " ")
            .replace(/\b\w/g, (letter) => letter.toUpperCase());
    }

    function updateHuntVisuals() {
        if (!isHuntMode) return;

        const total = Math.max(items.length, 1);
        const position = Math.min(currentIndex + 1, total);
        const percentage = Math.round((position / total) * 100);
        const feedbackText = practiceFeedback?.textContent || "Ready when you are.";

        const dots = document.querySelectorAll("[data-hunt-dot]");
        dots.forEach((dot, index) => {
            dot.classList.toggle("is-active", index === currentIndex);
            dot.classList.toggle("is-complete", index < currentIndex);
        });
        const activeDot = dots[currentIndex];
        if (huntFlightBird && activeDot && huntFlightBird.parentElement !== activeDot) {
            activeDot.appendChild(huntFlightBird);
        }
        if (huntMapPath) {
            huntMapPath.setAttribute("aria-valuenow", String(position));
        }
        if (huntCheckpoint) huntCheckpoint.classList.toggle("is-earned", currentIndex >= 3);
        if (huntProgressLabel) huntProgressLabel.textContent = `${formatHuntLabel(mode, "word")} ${position} of ${total}`;
        if (huntWordPosition) huntWordPosition.textContent = `${formatHuntLabel(mode, "word")} ${position} of ${total}`;
        if (huntDifficultyLabel) huntDifficultyLabel.textContent = formatHuntLabel(selectedDifficulty, "easy");
        if (huntLevelLabel) huntLevelLabel.textContent = formatHuntLabel(selectedProgressLevel, "level_1");
        if (huntReadingStatus) huntReadingStatus.textContent = feedbackText;
        if (huntGuideMessage) huntGuideMessage.textContent = feedbackText;
        if (practiceProgress?.parentElement) practiceProgress.parentElement.setAttribute("aria-valuenow", String(percentage));
    }

    function getColorSceneConfig() {
        return colorModeScenes[selectedDifficulty] || colorModeScenes.easy;
    }

    function getColorAssetUrl(theme, file) {
        return `${colorAssetBase}${theme}/${file}`;
    }

    function getColorSceneRevealTargetCount() {
        const availableItems = items.length > 0 ? items.length : 5;
        return Math.min(5, getColorSceneConfig().objects.length || 5, availableItems);
    }

    function updateColorModeControls() {
        if (!isColorMode || !skipBtn || !recordBtn || !nextBtn) return;

        if (colorModeCompletionReady) {
            skipBtn.classList.add("d-none");
            recordBtn.classList.add("d-none");
            nextBtn.textContent = "Finish";
            nextBtn.disabled = false;
        } else {
            skipBtn.classList.remove("d-none");
            recordBtn.classList.remove("d-none");
            nextBtn.textContent = "Next";
            nextBtn.disabled = false;
        }
    }

    function setupColorModeScene() {
        if (!isColorMode || !colorModeStage || !colorScene || !colorSceneBackground) return;

        const config = getColorSceneConfig();
        shell.classList.add("practice-color");
        colorModeStage.setAttribute("aria-hidden", "false");
        colorScene.dataset.theme = config.theme;
        colorSceneBackground.src = getColorAssetUrl(config.theme, "background.png");
        colorSceneBackground.alt = `${config.theme} scene background`;
        colorCompleteBurst?.classList.remove("is-visible");
        colorScene.querySelectorAll(".color-scene-object").forEach((object) => object.remove());

        config.objects.forEach((object, index) => {
            const layer = document.createElement("img");
            layer.className = "color-scene-object";
            layer.dataset.colorObject = object.key;
            layer.dataset.index = String(index);
            layer.src = getColorAssetUrl(config.theme, object.file);
            layer.alt = "";
            colorScene.appendChild(layer);
        });

        colorRevealedCount = 0;
        colorModeCompletionReady = false;
        colorNewStarsToCommit = null;
        colorStarsCommitted = false;
        if (colorFinalRevealTimer) {
            window.clearTimeout(colorFinalRevealTimer);
            colorFinalRevealTimer = null;
        }
        if (colorFinalRevealHold) {
            window.clearTimeout(colorFinalRevealHold);
            colorFinalRevealHold = null;
        }
        hideLevelCompleteOverlay();
        if (colorCompletionTimer) {
            window.clearTimeout(colorCompletionTimer);
            colorCompletionTimer = null;
        }
    }

    function updateColorModeReadingText() {
        if (!isColorMode || !colorPracticeText) return;
        colorPracticeText.textContent = items[currentIndex] || "No materials available.";
    }

    function advanceColorModeFromKeyboard(options = {}) {
        if (!items.length) return false;
        const { countAsSkip = false, countAsRead = false } = options;

        if (countAsSkip) {
            setCurrentItemOutcome("skipped");
        } else if (countAsRead) {
            setCurrentItemOutcome("read");
            revealNextColorObject();
            if (colorFinalRevealTimer) {
                window.clearTimeout(colorFinalRevealTimer);
                colorFinalRevealTimer = null;
            }
            if (colorFinalRevealHold) {
                window.clearTimeout(colorFinalRevealHold);
                colorFinalRevealHold = null;
            }
        }

        if (currentIndex < items.length - 1) {
            currentIndex += 1;
            practiceFeedback.textContent = "New item ready. Take your time.";
            practiceFeedback.classList.remove("is-success", "is-warning");
            playCoachAnimation('next');
            render();
            return true;
        }

        if (isColorMode && colorModeCompletionReady) {
            colorFinalRevealHold = window.setTimeout(() => {
                colorFinalRevealHold = null;
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => {
                        colorFinalRevealTimer = window.setTimeout(() => {
                            colorFinalRevealTimer = null;
                            completeColorModeLevel();
                        }, 900);
                    });
                });
            }, 0);
            return true;
        }

        showCompletion();
        return true;
    }

    function handleColorModeKeyboard(event) {
        if (!isColorMode || !items.length) return false;
        const activeElement = document.activeElement;
        if (isInteractiveElement(activeElement)) return false;

        if (event.key === 'ArrowUp') {
            event.preventDefault();
            advanceColorModeFromKeyboard({ countAsRead: true });
            return true;
        }

        if (event.key === 'ArrowDown') {
            event.preventDefault();
            advanceColorModeFromKeyboard({ countAsSkip: true });
            return true;
        }

        const isSpace = event.key === ' ' || event.key === 'Spacebar' || event.code === 'Space';
        if (isSpace) {
            event.preventDefault();
            advanceColorModeFromKeyboard({ countAsRead: true });
            return true;
        }

        if (event.key === 'Escape') {
            event.preventDefault();
            advanceColorModeFromKeyboard({ countAsSkip: true });
            return true;
        }

        return false;
    }

    function advanceHuntModeFromKeyboard(options = {}) {
        if (!items.length) return false;
        const { countAsSkip = false, countAsRead = false } = options;

        if (countAsSkip) {
            setCurrentItemOutcome("skipped");
            practiceFeedback.textContent = "Skipped. Keep chasing the treasure!";
            practiceFeedback.classList.remove("is-success");
            practiceFeedback.classList.add("is-warning");
            playCoachAnimation('skip');
        } else if (countAsRead) {
            setCurrentItemOutcome("read");
            practiceFeedback.textContent = "Nice reading. Keep flying forward!";
            practiceFeedback.classList.remove("is-warning");
            practiceFeedback.classList.add("is-success");
            playCoachAnimation('read');
        }

        updateCompletionSummary();
        render();
        return true;
    }

    function handleHuntModeKeyboard(event) {
        if (!isHuntMode || !items.length) return false;
        const activeElement = document.activeElement;
        if (isInteractiveElement(activeElement)) return false;

        if (event.key === 'ArrowUp') {
            event.preventDefault();
            advanceHuntModeFromKeyboard({ countAsRead: true });
            return true;
        }

        if (event.key === 'ArrowDown') {
            event.preventDefault();
            advanceHuntModeFromKeyboard({ countAsSkip: true });
            return true;
        }

        const isSpace = event.key === ' ' || event.key === 'Spacebar' || event.code === 'Space';
        if (isSpace) {
            event.preventDefault();
            advanceHuntModeFromKeyboard({ countAsRead: true });
            return true;
        }

        if (event.key === 'Escape') {
            event.preventDefault();
            advanceHuntModeFromKeyboard({ countAsSkip: true });
            return true;
        }

        return false;
    }

    function revealNextColorObject() {
        if (!isColorMode || !colorScene) return false;
        const config = getColorSceneConfig();
        const maxRevealCount = Math.min(config.objects.length, items.length || config.objects.length);
        if (colorRevealedCount >= maxRevealCount) return false;

        const objectLayer = colorScene.querySelector(`.color-scene-object[data-index="${colorRevealedCount}"]`);
        if (objectLayer) {
            objectLayer.classList.add("is-revealed");
        }
        colorRevealedCount += 1;
        colorModeCompletionReady = colorRevealedCount >= getColorSceneRevealTargetCount();
        updateColorModeControls();
        return true;
    }

    function getMaterialForLevel(context) {
        return getServerPracticeMaterials().find((material) => {
            if (!material) return false;
            const materialType = normalizeMaterialValue(material.item_type || material.type).toLowerCase();
            const materialDifficulty = normalizeMaterialValue(material.difficulty || material.difficulty_level).toLowerCase();
            const materialLevel = normalizeMaterialValue(material.level).toLowerCase();
            return materialType === mode
                && materialDifficulty === context.difficulty
                && materialLevel === context.level;
        }) || null;
    }

    function getPracticeProgressionUrl(context) {
        const nextMaterial = getMaterialForLevel(context);
        const query = new URLSearchParams({
            game: context.mode,
            difficulty: context.difficulty,
            level: context.level,
        });
        if (nextMaterial?.id !== undefined && nextMaterial?.id !== null) {
            query.set("id", String(nextMaterial.id));
        }
        return `/dashboard/practice/${mode}/?${query.toString()}`;
    }

    function getPracticeProgressionMapUrl(modeContext = selectedGameMode) {
        return `/dashboard/practice/progression/${modeContext || "word"}/`;
    }

    function getPracticeModeMaterialForLevel(context) {
        if (!context) return null;
        return getServerPracticeMaterials().find((material) => {
            if (!material) return false;
            const materialGameMode = normalizeMaterialValue(material.game_mode || material.mode).toLowerCase();
            const materialDifficulty = normalizeMaterialValue(material.difficulty || material.difficulty_level).toLowerCase();
            const materialLevel = normalizeMaterialValue(material.level).toLowerCase();
            return materialGameMode === context.mode
                && materialDifficulty === context.difficulty
                && materialLevel === context.level;
        }) || null;
    }

    function getPracticeModeLevelUrl(context, material) {
        const materialType = normalizeMaterialValue(material?.item_type || material?.type || "word").toLowerCase();
        const readerType = materialType === "paragraph" ? "paragraph" : materialType === "sentence" ? "sentence" : "word";
        const query = new URLSearchParams({
            id: String(material.id),
            game: context.mode,
            difficulty: context.difficulty,
            level: context.level,
        });
        return `/dashboard/practice/${readerType}/?${query.toString()}`;
    }

    function configureNextLevelAction() {
        if (!practiceNextLevelBtn) return null;
        const levelContext = getLevelProgressContext();
        const nextLevel = getNextLevelContext(levelContext.mode, levelContext.difficulty, levelContext.level);
        const nextMaterial = getPracticeModeMaterialForLevel(nextLevel);
        const isAvailable = Boolean(nextLevel && nextMaterial);

        practiceNextLevelBtn.classList.toggle("is-disabled", !isAvailable);
        practiceNextLevelBtn.setAttribute("aria-disabled", isAvailable ? "false" : "true");
        practiceNextLevelBtn.title = isAvailable ? "Continue to the next level" : "Next level not available.";
        practiceNextLevelBtn.href = isAvailable ? getPracticeModeLevelUrl(nextLevel, nextMaterial) : "#";
        if (nextLevelAvailabilityMessage) {
            nextLevelAvailabilityMessage.classList.toggle("is-visible", !isAvailable);
            nextLevelAvailabilityMessage.textContent = isAvailable ? "" : "Next level not available.";
        }
        return isAvailable ? { context: nextLevel, material: nextMaterial } : null;
    }

    function completeHuntModeLevel() {
        if (!isHuntMode || huntLevelTransitionInProgress) return false;
        huntLevelTransitionInProgress = true;

        const levelContext = getLevelProgressContext();
        const progressState = getPracticeProgressState();
        const entry = ensureLevelProgressEntry(progressState, levelContext.mode, levelContext.difficulty, levelContext.level);
        const metrics = getCompletionMetrics();
        entry.cards_completed = Math.max(entry.cards_completed || 0, items.length);
        entry.completed_cards = Array.from({ length: items.length }, (_, index) => index);
        entry.unlocked = true;
        entry.completed = true;
        entry.stars_earned = Math.max(Number(entry.stars_earned || 0) || 0, metrics.earnedStars);
        progressState[levelContext.mode][levelContext.difficulty][levelContext.level] = entry;
        savePracticeProgressState(progressState);

        const nextLevel = getNextLevelContext(levelContext.mode, levelContext.difficulty, levelContext.level);
        const nextMaterial = getPracticeModeMaterialForLevel(nextLevel);
        if (nextLevel && nextMaterial) {
            saveLevelProgressEntry(nextLevel.mode, nextLevel.difficulty, nextLevel.level, { unlocked: true });
        }

        if (nextBtn) nextBtn.disabled = true;
        if (recordBtn) recordBtn.disabled = true;
        if (skipBtn) skipBtn.disabled = true;
        if (practiceFeedback) practiceFeedback.textContent = "Level complete. Saving your reading journey...";

        showCompletion();
        return true;
    }

    function completeColorModeLevel() {
        if (!isColorMode || !colorModeCompletionReady) return false;

        const levelContext = getLevelProgressContext();
        const progressState = getPracticeProgressState();
        const entry = ensureLevelProgressEntry(progressState, levelContext.mode, levelContext.difficulty, levelContext.level);
        const serverSavedStars = Math.max(0, Number(getActiveMaterialMeta()?.stars_earned || 0) || 0);
        const previouslySavedStars = Math.max(0, Number(entry.stars_earned || 0) || 0, serverSavedStars);
        const sessionStars = Math.max(0, correctResponses * 10);
        colorNewStarsToCommit = Math.max(0, sessionStars - previouslySavedStars);
        colorStarsCommitted = false;
        entry.cards_completed = Math.max(entry.cards_completed || 0, Math.min(items.length, 5));
        entry.completed_cards = Array.from({ length: Math.min(items.length, 5) }, (_, index) => index);
        entry.unlocked = true;
        entry.completed = true;
        entry.stars_earned = Math.max(previouslySavedStars, sessionStars);
        progressState[levelContext.mode][levelContext.difficulty][levelContext.level] = entry;
        savePracticeProgressState(progressState);

        const nextLevel = getNextLevelContext(levelContext.mode, levelContext.difficulty, levelContext.level);
        const nextLevelIsAvailable = Boolean(nextLevel && getPracticeModeMaterialForLevel(nextLevel));
        if (nextLevelIsAvailable) {
            saveLevelProgressEntry(nextLevel.mode, nextLevel.difficulty, nextLevel.level, { unlocked: true });
        }

        if (colorCompleteBurst) {
            colorCompleteBurst.classList.add("is-visible");
        }
        if (practiceFeedback) {
            practiceFeedback.textContent = "Scene complete! Great work.";
            practiceFeedback.classList.remove("is-warning");
            practiceFeedback.classList.add("is-success");
        }
        if (nextBtn) nextBtn.disabled = true;
        if (recordBtn) recordBtn.disabled = true;
        if (skipBtn) skipBtn.disabled = true;
        colorModeCompletionReady = false;

        showCompletion();
        return true;
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

        const materialLevel = normalizeMaterialValue(material.level || selectedProgressLevel || "").toLowerCase();
        const requestedLevel = hasSelectedProgressLevel ? normalizeMaterialValue(selectedProgressLevel).toLowerCase() : "";
        if (requestedLevel && materialLevel && materialLevel !== requestedLevel) return false;

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
            items = isHuntMode ? serverItems.slice(0, 5) : serverItems.slice();
            currentIndex = 0;
            itemOutcomes = Array(items.length).fill(null);
            setupColorModeScene();
            if (isFreeMode) {
                toggleFreeModeBodyLock(true);
                renderFreeMode();
            } else {
                toggleFreeModeBodyLock(false);
                render();
            }
            preloadMascotFrameSets();
            setMascotState("idle", { loop: true, duration: 220, force: true });
            setCoachAnimationSource(initialCoachAnimation);
            return;
        }

        items = [];
        itemOutcomes = [];
        setupColorModeScene();
        if (practiceText) practiceText.textContent = "No materials available.";
        updateColorModeReadingText();
        if (practiceCounter) practiceCounter.textContent = "No items";
        if (practiceProgress) practiceProgress.style.width = "0%";
        if (nextBtn) nextBtn.disabled = true;
        toggleFreeModeBodyLock(isFreeMode);
        preloadMascotFrameSets();
        setMascotState("idle", { loop: true, duration: 220, force: true });
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

    function recordFreeModeSkip(currentCardIndex = scrollCurrentIndex) {
        if (!Number.isInteger(currentCardIndex) || currentCardIndex < 0 || currentCardIndex >= items.length) return;
        if (itemOutcomes[currentCardIndex] !== "skipped") {
            itemOutcomes[currentCardIndex] = "skipped";
            incorrectResponses = itemOutcomes.filter((outcome) => outcome === "skipped").length;
            correctResponses = itemOutcomes.filter((outcome) => outcome === "read").length;
            starsEarned = correctResponses * 10;
        }
    }

    function getCompletionMetrics() {
        const totalItems = items.reduce((total, item) => total + countWords(item), 0);
        const readItemCount = itemOutcomes.reduce((total, outcome) => total + (outcome === "read" ? 1 : 0), 0);
        const skippedItemCount = itemOutcomes.reduce((total, outcome) => total + (outcome === "skipped" ? 1 : 0), 0);
        const totalReadWordsRaw = itemOutcomes.reduce((total, outcome, index) => {
            return outcome === "read" ? total + getItemWordCount(index) : total;
        }, 0);
        const totalSkippedWordsRaw = itemOutcomes.reduce((total, outcome, index) => {
            return outcome === "skipped" ? total + getItemWordCount(index) : total;
        }, 0);
        const totalReadWords = isFreeMode
            ? Math.max(readItemCount, freeModeReadSteps)
            : (totalReadWordsRaw > 0 ? totalReadWordsRaw : readItemCount);
        const totalSkippedWords = isFreeMode
            ? Math.max(skippedItemCount, freeModeSkipSteps)
            : (totalSkippedWordsRaw > 0 ? totalSkippedWordsRaw : skippedItemCount);
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
        updateColorModeReadingText();
        updateColorModeControls();
        const label = mode.charAt(0).toUpperCase() + mode.slice(1);
        practiceCounter.textContent = `${label} ${currentIndex + 1}/${items.length}`;
        practiceProgress.style.width = `${((currentIndex + 1) / items.length) * 100}%`;
        updateHuntVisuals();
        updateCompletionSummary();
        if (nextBtn) {
            nextBtn.textContent = currentIndex === items.length - 1 ? (viewMode === 'view' ? "Exit" : "Finish") : "Next";
            nextBtn.disabled = isHuntMode && viewMode !== 'view'
                ? !itemOutcomes[currentIndex] || huntAdvanceInProgress
                : false;
        }
    }

    function renderFreeMode() {
        if (!scrollsTrack) return;
        if (!items.length) {
            scrollsTrack.innerHTML = '<div class="scrolls-card"><p class="scrolls-card-text">No reading cards are available right now.</p></div>';
            return;
        }

        const currentLevelContext = getLevelProgressContext();
        const levelEntry = ensureLevelProgressEntry(getPracticeProgressState(), currentLevelContext.mode, currentLevelContext.difficulty, currentLevelContext.level);
        const completedCards = new Set(levelEntry.completed_cards || []);

        const cardMarkup = items.map((item, index) => {
            const isComplete = completedCards.has(index);
            return `
                <section class="scrolls-card${isComplete ? ' is-complete' : ''}" data-index="${index}">
                    <h2 class="scrolls-card-text">${escapeHtml(item)}</h2>
                    <p class="scrolls-hint">Swipe up for the next challenge</p>
                </section>`;
        }).join('');

        scrollsTrack.innerHTML = cardMarkup;
        scrollsTrack.style.transform = `translateY(-${scrollCurrentIndex * 100}%)`;
        updateFreeModeProgress();
    }

    function setFreeModeReadButton(isComplete) {
        if (!scrollRecordBtn) return;
        scrollRecordBtn.classList.toggle('is-read', isComplete);
        scrollRecordBtn.innerHTML = isComplete
            ? '<i class="bi bi-check-circle-fill"></i> Completed'
            : '<i class="bi bi-mic-fill"></i> Read aloud';
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
        const currentCardIsComplete = Array.isArray(levelEntry.completed_cards) && levelEntry.completed_cards.includes(current);
        const isFinalCard = current === items.length - 1;

        if (scrollsProgressBarFill) scrollsProgressBarFill.style.width = `${progressPercent}%`;
        if (scrollsProgressMeta) {
            scrollsProgressMeta.textContent = levelEntry.completed
                ? 'Level complete! The next challenge is unlocked.'
                : isFinalCard
                    ? 'Swipe up to finish the challenge.'
                    : 'Swipe up for the next challenge';
        }
        if (scrollsAppTitle) scrollsAppTitle.textContent = titleText;
        if (scrollsDifficultyPill) scrollsDifficultyPill.textContent = difficultyLabelText || 'Easy';
        if (scrollsLevelPill) scrollsLevelPill.textContent = levelLabelText || 'Level 2';
        if (scrollsProgressPill) scrollsProgressPill.textContent = `Card ${current + 1} of ${items.length}`;
        if (scrollsStatusPill) scrollsStatusPill.textContent = levelEntry.completed ? 'Level complete' : completedCards > 0 ? `${completedCards} completed` : 'Ready';
        if (scrollsDots) {
            scrollsDots.innerHTML = items.map((_, index) => `<span class="${index === current ? 'is-active' : ''}"></span>`).join('');
        }
        setFreeModeReadButton(currentCardIsComplete);
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

        return showCompletion();
    }

    function goToFreeModeCard(nextIndex, options = {}) {
        if (!items.length) return false;
        const safeIndex = Math.max(0, Math.min(items.length - 1, nextIndex));
        const movedForward = safeIndex > scrollCurrentIndex;
        if (movedForward) {
            if (options.countAsSkip) {
                recordFreeModeSkip(scrollCurrentIndex);
            }
            persistFreeModeCardProgress(scrollCurrentIndex);
        }

        scrollCurrentIndex = safeIndex;
        if (scrollsTrack) scrollsTrack.style.transform = `translateY(-${scrollCurrentIndex * 100}%)`;
        updateFreeModeProgress();
        return false;
    }

    function handleFreeModeSwipe(direction) {
        if (!items.length || !lockFreeModeGesture()) return;
        if (direction === 'up') {
            if (scrollCurrentIndex >= items.length - 1) {
                persistFreeModeCardProgress(scrollCurrentIndex);
                completeFreeModeLevel();
                return;
            }
            goToFreeModeCard(scrollCurrentIndex + 1);
        } else if (direction === 'down') {
            goToFreeModeCard(scrollCurrentIndex + 1, { countAsSkip: true });
        }
    }

    function advanceFreeModeFromKeyboard(options = {}) {
        if (!items.length) return false;
        const { countAsSkip = false, countAsRead = false } = options;

        if (countAsSkip) {
            freeModeSkipSteps += 1;
            setCurrentItemOutcome("skipped");
        } else if (countAsRead) {
            freeModeReadSteps += 1;
            setCurrentItemOutcome("read");
        }

        if (scrollCurrentIndex >= items.length - 1) {
            persistFreeModeCardProgress(scrollCurrentIndex);
            completeFreeModeLevel();
            return true;
        }

        goToFreeModeCard(scrollCurrentIndex + 1, { countAsSkip });
        return true;
    }

    function handleFreeModeKeyboard(event) {
        if (!isFreeMode || !items.length) return false;
        const activeElement = document.activeElement;
        if (isInteractiveElement(activeElement)) return false;

        if (event.key === 'ArrowUp') {
            event.preventDefault();
            advanceFreeModeFromKeyboard({ countAsRead: true });
            return true;
        }

        if (event.key === 'ArrowDown') {
            event.preventDefault();
            advanceFreeModeFromKeyboard({ countAsSkip: true });
            return true;
        }

        const isSpace = event.key === ' ' || event.key === 'Spacebar' || event.code === 'Space';
        if (isSpace) {
            event.preventDefault();
            advanceFreeModeFromKeyboard({ countAsRead: true });
            return true;
        }

        if (event.key === 'Escape') {
            event.preventDefault();
            advanceFreeModeFromKeyboard({ countAsSkip: true });
            return true;
        }

        return false;
    }

    function hideLevelCompleteOverlay() {
        const overlay = document.getElementById("scrollsLevelOverlay");
        if (overlay) overlay.hidden = true;
    }

    function showLevelCompleteOverlay(options = {}) {
        const overlay = document.getElementById("scrollsLevelOverlay");
        const title = document.getElementById("scrollsLevelOverlayTitle");
        const message = document.getElementById("scrollsLevelOverlayMessage");
        const action = document.getElementById("scrollsLevelOverlayAction");
        if (!overlay) return false;

        const levelContext = getLevelProgressContext();
        const nextLevel = options.nextLevelContext || getNextLevelContext(levelContext.mode, levelContext.difficulty, levelContext.level);
        const actionLabel = options.actionLabel || (nextLevel ? 'View Adventure Map' : 'Back to Practice');
        const actionUrl = options.actionUrl || (nextLevel ? getPracticeProgressionUrl(nextLevel) : `/dashboard/practice/progression/${selectedGameMode}/`);
        if (title) {
            title.textContent = options.title || 'Level Complete';
        }
        if (message) {
            message.textContent = options.message || (nextLevel
                ? `You finished every card in this level. The next level will be available on the Adventure Map.`
                : 'You finished every card in this level. Great work!');
        }
        if (action) {
            action.href = actionUrl;
            action.textContent = actionLabel;
        }
        overlay.hidden = false;
        return true;
    }

    function handleFreeModeReadAttempt() {
        const currentItem = items[scrollCurrentIndex];
        if (!currentItem) return false;

        freeModeReadSteps += 1;
        setCurrentItemOutcome("read");
        if (scrollsFeedback) {
            scrollsFeedback.textContent = 'Nice work. Keep going to the next card.';
        }
        if (scrollsStatusPill) {
            scrollsStatusPill.textContent = 'Reading';
        }
        persistFreeModeCardProgress(scrollCurrentIndex);
        scrollsTrack?.querySelector(`.scrolls-card[data-index="${scrollCurrentIndex}"]`)?.classList.add('is-complete');
        setFreeModeReadButton(true);

        window.setTimeout(() => {
            if (scrollCurrentIndex >= items.length - 1) {
                persistFreeModeCardProgress(scrollCurrentIndex);
                completeFreeModeLevel();
                return;
            }
            goToFreeModeCard(scrollCurrentIndex + 1);
            hideLevelCompleteOverlay();
        }, 320);
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
                if (delta < 0) {
                    handleFreeModeSwipe('up');
                } else {
                    handleFreeModeSwipe('down');
                }
            }
        }, { passive: true });
        scrollsTrack.addEventListener('wheel', (event) => {
            if (Math.abs(event.deltaY) > 120) {
                event.preventDefault();
                if (event.deltaY > 0) {
                    handleFreeModeSwipe('up');
                } else {
                    handleFreeModeSwipe('down');
                }
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
            game_mode: selectedGameMode,
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

    function trackPracticeSessionCompletion() {
        const parsedCurrentCount = Number.parseInt(localStorage.getItem(practiceSessionCountStorageKey) || "0", 10);
        const currentCount = Number.isFinite(parsedCurrentCount) ? parsedCurrentCount : 0;
        const nextCount = currentCount + 1;
        localStorage.setItem(practiceSessionCountStorageKey, String(nextCount));
        window.dispatchEvent(new CustomEvent("pabasa:practice-session-count-updated", { detail: { count: nextCount } }));
        try {
            window.dispatchEvent(new StorageEvent("storage", { key: practiceSessionCountStorageKey }));
        } catch (error) {
            window.dispatchEvent(new Event("storage"));
        }
    }

    function showCompletion() {
        shell.classList.add("is-complete");
        updateCompletionSummary();
        configureNextLevelAction();

        // Skip updating stats if in view mode
        if (viewMode === 'view') return Promise.resolve(false);

        const metrics = getCompletionMetrics();

        // Persist stars to total progress
        const parsedCurrentTotal = Number.parseInt(localStorage.getItem("pabasa_total_stars") || "0", 10);
        const currentTotal = Math.max(0, Number.isFinite(parsedCurrentTotal) ? parsedCurrentTotal : 0);
        let newlyEarnedStars = Math.max(0, Number(metrics.earnedStars) || 0);
        if (isColorMode) {
            if (colorNewStarsToCommit === null) {
                const levelContext = getLevelProgressContext();
                const progressState = getPracticeProgressState();
                const savedEntry = getStoredLevelEntry(progressState, levelContext.mode, levelContext.difficulty, levelContext.level);
                const serverSavedStars = Math.max(0, Number(getActiveMaterialMeta()?.stars_earned || 0) || 0);
                const savedStars = Math.max(0, Number(savedEntry.stars_earned || 0) || 0, serverSavedStars);
                colorNewStarsToCommit = Math.max(0, newlyEarnedStars - savedStars);
            }
            newlyEarnedStars = colorStarsCommitted ? 0 : Math.max(0, colorNewStarsToCommit || 0);
            colorStarsCommitted = true;
        }
        localStorage.setItem("pabasa_total_stars", String(currentTotal + newlyEarnedStars));

        trackPracticeSessionCompletion();
        const completionRequest = submitPracticeCompletion();

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

        return completionRequest;
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
        freeModeReadSteps = 0;
        freeModeSkipSteps = 0;
        colorModeCompletionReady = false;
        colorNewStarsToCommit = null;
        colorStarsCommitted = false;
        huntLevelTransitionInProgress = false;
        huntAdvanceInProgress = false;
        huntCheckpointToast?.setAttribute("hidden", "");
        huntWordArea?.classList.remove("is-closing");
        hideLevelCompleteOverlay();
        // No deferred Done button to clear.
        if (recordBtn) recordBtn.disabled = false;
        if (skipBtn) skipBtn.disabled = false;
        setupColorModeScene();
        practiceFeedback.textContent = "Ready when you are.";
        practiceFeedback.classList.remove("is-success", "is-warning");
        updateCompletionSummary();
        render();
    }

    skipBtn?.addEventListener("click", function () {
        setCurrentItemOutcome("skipped");
        practiceFeedback.textContent = "Skipped. That item will count as a chance to improve next time.";
        practiceFeedback.classList.remove("is-success");
        practiceFeedback.classList.add("is-warning");
        setMascotState("skip", { loop: false, holdIdle: true, duration: 150, force: true });
        playCoachAnimation('skip');
        updateCompletionSummary();
        render();
    });

    recordBtn?.addEventListener("pointerdown", function () {
        setMascotState("reading", { loop: true, duration: 220, force: true });
    });

    recordBtn?.addEventListener("pointerup", function () {
        if (mascotAnimationState === "reading") {
            setMascotState("idle", { loop: true, duration: 220, force: true });
        }
    });

    recordBtn?.addEventListener("pointercancel", function () {
        if (mascotAnimationState === "reading") {
            setMascotState("idle", { loop: true, duration: 220, force: true });
        }
    });

    recordBtn?.addEventListener("pointerleave", function () {
        if (mascotAnimationState === "reading") {
            setMascotState("idle", { loop: true, duration: 220, force: true });
        }
    });

    recordBtn?.addEventListener("click", function () {
        const wasAlreadyRead = itemOutcomes[currentIndex] === "read";
        setCurrentItemOutcome("read");
        const revealedObject = wasAlreadyRead ? false : revealNextColorObject();
        if (colorFinalRevealTimer) {
            window.clearTimeout(colorFinalRevealTimer);
            colorFinalRevealTimer = null;
        }
        if (colorFinalRevealHold) {
            window.clearTimeout(colorFinalRevealHold);
            colorFinalRevealHold = null;
        }
        practiceFeedback.textContent = "Nice reading. You earned a practice star.";
        practiceFeedback.classList.remove("is-warning");
        practiceFeedback.classList.add("is-success");
        setMascotState("reading", { loop: true, duration: 220, force: true });
        clearMascotAnimationIdleHold();
        mascotAnimationIdleHoldTimer = window.setTimeout(() => {
            mascotAnimationIdleHoldTimer = null;
            if (mascotAnimationState === "reading") {
                setMascotState("idle", { loop: true, duration: 145, force: true });
            }
        }, 700);
        playCoachAnimation('read');
        updateCompletionSummary();
        if (isColorMode && revealedObject && colorModeCompletionReady) {
            practiceFeedback.textContent = "All 5 scene details have been revealed. Tap Finish to complete the scene.";
            practiceFeedback.classList.remove("is-warning");
            practiceFeedback.classList.add("is-success");
        }
        if (isColorMode && colorModeCompletionReady && currentIndex >= items.length - 1) {
            colorFinalRevealTimer = window.setTimeout(() => {
                colorFinalRevealTimer = null;
                completeColorModeLevel();
            }, 180);
            render();
            return;
        }
        render();
    });

    nextBtn?.addEventListener("click", function () {
        if (isColorMode) {
            if (colorModeCompletionReady) {
                setMascotState("next", { loop: false, holdIdle: true, duration: 150, force: true });
                completeColorModeLevel();
                return;
            }
            if (currentIndex < items.length - 1) {
                currentIndex += 1;
                practiceFeedback.textContent = "New item ready. Take your time.";
                practiceFeedback.classList.remove("is-success", "is-warning");
                setMascotState("next", { loop: false, holdIdle: true, duration: 150, force: true });
                playCoachAnimation('next');
                render();
                return;
            }
            showCompletion();
            return;
        }

        if (isHuntMode) {
            if (!itemOutcomes[currentIndex] || huntAdvanceInProgress) return;
            huntAdvanceInProgress = true;
            nextBtn.disabled = true;
            huntWordArea?.classList.add("is-closing");
            window.setTimeout(() => {
                document.querySelector(`[data-hunt-dot="${currentIndex}"]`)?.classList.add("is-complete");
                if (currentIndex >= items.length - 1) {
                    huntAdvanceInProgress = false;
                    completeHuntModeLevel();
                    return;
                }
                currentIndex += 1;
                if (currentIndex === 3 && huntCheckpointToast) {
                    huntCheckpointToast.hidden = false;
                    window.setTimeout(() => { huntCheckpointToast.hidden = true; }, 2200);
                }
                practiceFeedback.textContent = "New word ready. Read or skip, then choose Next.";
                practiceFeedback.classList.remove("is-success", "is-warning");
                setMascotState("next", { loop: false, holdIdle: true, duration: 150, force: true });
                playCoachAnimation('next');
                huntWordArea?.classList.remove("is-closing");
                huntAdvanceInProgress = false;
                render();
            }, 220);
            return;
        }

        if (currentIndex < items.length - 1) {
            currentIndex += 1;
            practiceFeedback.textContent = "New item ready. Take your time.";
            practiceFeedback.classList.remove("is-success", "is-warning");
            setMascotState("next", { loop: false, holdIdle: true, duration: 150, force: true });
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
        if (handleColorModeKeyboard(event)) return;
        if (handleHuntModeKeyboard(event)) return;
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

    document.addEventListener("wheel", function (event) {
        if (!isColorMode && !isFreeMode && !isHuntMode) return;
        const activeElement = document.activeElement;
        if (isInteractiveElement(activeElement)) return;
        event.preventDefault();
    }, { passive: false });

    practiceAgainBtn?.addEventListener("click", restartPractice);
    practiceNextLevelBtn?.addEventListener("click", function (event) {
        if (practiceNextLevelBtn.getAttribute("aria-disabled") === "true") {
            event.preventDefault();
        }
    });

    if (viewMode === 'view') {
        if (skipBtn) skipBtn.classList.add("d-none");
        if (recordBtn) recordBtn.classList.add("d-none");
        if (starCount) starCount.classList.add("d-none");
        if (practiceFeedback) {
            practiceFeedback.textContent = "Reviewing completed content.";
            practiceFeedback.classList.remove("is-success", "is-warning");
        }
    }

    if (isFreeMode) {
        toggleFreeModeBodyLock(true);
        attachFreeModeInteractions();
    } else {
        toggleFreeModeBodyLock(false);
    }

    loadItems();
})();
