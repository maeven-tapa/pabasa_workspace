(() => {
    "use strict";
    const root = document.querySelector(".sentence-bot-root");
    if (!root) return;
    const assetRoot = window.__PABASA_SENTENCE_BOT_ASSET_ROOT__ || "/static/pabasa_app/images/sentence_bot/";
    const material = window.__PABASA_CUSTOM_MATERIAL__ || {};
    const persistedCompletion = window.__PABASA_SENTENCE_BOT_COMPLETION__ || {};
    const completionUrl = window.__PABASA_SENTENCE_BOT_COMPLETE_URL__ || "/api/sentence-bot/complete/";
    const backUrl = window.__PABASA_SENTENCE_BOT_BACK_URL__ || "/dashboard/assessment/";
    const language = /filipino|tagalog|fil\b/i.test(String(material.language || material.content_json?.language || "")) ? "FILIPINO" : "ENGLISH";
    const sourceItems = Array.isArray(material.items) ? material.items : [];
    const totalFromData = sourceItems.length || String(material.content || "").split(/\r?\n/).filter(line => line.trim()).length || 1;
    const state = { index: 0, total: totalFromData, learned: 0, mode: "idle", successTimer: null };
    if (!persistedCompletion.completed) {
        const originalFetch = window.fetch.bind(window);
        let retryRequiresFreshSentence = false;
        window.fetch = async (input, init = {}) => {
            const requestUrl = typeof input === "string" ? input : String(input?.url || "");
            if (requestUrl.endsWith("/api/reading/transcribe/")) {
                const requestBody = init.body;
                if (retryRequiresFreshSentence && requestBody instanceof FormData) {
                    requestBody.set("current_syllable_index", "0");
                    requestBody.delete("syllable_context");
                }
                const response = await originalFetch(input, init);
                let sentenceBotResponse = response;
                try {
                    const result = await response.clone().json();
                    const recognizedAttempt = Boolean(
                        String(result.transcript || "").trim()
                        || Number(result.matched || 0) > 0
                        || (Array.isArray(result.word_results) && result.word_results.length)
                    );
                    const hasMiscue = Array.isArray(result.word_results)
                        && result.word_results.some(item => String(item?.result || "").toLowerCase() === "miscue");
                    if (result.complete && hasMiscue) {
                        retryRequiresFreshSentence = true;
                        result.complete = false;
                        result.matched = 0;
                        result.correct_word_count = 0;
                        result.current_word_index = 0;
                        result.current_syllable_index = 0;
                        sentenceBotResponse = new Response(JSON.stringify(result), {
                            status: response.status,
                            statusText: response.statusText,
                            headers: response.headers,
                        });
                    } else if (result.complete) {
                        retryRequiresFreshSentence = false;
                    } else if (recognizedAttempt && (hasMiscue || Number(result.matched || 0) === 0)) {
                        retryRequiresFreshSentence = true;
                    }
                } catch (error) {
                    // The shared reader owns response/error presentation.
                }
                return sentenceBotResponse;
            }
            if (!requestUrl.endsWith("/record-assessment-completion/")) return originalFetch(input, init);
            let payload = {};
            try { payload = JSON.parse(init.body || "{}"); } catch (error) { payload = {}; }
            payload.material_id = material.id || payload.material_id;
            payload.activity_type = "sentence_bot";
            payload.items_completed = state.total;
            payload.correct_items = state.total;
            payload.scores = { ...(payload.scores || {}), correct_sentences: state.total, total_sentences: state.total };
            return originalFetch(completionUrl, { ...init, body: JSON.stringify(payload) });
        };
    }
    const stage = root.querySelector(".reader-stage");
    const card = root.querySelector(".reader-card");
    const wordStage = root.querySelector(".word-stage");
    const footer = root.querySelector(".reader-footer");
    const startButton = document.getElementById("btnStartReading");
    const stopButton = document.getElementById("btnStopReading");
    const doneButton = document.getElementById("reviewBtn");
    const backButton = document.getElementById("finishBtn");
    const lab = document.createElement("section");
    lab.className = "sentence-bot-lab";
    lab.innerHTML = `
        <div class="sentence-bot-circuit" aria-hidden="true"></div>
        <img class="sentence-bot-particles" src="${assetRoot}particle1.png" alt="">
        <header class="sentence-bot-header">
            <div><p class="sentence-bot-kicker">PABASA LANGUAGE LAB</p><h1>SENTENCE BOT</h1></div>
            <div class="sentence-bot-training-meta"><span class="sentence-bot-language">${language}</span><strong id="sentenceBotTraining">TRAINING 01 / ${pad(state.total)}</strong></div>
        </header>
        <div class="sentence-bot-workspace">
            <aside class="sentence-bot-character-panel">
                <div class="sentence-bot-system-status"><span class="sentence-bot-status-light" aria-hidden="true"></span><b>PIPPO SYSTEM</b><em id="sentenceBotStatus">READY</em></div>
                <div class="sentence-bot-orbit" aria-hidden="true"><i></i><i></i><i></i></div>
                <div class="sentence-bot-core-ring" aria-hidden="true"><span></span></div>
                <img id="sentenceBotRobot" class="sentence-bot-robot" src="${assetRoot}robot_idle.png" alt="Friendly Sentence Bot is ready">
                <div class="sentence-bot-message" id="sentenceBotMessage" role="status" aria-live="polite"><span class="sentence-bot-message-dot" aria-hidden="true"></span><span>READY TO LEARN</span></div>
            </aside>
            <div class="sentence-bot-lesson-panel">
                <div class="sentence-bot-prompt-label"><span></span> KNOWLEDGE INPUT <span></span></div>
                <div class="sentence-bot-sentence-slot"></div>
                <p class="sentence-bot-voice-guide" id="sentenceBotVoiceGuide"><i class="bi bi-volume-up" aria-hidden="true"></i><span>Read the sentence aloud</span></p>
                <div class="sentence-bot-action-slot"></div>
                <div class="sentence-bot-result-feedback" id="sentenceBotResultFeedback" aria-live="polite"><span aria-hidden="true"></span><b>SENTENCE READY</b></div>
            </div>
            <aside class="sentence-bot-memory" aria-label="Robot memory progress">
                <div class="sentence-bot-memory-title"><span>ROBOT MEMORY</span><strong id="sentenceBotLearned">0 / ${state.total} LEARNED</strong></div>
                <div class="sentence-bot-chip-bank" id="sentenceBotChipBank"></div>
            </aside>
        </div>`;
    stage?.insertBefore(lab, card);
    lab.querySelector(".sentence-bot-sentence-slot")?.appendChild(wordStage);
    lab.querySelector(".sentence-bot-action-slot")?.appendChild(footer);
    if (card) card.hidden = true;
    const robot = document.getElementById("sentenceBotRobot");
    const message = document.getElementById("sentenceBotMessage");
    const systemStatus = document.getElementById("sentenceBotStatus");
    const voiceGuide = document.getElementById("sentenceBotVoiceGuide");
    const resultFeedback = document.getElementById("sentenceBotResultFeedback");
    const training = document.getElementById("sentenceBotTraining");
    const learned = document.getElementById("sentenceBotLearned");
    const chipBank = document.getElementById("sentenceBotChipBank");
    function pad(value) { return String(Math.max(0, Number(value) || 0)).padStart(2, "0"); }
    function renderChips() {
        if (!chipBank) return;
        chipBank.style.setProperty("--chip-count", state.total);
        chipBank.dataset.chipCount = String(state.total);
        chipBank.replaceChildren(...Array.from({ length: state.total }, (_, index) => {
            const item = document.createElement("span");
            item.className = `sentence-bot-memory-chip${index < state.learned ? " is-learned" : ""}${index === state.index && state.learned < state.total ? " is-current" : ""}${index === state.learned - 1 && state.mode === "success" ? " is-activating" : ""}`;
            const image = document.createElement("img");
            image.src = `${assetRoot}chip${index + 1}.png`;
            image.alt = "";
            const chipCopy = document.createElement("span");
            chipCopy.className = "sentence-bot-chip-copy";
            chipCopy.innerHTML = `<b>CHIP ${pad(index + 1)}</b><small>${index < state.learned ? "LEARNED ✓" : index === state.index ? "READY" : "EMPTY"}</small>`;
            item.append(image, chipCopy); return item;
        }));
        if (learned) learned.textContent = `${state.learned} / ${state.total} LEARNED`;
        if (training) training.textContent = `TRAINING ${pad(Math.min(state.index + 1, state.total))} / ${pad(state.total)}`;
    }
    function setMode(mode, copy) {
        state.mode = mode; root.dataset.botState = mode;
        const robotMode = mode === "processing" ? "listening" : mode;
        if (robot) { robot.src = `${assetRoot}robot_${robotMode}.png`; robot.alt = `Friendly Sentence Bot is ${mode === "idle" ? "ready" : mode}`; }
        if (message) message.innerHTML = `<span class="sentence-bot-message-dot" aria-hidden="true"></span><span>${copy}</span>`;
        if (systemStatus) systemStatus.textContent = mode === "listening" ? "LISTENING" : mode === "processing" ? "CHECKING" : mode === "success" ? "LEARNED" : mode === "retry" ? "TRY AGAIN" : "READY";
        if (voiceGuide) voiceGuide.querySelector("span").textContent = mode === "retry" ? "Read the same sentence again" : mode === "processing" ? "Pippo is checking your reading" : mode === "listening" ? "Speak clearly — Pippo is listening" : mode === "success" ? "Great reading!" : "Read the sentence aloud";
        if (resultFeedback) resultFeedback.querySelector("b").textContent = mode === "retry" ? "SAME SENTENCE · TRY AGAIN" : mode === "processing" ? "CHECKING YOUR READING" : mode === "listening" ? "VOICE SIGNAL ACTIVE" : mode === "success" ? "SENTENCE LEARNED ✓" : "SENTENCE READY";
        if (startButton) startButton.innerHTML = mode === "listening" ? '<i class="bi bi-soundwave"></i> PIPPO IS LISTENING' : mode === "processing" ? '<i class="bi bi-cpu"></i> CHECKING...' : '<i class="bi bi-mic-fill"></i> TEACH PIPPO';
    }
    function settleToIdle() { if (!root.classList.contains("is-complete")) setMode("idle", "READY TO LEARN"); }
    startButton?.setAttribute("aria-label", "Read aloud to teach the robot");
    stopButton?.addEventListener("click", settleToIdle);
    doneButton?.addEventListener("click", event => {
        event.preventDefault();
        event.stopImmediatePropagation();
        backButton?.click();
    }, true);
    if (persistedCompletion.completed) {
        backButton?.addEventListener("click", event => {
            event.preventDefault();
            event.stopImmediatePropagation();
            window.location.assign(backUrl);
        }, true);
    }
    const counter = document.getElementById("counter");
    const speechStatus = document.getElementById("speechStatus");
    let completionRendered = false;

    function syncItemFromEngine() {
        const match = String(counter?.textContent || "").match(/(\d+)\s*\/\s*(\d+)/);
        if (!match) return;
        const nextIndex = Math.max(0, Number(match[1]) - 1);
        const nextTotal = Math.max(1, Number(match[2]));
        const itemChanged = nextIndex !== state.index || nextTotal !== state.total;
        state.index = nextIndex;
        state.total = nextTotal;
        renderChips();
        if (itemChanged && !root.classList.contains("is-complete")) {
            setMode(root.classList.contains("is-recording") ? "listening" : "idle",
                root.classList.contains("is-recording") ? "I'M LISTENING..." : "I'M READY TO LEARN!");
        }
    }

    function syncStatusFromEngine() {
        if (root.classList.contains("is-complete")) return;
        const statusText = String(speechStatus?.textContent || "");
        if (/great job.*finished this item/i.test(statusText)) {
            state.learned = Math.max(state.learned, Math.min(state.total, state.index + 1));
            setMode("success", "I LEARNED IT! ✨");
            renderChips();
        } else if (/not quite|try again/i.test(statusText)) {
            setMode("retry", "I DIDN'T CATCH THAT — LET'S TRY AGAIN!");
        } else if (/microphone access|unavailable|error|trouble/i.test(statusText)) {
            setMode("retry", "LET'S CHECK THE MICROPHONE.");
        } else if (startButton?.dataset.speechProcessingState) {
            setMode("processing", "CHECKING YOUR READING...");
        } else if (root.classList.contains("is-recording")) {
            setMode("listening", "I'M LISTENING...");
        }
    }

    function renderCompletionFromEngine() {
        if (completionRendered || !root.classList.contains("is-complete")) return;
        completionRendered = true;
        state.learned = persistedCompletion.completed
            ? Math.min(state.total, Math.max(0, Number(persistedCompletion.correct_sentences) || 0))
            : state.total;
        state.index = state.total - 1;
        renderChips();
        setMode("success", "ROBOT TRAINING COMPLETE!");
        const kicker = document.querySelector(".completion-kicker");
        const title = document.getElementById("completionTitle");
        const completionMessage = document.getElementById("completionMessage");
        const completionActions = root.querySelector(".completion-actions");
        let sentenceResult = document.getElementById("sentenceBotCompletionResult");
        if (!sentenceResult && completionActions) {
            sentenceResult = document.createElement("div");
            sentenceResult.id = "sentenceBotCompletionResult";
            sentenceResult.className = "sentence-bot-completion-result";
            sentenceResult.innerHTML = '<span>CORRECT SENTENCES READ</span><strong></strong>';
            completionActions.before(sentenceResult);
        }
        if (kicker) kicker.textContent = "ROBOT TRAINING";
        if (title) title.textContent = "COMPLETE! 🤖";
        if (completionMessage) completionMessage.textContent = "Woohoo! 🚀 Pippo knows all the sentences now! 🤖🎉";
        const sentenceResultValue = sentenceResult?.querySelector("strong");
        if (sentenceResultValue) sentenceResultValue.textContent = `${state.learned} / ${state.total}`;
        if (doneButton) doneButton.textContent = "Done";
        if (backButton) backButton.textContent = "Back to Materials";
    }

    new MutationObserver(() => {
        syncStatusFromEngine();
        renderCompletionFromEngine();
    }).observe(root, { attributes: true, attributeFilter: ["class"] });
    if (speechStatus) new MutationObserver(syncStatusFromEngine).observe(speechStatus, { childList: true, characterData: true, subtree: true });
    if (startButton) new MutationObserver(syncStatusFromEngine).observe(startButton, { attributes: true, attributeFilter: ["data-speech-processing-state", "disabled"] });
    if (counter) new MutationObserver(syncItemFromEngine).observe(counter, { childList: true, characterData: true, subtree: true });

    if (persistedCompletion.completed) {
        state.total = Math.max(1, Number(persistedCompletion.total_sentences) || state.total);
        state.learned = Math.min(state.total, Math.max(0, Number(persistedCompletion.correct_sentences) || 0));
        state.index = Math.max(0, state.total - 1);
        renderChips();
        root.classList.add("is-complete");
        renderCompletionFromEngine();
    } else {
        renderChips();
        syncItemFromEngine();
        settleToIdle();
    }
})();
