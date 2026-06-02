(function () {
    const words = ["bahay", "aklat", "guro", "paaralan", "araw", "ulap", "talata", "pangarap", "pagbasa", "salita"];
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
    const reviewBtn = document.getElementById("reviewBtn");
    const finishBtn = document.getElementById("finishBtn");

    const params = new URLSearchParams(window.location.search);
    const testTitle = params.get("test") || "Assessment";
    const testCode = params.get("code") || "TST-000";
    testMeta.textContent = testTitle + " - " + testCode;

    function renderWord() {
        readingWord.textContent = words[currentIndex];
        counter.textContent = "Word " + (currentIndex + 1) + "/" + words.length;
        progressFill.style.width = ((currentIndex + 1) / words.length) * 100 + "%";
        prevBtn.disabled = currentIndex === 0;
        nextBtn.disabled = false;
        nextBtn.textContent = currentIndex === words.length - 1 ? "Finish" : "Next";
        if (completionCount) {
            completionCount.textContent = words.length;
        }
    }

    function showCompletion() {
        shell.classList.add("is-complete");
        closePauseMenu();
    }

    function restartAssessment() {
        shell.classList.remove("is-complete");
        currentIndex = 0;
        renderWord();
    }

    prevBtn.addEventListener("click", function () {
        if (currentIndex > 0) {
            currentIndex -= 1;
            renderWord();
        }
    });

    nextBtn.addEventListener("click", function () {
        if (currentIndex < words.length - 1) {
            currentIndex += 1;
            renderWord();
            return;
        }

        showCompletion();
    });

    function closePauseMenu() {
        pauseMenu.classList.add("d-none");
        pauseOverlay.classList.add("d-none");
        pauseBtn.setAttribute("aria-expanded", "false");
    }

    pauseBtn.addEventListener("click", function () {
        const isHidden = pauseMenu.classList.contains("d-none");
        pauseMenu.classList.toggle("d-none", !isHidden);
        pauseOverlay.classList.toggle("d-none", !isHidden);
        pauseBtn.setAttribute("aria-expanded", isHidden ? "true" : "false");
    });

    pauseOverlay.addEventListener("click", closePauseMenu);

    resumeBtn.addEventListener("click", function () {
        closePauseMenu();
    });

    retryBtn.addEventListener("click", function () {
        shell.classList.remove("is-complete");
        currentIndex = 0;
        renderWord();
        closePauseMenu();
    });

    quitBtn.addEventListener("click", function () {
        window.location.href = "/dashboard/assessment/";
    });

    if (reviewBtn) {
        reviewBtn.addEventListener("click", restartAssessment);
    }

    if (finishBtn) {
        finishBtn.addEventListener("click", function () {
            window.location.href = "/dashboard/assessment/";
        });
    }

    document.addEventListener("click", function (event) {
        if (!pauseMenu.contains(event.target) && !pauseBtn.contains(event.target)) {
            closePauseMenu();
        }
    });

    renderWord();
})();
