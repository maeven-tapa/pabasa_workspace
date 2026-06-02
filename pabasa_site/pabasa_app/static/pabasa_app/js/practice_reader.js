(function () {
    const sets = {
        word: {
            label: "Word",
            items: ["bahay", "araw", "aklat", "guro", "paaralan"]
        },
        sentence: {
            label: "Sentence",
            items: [
                "Si Ana ay nagbabasa.",
                "Ang bata ay may aklat.",
                "Masaya kami sa klase.",
                "Si Lito ay sumulat.",
                "Tahimik ang silid."
            ]
        },
        paragraph: {
            label: "Story",
            items: [
                "Si Maya ay may bagong aklat. Binasa niya ito nang dahan-dahan. Masaya siyang natuto ng bagong salita.",
                "Maagang pumasok si Carlo. Umupo siya malapit sa guro. Nagbasa siya ng maikling kuwento.",
                "May maliit na halaman sa bintana. Diniligan ito ni Ana. Araw-araw niya itong tinitingnan.",
                "Nagpraktis ang klase ng pagbasa. Nakinig muna sila sa guro. Pagkatapos, sabay-sabay silang bumasa.",
                "Pumili si Lito ng paboritong pahina. Binasa niya ito nang malinaw. Ngumiti siya matapos ang gawain."
            ]
        }
    };

    const shell = document.querySelector("[data-practice-mode]");
    const mode = shell ? shell.getAttribute("data-practice-mode") : "word";
    const activeSet = sets[mode] || sets.word;
    let currentIndex = 0;
    let stars = 0;

    const practiceText = document.getElementById("practiceText");
    const practiceCounter = document.getElementById("practiceCounter");
    const practiceProgress = document.getElementById("practiceProgress");
    const practiceFeedback = document.getElementById("practiceFeedback");
    const starCount = document.getElementById("starCount");
    const listenBtn = document.getElementById("listenBtn");
    const recordBtn = document.getElementById("recordBtn");
    const nextBtn = document.getElementById("practiceNextBtn");
    const completeStars = document.getElementById("completeStars");
    const completeItems = document.getElementById("completeItems");
    const practiceAgainBtn = document.getElementById("practiceAgainBtn");

    function render() {
        practiceText.textContent = activeSet.items[currentIndex];
        practiceCounter.textContent = activeSet.label + " " + (currentIndex + 1) + "/" + activeSet.items.length;
        practiceProgress.style.width = ((currentIndex + 1) / activeSet.items.length) * 100 + "%";
        starCount.textContent = stars + (stars === 1 ? " star" : " stars");
        nextBtn.textContent = currentIndex === activeSet.items.length - 1 ? "Finish" : "Next";
        nextBtn.disabled = false;
        if (completeStars) {
            completeStars.textContent = stars;
        }
        if (completeItems) {
            completeItems.textContent = activeSet.items.length;
        }
    }

    function showCompletion() {
        shell.classList.add("is-complete");
        if (completeStars) {
            completeStars.textContent = stars;
        }
        if (completeItems) {
            completeItems.textContent = activeSet.items.length;
        }
    }

    function restartPractice() {
        shell.classList.remove("is-complete");
        currentIndex = 0;
        stars = 0;
        practiceFeedback.textContent = "Ready when you are.";
        render();
    }

    listenBtn.addEventListener("click", function () {
        practiceFeedback.textContent = "Listen in your mind, then read it with a steady voice.";
    });

    recordBtn.addEventListener("click", function () {
        stars += 1;
        practiceFeedback.textContent = "Nice reading. You earned a practice star.";
        render();
    });

    nextBtn.addEventListener("click", function () {
        if (currentIndex < activeSet.items.length - 1) {
            currentIndex += 1;
            practiceFeedback.textContent = "New item ready. Take your time.";
            render();
            return;
        }

        showCompletion();
    });

    if (practiceAgainBtn) {
        practiceAgainBtn.addEventListener("click", restartPractice);
    }

    render();
})();
