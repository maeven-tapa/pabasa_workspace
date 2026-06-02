(function () {
function initStudentsPage() {
    const studentSearchInput = document.getElementById("studentSearchInput");
    const readingLevelFilter = document.getElementById("readingLevelFilter");
    const studentRows = Array.from(document.querySelectorAll(".student-card-row"));
    const studentEmptyState = document.getElementById("studentEmptyState");
    const studentResultCount = document.getElementById("studentResultCount");
    const assignSectionModal = document.getElementById("assignSectionModal");
    const studentNameInput = document.getElementById("assignSectionStudentName");
    const currentSectionInput = document.getElementById("assignSectionCurrentSection");
    const changeStatusModal = document.getElementById("changeStatusModal");
    const changeStatusStudentName = document.getElementById("changeStatusStudentName");
    const changeStatusCurrent = document.getElementById("changeStatusCurrent");

    function normalize(value) {
        return (value || "").toLowerCase().trim();
    }

    function filterStudents() {
        const query = normalize(studentSearchInput ? studentSearchInput.value : "");
        const selectedLevel = readingLevelFilter ? readingLevelFilter.value : "All levels";
        let visibleCount = 0;

        studentRows.forEach(function (row) {
            const searchableText = normalize(
                [
                    row.getAttribute("data-student-name"),
                    row.getAttribute("data-reading-level"),
                    row.getAttribute("data-class-name"),
                    row.textContent
                ].join(" ")
            );
            const rowLevel = row.getAttribute("data-reading-level") || "";
            const matchesSearch = !query || searchableText.includes(query);
            const matchesLevel = selectedLevel === "All levels" || rowLevel === selectedLevel;
            const shouldShow = matchesSearch && matchesLevel;

            row.classList.toggle("d-none", !shouldShow);
            if (shouldShow) {
                visibleCount += 1;
            }
        });

        if (studentEmptyState) {
            studentEmptyState.classList.toggle("is-visible", visibleCount === 0);
        }

        if (studentResultCount) {
            studentResultCount.textContent = visibleCount;
        }
    }

    if (studentSearchInput) {
        studentSearchInput.addEventListener("input", filterStudents);
    }

    if (readingLevelFilter) {
        readingLevelFilter.addEventListener("change", filterStudents);
    }

    filterStudents();

    if (!assignSectionModal || !studentNameInput || !currentSectionInput) {
        return;
    }

    assignSectionModal.addEventListener("show.bs.modal", function (event) {
        const trigger = event.relatedTarget;
        if (!trigger) {
            return;
        }

        const studentName = trigger.getAttribute("data-student-name") || "";
        const currentSection = trigger.getAttribute("data-current-section") || "";

        studentNameInput.value = studentName;
        currentSectionInput.value = currentSection;
    });

    if (!changeStatusModal || !changeStatusStudentName || !changeStatusCurrent) {
        return;
    }

    changeStatusModal.addEventListener("show.bs.modal", function (event) {
        const trigger = event.relatedTarget;
        if (!trigger) {
            return;
        }

        const studentName = trigger.getAttribute("data-student-name") || "";
        const currentStatus = trigger.getAttribute("data-current-status") || "";

        changeStatusStudentName.value = studentName;
        changeStatusCurrent.value = currentStatus;
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initStudentsPage);
} else {
    initStudentsPage();
}
})();
