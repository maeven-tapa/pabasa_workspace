(() => {
    const data = JSON.parse(document.getElementById("material").textContent || "{}");
    const completion = JSON.parse(document.getElementById("completion").textContent || "{}");
    const stage = document.getElementById("stage");
    const progress = document.getElementById("progress");
    const fill = document.getElementById("progressFill");
    const hudCount = document.getElementById("hudClapCount");
    const items = [...(data.items || [])];
    let index = 0;
    let phase = "my-turn";
    let revealed = 0;
    let clapCount = 0;
    let answers = [];
    let utterance = null;
    let recorder = null;
    let stream = null;
    let chunks = [];
    let uploadChain = Promise.resolve();
    let syllableContext = "";
    let finishingReading = false;
    let readingComplete = false;
    let attemptDisplay = "";
    let attemptStatus = "";
    let lastTranscript = "";
    let wrongFeedbackActive = false;
    let lottieAnimation = null;
    const clapSound = new Audio("/static/pabasa_app/audio/clap/clap-sound-effect.mp3");
    const started = Date.now();

    const escapeHtml = value => String(value ?? "").replace(/[&<>\"]/g, character => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;",
    }[character]));
    const csrfToken = () => document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || "";
    const item = () => items[index];
    const word = () => String(item()?.word || "").toUpperCase();
    const syllables = () => Array.isArray(item()?.syllables) ? item().syllables : [word()];
    const spokenGrouping = transcript => String(transcript || "").trim().replace(/[\u2010-\u2015-]/g, " ").split(/\s+/).filter(Boolean).join(" | ").toUpperCase();

    function updateHud() {
        hudCount.textContent = clapCount;
        progress.textContent = `${Math.min(index + 1, items.length)} / ${items.length}`;
        fill.style.width = `${items.length ? ((index + 1) / items.length) * 100 : 100}%`;
    }

    function displayedWord() {
        if (phase === "my-turn" || phase === "tts") return word();
        if (attemptDisplay) return attemptDisplay;
        const parts = syllables();
        const count = phase === "count" || phase === "ready-to-count" ? parts.length : Math.max(0, Math.min(revealed, parts.length));
        if (!count) return word();
        return `${parts.slice(0, count).join(" | ")}${count < parts.length ? ` | ${parts.slice(count).join("")}` : ""}`.toUpperCase();
    }

    function render(feedback = "") {
        if (!item()) return finish();
        updateHud();
        const buttonLabel = phase === "my-turn" ? "MY TURN!" : phase === "tts" ? "MY TURN!" : phase === "your-turn" ? "YOUR TURN!" : phase === "recording" ? "FINISH READING" : "LET'S COUNT!";
        const instruction = phase === "my-turn" || phase === "tts" ? "Watch me!" : phase === "your-turn" || phase === "recording" ? "Now you say it!" : "LET'S COUNT!";
        const countControls = phase === "count" ? `<div class="clap-area"><button class="clap-pad" id="clapPad" type="button" aria-label="Clap once"><span id="clapAnimation" class="clap-animation"></span><span class="clap-number" id="clapNumber">${clapCount}</span></button><p class="clap-hint">One clap for each syllable</p></div><div class="actions"><button class="minor" id="clear" type="button">Clear</button><button class="primary" id="check" type="button" ${clapCount < 1 ? "disabled" : ""}>Check ✓</button></div>` : `<div class="actions"><button class="primary" id="primary" type="button" ${phase === "tts" ? "disabled" : ""}>${buttonLabel}</button></div>`;
        stage.innerHTML = `<article class="forest-card"><div class="activity-content phase-${phase}"><div class="word-safe-area" id="wordSafeArea"><div class="word phase2-word ${attemptStatus ? `phase2-${attemptStatus}` : ""}" id="heroWord">${escapeHtml(displayedWord())}</div></div><p class="instruction">${instruction}</p>${countControls}<p class="feedback">${escapeHtml(feedback)}</p></div><img class="mascot" src="${window.CLAP_MASCOT_URL}" alt="PABASA mascot"></article>`;
        requestAnimationFrame(fitWord);
        if (attemptStatus === "wrong") document.getElementById("heroWord")?.addEventListener("animationend", resetWrongAttempt, { once: true });
        if (phase === "count") setupLottie();
        document.getElementById("primary")?.addEventListener("click", primaryAction);
        document.getElementById("clapPad")?.addEventListener("click", clap);
        document.getElementById("clear")?.addEventListener("click", () => { clapCount = 0; render(); });
        document.getElementById("check")?.addEventListener("click", check);
    }

    function fitWord() {
        const safe = document.getElementById("wordSafeArea");
        const hero = document.getElementById("heroWord");
        if (!safe || !hero) return;
        const available = Math.max(1, safe.clientWidth - 16);
        const preferred = displayedWord().length <= 8 ? 104 : displayedWord().length <= 15 ? 78 : 58;
        hero.style.fontSize = `${Math.max(24, Math.min(preferred, preferred * available / Math.max(hero.scrollWidth, 1)))}px`;
        hero.classList.add("is-fitted");
    }

    function speak() {
        if (!("speechSynthesis" in window)) {
            beginYourTurn();
            return;
        }
        phase = "tts";
        render();
        speechSynthesis.cancel();
        utterance = new SpeechSynthesisUtterance(item().word);
        utterance.lang = data.language === "Filipino" ? "fil-PH" : "en-US";
        utterance.onend = beginYourTurn;
        utterance.onerror = beginYourTurn;
        speechSynthesis.speak(utterance);
    }

    function primaryAction() {
        if (phase === "my-turn") return speak();
        if (phase === "your-turn") return startRecording();
        if (phase === "recording") return stopRecording();
        if (phase === "ready-to-count") { phase = "count"; render(); }
    }

    function beginYourTurn() {
        if (phase !== "tts") return;
        phase = "your-turn";
        render();
    }

    function resetWrongAttempt() {
        if (phase !== "your-turn" || attemptStatus !== "wrong") return;
        attemptDisplay = "";
        attemptStatus = "";
        wrongFeedbackActive = false;
        render();
    }

    function showWrongAttempt() {
        if (wrongFeedbackActive || readingComplete) return;
        wrongFeedbackActive = true;
        finishingReading = false;
        stopRecording();
        phase = "your-turn";
        attemptStatus = "wrong";
        render();
    }

    async function uploadChunk(blob) {
        if (readingComplete || wrongFeedbackActive || !blob?.size || (phase !== "recording" && !finishingReading)) return;
        const form = new FormData();
        form.append("audio", blob, `clap-reading-${Date.now()}.webm`);
        form.append("target_text", item().word);
        form.append("current_syllable_index", String(revealed));
        form.append("syllable_context", syllableContext);
        form.append("syllables", JSON.stringify(syllables()));
        form.append("mode", "word");
        form.append("language", data.language || "");
        const response = await fetch("/api/reading/transcribe/", { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": csrfToken() }, body: form });
        const result = await response.json();
        if (!response.ok || !result.success) throw new Error(result.error || "Speech recognition failed.");
        lastTranscript = String(result.raw_transcript || result.transcript || "").trim();
        if (lastTranscript) attemptDisplay = spokenGrouping(lastTranscript);
        revealed = Math.max(revealed, Number(result.current_syllable_index || 0), Number(result.syllable_context_count || 0));
        syllableContext = String(result.syllable_context || "");
        if (result.phase2_correct === true && result.complete === true && Number(result.progress || 0) >= 100) {
            readingComplete = true;
            finishingReading = false;
            stopRecording();
            phase = "ready-to-count";
            revealed = syllables().length;
            attemptStatus = "correct";
            render("You read it! Tap LET'S COUNT when you're ready.");
        } else if (result.complete === true) {
            showWrongAttempt();
        } else if (!finishingReading) {
            render();
        }
    }

    async function startRecording() {
        if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
            render("Microphone access is needed. Please try again.");
            return;
        }
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
            chunks = [];
            finishingReading = false;
            recorder = new MediaRecorder(stream);
            phase = "recording";
            readingComplete = false;
            render("Listening… say the word!");
            recorder.ondataavailable = event => { if (event.data?.size) uploadChain = uploadChain.then(() => uploadChunk(event.data)).catch(error => render(error.message)); };
            recorder.onstop = async () => {
                await uploadChain;
                if (!readingComplete && phase === "recording") showWrongAttempt();
            };
            recorder.start(900);
        } catch (error) {
            render("Please allow microphone access, then try again.");
        }
    }

    function stopRecording() {
        if (recorder && recorder.state !== "inactive") {
            finishingReading = true;
            recorder.stop();
        }
        stream?.getTracks().forEach(track => track.stop());
        stream = null;
        recorder = null;
    }

    function setupLottie() {
        const container = document.getElementById("clapAnimation");
        if (!container || !window.lottie) return;
        lottieAnimation?.destroy();
        lottieAnimation = window.lottie.loadAnimation({ container, renderer: "svg", loop: false, autoplay: false, path: window.CLAP_ANIMATION_URL });
    }

    function clap() {
        if (clapCount >= 10) return;
        clapCount += 1;
        document.getElementById("clapNumber").textContent = clapCount;
        lottieAnimation?.stop();
        clapSound.currentTime = 0;
        clapSound.play().catch(() => {});
        lottieAnimation?.goToAndPlay(0, true);
        hudCount.textContent = clapCount;
        document.getElementById("check").disabled = false;
    }

    function check() {
        const current = item();
        const correct = clapCount === Number(current.syllable_count);
        const feedback = stage.querySelector(".feedback");
        if (!correct) {
            feedback.textContent = "Almost! Count the word parts again.";
            stage.querySelector(".activity-content").classList.add("is-wrong");
            return;
        }
        answers.push({ word_id: current.id, answer: clapCount, claps: clapCount });
        feedback.textContent = "Great counting!";
        feedback.classList.add("is-correct");
        stage.querySelector(".activity-content").classList.add("is-correct");
        setTimeout(() => { index += 1; phase = "my-turn"; revealed = 0; clapCount = 0; syllableContext = ""; render(); }, 420);
    }

    async function finish() {
        updateHud();
        progress.textContent = "Complete ✓";
        fill.style.width = "100%";
        stage.innerHTML = `<article class="forest-card"><div class="complete"><div class="complete-label">Saving result…</div><h2>Great job! 🎉</h2></div></article>`;
        try {
            const response = await fetch("/record-assessment-completion/", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() }, body: JSON.stringify({ material_id: data.id, activity_type: "assessment", assessment_type: "word", items_completed: items.length, scores: { answers, duration_seconds: Math.round((Date.now() - started) / 1000) } }) });
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error(result.error || "Unable to save result.");
            stage.innerHTML = `<article class="forest-card"><div class="complete"><div class="complete-label">Activity complete</div><h2>Great job! 🎉</h2><p>${Number(result.correct_items || 0)} of ${Number(result.items_completed || 0)} correct · ${Number(result.accuracy || 0)}%</p><a class="primary" href="/dashboard/assessment/">Back to Assessments →</a></div></article>`;
        } catch (error) {
            stage.innerHTML = `<article class="forest-card"><div class="complete"><div class="complete-label">Result not saved</div><h2>Please try again</h2><p>${escapeHtml(error.message)}</p><button class="primary" id="retrySave" type="button">Save again</button></div></article>`;
            document.getElementById("retrySave").onclick = finish;
        }
    }

    if (completion.completed) {
        progress.textContent = "Completed ✓";
        fill.style.width = "100%";
        stage.innerHTML = `<article class="forest-card"><div class="complete"><div class="complete-label">Completed ✓</div><h2>Activity finished!</h2><p>${Number(completion.correct_items || 0)} of ${Number(completion.total_items || 0)} correct · ${Number(completion.accuracy || 0)}%</p></div></article>`;
    } else if (items.length) {
        render();
    }
    window.addEventListener("resize", () => requestAnimationFrame(fitWord));
})();
