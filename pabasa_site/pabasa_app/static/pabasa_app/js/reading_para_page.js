(function () {
    const words = [
        "Maagang pumasok si Ana sa paaralan upang magbasa kasama ang kaniyang guro. Tahimik siyang umupo at dahan-dahang binigkas ang bawat salita. Dahil sa araw-araw na praktis, mas naging malinaw at mabilis ang kaniyang pagbasa.",
        "Tuwing umaga, naglalaan si Carlo ng sampung minuto para sa reading warm-up. Inuulit niya ang mahihirap na salita hanggang maging pamilyar ang tunog at baybay. Sa tulong nito, tumaas ang kaniyang kumpiyansa sa klase.",
        "Nagbigay ang guro ng maikling talata tungkol sa kalikasan. Binasa ito ng mga bata nang paisa-isa habang pinapansin ang tamang pagbigkas at paghinto. Naging mas maayos ang daloy ng kanilang pagbabasa.",
        "Sa reading center, pumili si Lito ng kuwentong may simpleng pangungusap. Tinukoy niya ang mga salitang hindi pa niya kabisado at isinulat sa notebook. Pagkatapos, nagpraktis siya kasama ang kaklase.",
        "Isinama ni Maya ang kaniyang magulang sa gabi-gabing reading routine. Nagbabasa sila ng isang talata at pinag-uusapan ang kahulugan ng bagong salita. Dahil dito, mas nauunawaan niya ang binabasa.",
        "Sa oras ng pagsusulit, hinikayat ng guro ang mga bata na huminga nang malalim bago magsimula. Dahan-dahan nilang binasa ang bawat pangungusap para maiwasan ang pagkalito. Nakatulong ito upang tumaas ang kanilang accuracy.",
        "Matapos ang reading session, nagbigay ng feedback ang guro tungkol sa wastong diin at intonasyon. Ang mga bata ay nag-notes sa mga salitang kailangang balikan. Sa susunod na linggo, kapansin-pansin ang kanilang pag-unlad.",
        "May simpleng activity kung saan itinutugma ng mga bata ang salita sa larawan. Pagkatapos ng gawain, binasa nila ang maikling talata gamit ang tamang bilis. Naging mas masaya at interaktibo ang aralin.",
        "Bawat Biyernes, may group reading ang klase upang mapalakas ang teamwork. Pinapakinggan nila ang isa't isa at nagbibigay ng magalang na pagwawasto kapag may maling bigkas. Nakabubuo ito ng mas positibong learning environment.",
        "Sa pagtatapos ng buwan, sinuri ng guro ang progreso ng bawat mag-aaral. Ipinakita sa kanila ang pagtaas ng kanilang WPM at comprehension score. Dahil dito, mas motivated silang ipagpatuloy ang regular na pagbabasa."
    ];
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

    const params = new URLSearchParams(window.location.search);
    const testTitle = params.get("test") || "Assessment";
    const testCode = params.get("code") || "TST-000";
    testMeta.textContent = testTitle + " - " + testCode;

    function renderWord() {
        readingWord.textContent = words[currentIndex];
        counter.textContent = "Paragraph " + (currentIndex + 1) + "/" + words.length;
        progressFill.style.width = ((currentIndex + 1) / words.length) * 100 + "%";
        prevBtn.disabled = currentIndex === 0;
        nextBtn.disabled = currentIndex === words.length - 1;
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
        }
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
        currentIndex = 0;
        renderWord();
        closePauseMenu();
    });

    quitBtn.addEventListener("click", function () {
        window.location.href = "/dashboard/assessment/";
    });

    document.addEventListener("click", function (event) {
        if (!pauseMenu.contains(event.target) && !pauseBtn.contains(event.target)) {
            closePauseMenu();
        }
    });

    renderWord();
})();
