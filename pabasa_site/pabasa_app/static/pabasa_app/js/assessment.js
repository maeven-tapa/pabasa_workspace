document.addEventListener("DOMContentLoaded", function () {
    const addItemModal = document.getElementById("addItemModal");
    const itemLessonName = document.getElementById("itemLessonName");
    const readingType = document.getElementById("readingType");
    const viewResponseModal = document.getElementById("viewResponseModal");
    const responseTestName = document.getElementById("responseTestName");
    const responseSummaryModal = document.getElementById("responseSummaryModal");
    const startAssessmentModal = document.getElementById("startAssessmentModal");
    const startAssessmentName = document.getElementById("startAssessmentName");
    const startAssessmentCode = document.getElementById("startAssessmentCode");
    const summaryStudentName = document.getElementById("summaryStudentName");
    const summaryAccuracy = document.getElementById("summaryAccuracy");
    const summaryTimeRead = document.getElementById("summaryTimeRead");
    const summaryWordsToPractice = document.getElementById("summaryWordsToPractice");
    const summaryWpm = document.getElementById("summaryWpm");
    const summaryReadOverTotal = document.getElementById("summaryReadOverTotal");
    const editTestModal = document.getElementById("editTestModal");
    const editTestIcon = document.getElementById("editTestIcon");
    const editTestIconPreview = document.getElementById("editTestIconPreview");
    const editTestTitle = document.getElementById("editTestTitle");
    const editTestDescription = document.getElementById("editTestDescription");
    const enableTargetReadingTime = document.getElementById("enableTargetReadingTime");
    const targetReadingTimeRow = document.getElementById("targetReadingTimeRow");
    const targetReadingTime = document.getElementById("targetReadingTime");
    const editSectionOnly = document.getElementById("editSectionOnly");
    const editSectionOnlyRow = document.getElementById("editSectionOnlyRow");
    const editAllowedSection = document.getElementById("editAllowedSection");
    const sendParentEmail = document.getElementById("sendParentEmail");
    const parentEmailRow = document.getElementById("parentEmailRow");
    const parentEmail = document.getElementById("parentEmail");
    const enableAssessmentAvailability = document.getElementById("enableAssessmentAvailability");
    const scheduleSectionRow = document.getElementById("scheduleSectionRow");
    const availabilityStartDate = document.getElementById("availabilityStartDate");
    const availabilityStartTime = document.getElementById("availabilityStartTime");
    const availabilityEndDate = document.getElementById("availabilityEndDate");
    const availabilityEndTime = document.getElementById("availabilityEndTime");

    function toggleSectionOnlyRow() {
        if (!editSectionOnly || !editSectionOnlyRow || !editAllowedSection) {
            return;
        }

        const isChecked = editSectionOnly.checked;
        editSectionOnlyRow.classList.toggle("d-none", !isChecked);
        editAllowedSection.required = isChecked;
        if (!isChecked) {
            editAllowedSection.value = "grade5a";
        }
    }

    if (editSectionOnly) {
        editSectionOnly.addEventListener("change", toggleSectionOnlyRow);
    }

    function toggleTargetReadingTimeRow() {
        if (!enableTargetReadingTime || !targetReadingTimeRow || !targetReadingTime) {
            return;
        }

        const isEnabled = enableTargetReadingTime.checked;
        targetReadingTimeRow.classList.toggle("d-none", !isEnabled);
        targetReadingTime.required = isEnabled;

        if (!isEnabled) {
            targetReadingTime.value = "";
        }
    }

    if (enableTargetReadingTime) {
        enableTargetReadingTime.addEventListener("change", toggleTargetReadingTimeRow);
    }

    function toggleParentEmailRows() {
        if (!sendParentEmail || !parentEmailRow || !parentEmail) {
            return;
        }

        const isParentEmailEnabled = sendParentEmail.checked;
        parentEmailRow.classList.toggle("d-none", !isParentEmailEnabled);
        parentEmail.required = isParentEmailEnabled;

        if (!isParentEmailEnabled) {
            parentEmail.value = "";
        }
    }

    if (sendParentEmail) {
        sendParentEmail.addEventListener("change", toggleParentEmailRows);
    }

    function toggleAvailabilitySection() {
        if (!enableAssessmentAvailability || !scheduleSectionRow) {
            return;
        }

        const isEnabled = enableAssessmentAvailability.checked;
        scheduleSectionRow.classList.toggle("d-none", !isEnabled);

        [availabilityStartDate, availabilityStartTime, availabilityEndDate, availabilityEndTime].forEach(function (field) {
            if (!field) {
                return;
            }

            field.required = isEnabled;
            if (!isEnabled) {
                field.value = "";
            }
        });
    }

    if (enableAssessmentAvailability) {
        enableAssessmentAvailability.addEventListener("change", toggleAvailabilitySection);
    }

    function updateReadingSections(value) {
        document.querySelectorAll("[data-reading-section]").forEach(function (section) {
            section.classList.toggle("d-none", section.getAttribute("data-reading-section") !== value);
        });
    }

    if (readingType) {
        readingType.addEventListener("change", function () {
            updateReadingSections(readingType.value);
        });
        updateReadingSections(readingType.value);
    }

    if (addItemModal && itemLessonName) {
        addItemModal.addEventListener("show.bs.modal", function (event) {
            const trigger = event.relatedTarget;
            const lessonTitle = trigger ? trigger.getAttribute("data-lesson-title") : "Assessment";
            itemLessonName.textContent = lessonTitle || "Assessment";
        });
    }

    if (viewResponseModal && responseTestName) {
        viewResponseModal.addEventListener("show.bs.modal", function (event) {
            const trigger = event.relatedTarget;
            const testTitle = trigger ? trigger.getAttribute("data-test-title") : "Assessment";
            responseTestName.textContent = testTitle || "Assessment";
        });
    }

    if (responseSummaryModal) {
        responseSummaryModal.addEventListener("show.bs.modal", function (event) {
            const trigger = event.relatedTarget;
            const studentName = trigger ? trigger.getAttribute("data-student-name") : "Student";
            const accuracy = trigger ? trigger.getAttribute("data-accuracy") : "-";
            const timeRead = trigger ? trigger.getAttribute("data-time-read") : "-";
            const wordsToPractice = trigger ? trigger.getAttribute("data-words-practice") : "-";
            const wpm = trigger ? trigger.getAttribute("data-wpm") : "-";
            const readWords = trigger ? trigger.getAttribute("data-read-words") : "-";
            const totalWords = trigger ? trigger.getAttribute("data-total-words") : "-";

            if (summaryStudentName) {
                summaryStudentName.textContent = studentName || "Student";
            }

            if (summaryAccuracy) {
                summaryAccuracy.textContent = accuracy || "-";
            }

            if (summaryTimeRead) {
                summaryTimeRead.textContent = timeRead || "-";
            }

            if (summaryWordsToPractice) {
                summaryWordsToPractice.textContent = wordsToPractice || "-";
            }

            if (summaryWpm) {
                summaryWpm.textContent = wpm || "-";
            }

            if (summaryReadOverTotal) {
                summaryReadOverTotal.textContent = (readWords || "-") + " / " + (totalWords || "-");
            }
        });
    }

    if (startAssessmentModal) {
        startAssessmentModal.addEventListener("show.bs.modal", function (event) {
            const trigger = event.relatedTarget;
            const testTitle = trigger ? trigger.getAttribute("data-test-title") : "Assessment";
            const testCode = trigger ? trigger.getAttribute("data-test-code") : "TST-000";

            if (startAssessmentName) {
                startAssessmentName.textContent = testTitle || "Assessment";
            }

            if (startAssessmentCode) {
                startAssessmentCode.textContent = testCode || "TST-000";
            }
        });
    }

    if (editTestIcon && editTestIconPreview) {
        editTestIcon.addEventListener("change", function () {
            editTestIconPreview.className = "bi " + editTestIcon.value;
        });
    }

    if (editTestModal) {
        editTestModal.addEventListener("show.bs.modal", function (event) {
            const trigger = event.relatedTarget;
            const testTitle = trigger ? trigger.getAttribute("data-test-title") : "";
            const testDescription = trigger ? trigger.getAttribute("data-test-description") : "";
            const testIcon = trigger ? trigger.getAttribute("data-test-icon") : "bi-journal-check";
            const sectionOnly = trigger ? trigger.getAttribute("data-section-only") : "false";
            const testSection = trigger ? trigger.getAttribute("data-test-section") : "grade5a";

            if (editTestTitle) {
                editTestTitle.value = testTitle || "";
            }

            if (editTestDescription) {
                editTestDescription.value = testDescription || "";
            }

            if (editTestIcon) {
                editTestIcon.value = testIcon || "bi-journal-check";
            }

            if (editTestIconPreview) {
                editTestIconPreview.className = "bi " + (testIcon || "bi-journal-check");
            }

            if (editSectionOnly) {
                editSectionOnly.checked = sectionOnly === "true";
            }

            if (enableTargetReadingTime) {
                enableTargetReadingTime.checked = false;
            }

            if (editAllowedSection) {
                editAllowedSection.value = testSection || "grade5a";
            }

            if (sendParentEmail) {
                sendParentEmail.checked = false;
            }

            if (enableAssessmentAvailability) {
                enableAssessmentAvailability.checked = false;
            }

            toggleParentEmailRows();
            toggleAvailabilitySection();
            toggleTargetReadingTimeRow();

            toggleSectionOnlyRow();
        });
    }

    toggleSectionOnlyRow();
    toggleParentEmailRows();
    toggleAvailabilitySection();
    toggleTargetReadingTimeRow();
});
