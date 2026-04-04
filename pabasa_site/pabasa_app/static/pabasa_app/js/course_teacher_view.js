document.addEventListener("DOMContentLoaded", function () {
    const changeStatusModal = document.getElementById("changeStatusModal");
    const statusLessonName = document.getElementById("statusLessonName");
    const lessonStatus = document.getElementById("lessonStatus");
    const statusDraftPublishDateRow = document.getElementById("statusDraftPublishDateRow");
    const statusDraftPublishDate = document.getElementById("statusDraftPublishDate");
    const archivedOptionsSection = document.getElementById("archivedOptionsSection");
    const archiveUntilDateMode = document.getElementById("archiveUntilDateMode");
    const archiveTillCompleteMode = document.getElementById("archiveTillCompleteMode");
    const archiveTillIWantMode = document.getElementById("archiveTillIWantMode");
    const archiveUntilDateRow = document.getElementById("archiveUntilDateRow");
    const archiveTillCompleteRow = document.getElementById("archiveTillCompleteRow");
    const archiveUntilDate = document.getElementById("archiveUntilDate");
    const archiveTillCompleteSelect = document.getElementById("archiveTillCompleteSelect");
    const lessonIcon = document.getElementById("lessonIcon");
    const lessonIconPreview = document.getElementById("lessonIconPreview");
    const editLessonModal = document.getElementById("editLessonModal");
    const editLessonIcon = document.getElementById("editLessonIcon");
    const editLessonIconPreview = document.getElementById("editLessonIconPreview");
    const editLessonName = document.getElementById("editLessonName");
    const editLessonDescription = document.getElementById("editLessonDescription");
    const editLessonWeek = document.getElementById("editLessonWeek");
    const addLessonStatus = document.getElementById("addLessonStatus");
    const draftPublishDateRow = document.getElementById("draftPublishDateRow");
    const draftPublishDate = document.getElementById("draftPublishDate");
    const unlockAfterLesson = document.getElementById("unlockAfterLesson");
    const unlockByDateTime = document.getElementById("unlockByDateTime");
    const unlockAfterLessonRow = document.getElementById("unlockAfterLessonRow");
    const unlockAfterLessonSelect = document.getElementById("unlockAfterLessonSelect");
    const unlockByDateTimeRow = document.getElementById("unlockByDateTimeRow");
    const unlockDate = document.getElementById("unlockDate");
    const unlockTime = document.getElementById("unlockTime");
    const editQuizModal = document.getElementById("editQuizModal");
    const editQuizName = document.getElementById("editQuizName");
    const editQuizDescription = document.getElementById("editQuizDescription");
    const editQuizWeek = document.getElementById("editQuizWeek");
    const editUnlockAfterLesson = document.getElementById("editUnlockAfterLesson");
    const editUnlockByDateTime = document.getElementById("editUnlockByDateTime");
    const editUnlockAfterLessonRow = document.getElementById("editUnlockAfterLessonRow");
    const editUnlockAfterLessonSelect = document.getElementById("editUnlockAfterLessonSelect");
    const editUnlockByDateTimeRow = document.getElementById("editUnlockByDateTimeRow");
    const editUnlockDate = document.getElementById("editUnlockDate");
    const editUnlockTime = document.getElementById("editUnlockTime");
    const editTriesCount = document.getElementById("editTriesCount");
    const addItemModal = document.getElementById("addItemModal");
    const itemLessonName = document.getElementById("itemLessonName");
    const readingType = document.getElementById("readingType");
    const removeLessonModal = document.getElementById("removeLessonModal");
    const removeLessonName = document.getElementById("removeLessonName");
    const lessonCardCols = Array.from(document.querySelectorAll(".lesson-card-col"));
    const lessonCardGrids = Array.from(document.querySelectorAll(".lesson-cards-grid"));
    let draggingCard = null;

    if (!changeStatusModal || !statusLessonName) {
        return;
    }

    function toggleArchiveModeRows() {
        if (!archiveUntilDateMode || !archiveTillCompleteMode || !archiveUntilDateRow || !archiveTillCompleteRow) {
            return;
        }

        const isUntilDate = archiveUntilDateMode.checked;
        const isTillComplete = archiveTillCompleteMode.checked;
        archiveUntilDateRow.classList.toggle("d-none", !isUntilDate);
        archiveTillCompleteRow.classList.toggle("d-none", !isTillComplete);

        if (archiveUntilDate) {
            archiveUntilDate.required = isUntilDate;
            if (!isUntilDate) {
                archiveUntilDate.value = "";
            }
        }

        if (archiveTillCompleteSelect) {
            archiveTillCompleteSelect.required = isTillComplete;
        }
    }

    function toggleStatusDraftPublishDate() {
        if (!lessonStatus || !statusDraftPublishDateRow || !archivedOptionsSection) {
            return;
        }

        const isDraft = lessonStatus.value === "draft";
        const isArchived = lessonStatus.value === "archived";
        statusDraftPublishDateRow.classList.toggle("d-none", !isDraft);
        archivedOptionsSection.classList.toggle("d-none", !isArchived);

        if (statusDraftPublishDate) {
            statusDraftPublishDate.required = isDraft;
            if (!isDraft) {
                statusDraftPublishDate.value = "";
            }
        }

        if (!isArchived) {
            if (archiveUntilDate) {
                archiveUntilDate.required = false;
                archiveUntilDate.value = "";
            }
            if (archiveTillCompleteSelect) {
                archiveTillCompleteSelect.required = false;
            }
        } else {
            toggleArchiveModeRows();
        }
    }

    changeStatusModal.addEventListener("show.bs.modal", function (event) {
        const trigger = event.relatedTarget;
        const lessonTitle = trigger ? trigger.getAttribute("data-lesson-title") : "Lesson";
        statusLessonName.textContent = lessonTitle || "Lesson";
        toggleStatusDraftPublishDate();
    });

    if (lessonStatus) {
        lessonStatus.addEventListener("change", toggleStatusDraftPublishDate);
        toggleStatusDraftPublishDate();
    }

    if (archiveUntilDateMode) {
        archiveUntilDateMode.addEventListener("change", toggleArchiveModeRows);
    }

    if (archiveTillCompleteMode) {
        archiveTillCompleteMode.addEventListener("change", toggleArchiveModeRows);
    }

    if (archiveTillIWantMode) {
        archiveTillIWantMode.addEventListener("change", toggleArchiveModeRows);
    }

    if (lessonIcon && lessonIconPreview) {
        lessonIcon.addEventListener("change", function () {
            lessonIconPreview.className = "bi " + lessonIcon.value;
        });
    }

    if (editLessonIcon && editLessonIconPreview) {
        editLessonIcon.addEventListener("change", function () {
            editLessonIconPreview.className = "bi " + editLessonIcon.value;
        });
    }

    if (editLessonModal && editLessonName && editLessonDescription && editLessonWeek && editLessonIcon && editLessonIconPreview) {
        editLessonModal.addEventListener("show.bs.modal", function (event) {
            const trigger = event.relatedTarget;

            const lessonTitle = trigger ? trigger.getAttribute("data-lesson-title") : "";
            const lessonDescription = trigger ? trigger.getAttribute("data-lesson-description") : "";
            const lessonWeek = trigger ? trigger.getAttribute("data-lesson-week") : "week1";
            const lessonIconClass = trigger ? trigger.getAttribute("data-lesson-icon") : "bi-journal-richtext";

            editLessonName.value = lessonTitle || "";
            editLessonDescription.value = lessonDescription || "";
            editLessonWeek.value = lessonWeek || "week1";
            editLessonIcon.value = lessonIconClass || "bi-journal-richtext";
            editLessonIconPreview.className = "bi " + editLessonIcon.value;
        });
    }

    function toggleDraftPublishDate() {
        if (!addLessonStatus || !draftPublishDateRow) {
            return;
        }

        const isDraft = addLessonStatus.value === "draft";
        draftPublishDateRow.classList.toggle("d-none", !isDraft);

        if (draftPublishDate) {
            draftPublishDate.required = isDraft;
            if (!isDraft) {
                draftPublishDate.value = "";
            }
        }
    }

    if (addLessonStatus) {
        addLessonStatus.addEventListener("change", toggleDraftPublishDate);
        toggleDraftPublishDate();
    }

    function toggleQuizUnlockRows() {
        const useAfterLesson = unlockAfterLesson && unlockAfterLesson.checked;
        const useDateTime = unlockByDateTime && unlockByDateTime.checked;

        if (unlockAfterLessonRow) {
            unlockAfterLessonRow.classList.toggle("d-none", !useAfterLesson);
        }

        if (unlockByDateTimeRow) {
            unlockByDateTimeRow.classList.toggle("d-none", !useDateTime);
        }

        if (unlockAfterLessonSelect) {
            unlockAfterLessonSelect.required = !!useAfterLesson;
        }

        if (unlockDate) {
            unlockDate.required = !!useDateTime;
            if (!useDateTime) {
                unlockDate.value = "";
            }
        }

        if (unlockTime) {
            unlockTime.required = !!useDateTime;
            if (!useDateTime) {
                unlockTime.value = "";
            }
        }
    }

    if (unlockAfterLesson) {
        unlockAfterLesson.addEventListener("change", toggleQuizUnlockRows);
    }

    if (unlockByDateTime) {
        unlockByDateTime.addEventListener("change", toggleQuizUnlockRows);
    }

    toggleQuizUnlockRows();

    function toggleEditQuizUnlockRows() {
        const useAfterLesson = editUnlockAfterLesson && editUnlockAfterLesson.checked;
        const useDateTime = editUnlockByDateTime && editUnlockByDateTime.checked;

        if (editUnlockAfterLessonRow) {
            editUnlockAfterLessonRow.classList.toggle("d-none", !useAfterLesson);
        }

        if (editUnlockByDateTimeRow) {
            editUnlockByDateTimeRow.classList.toggle("d-none", !useDateTime);
        }

        if (editUnlockAfterLessonSelect) {
            editUnlockAfterLessonSelect.required = !!useAfterLesson;
        }

        if (editUnlockDate) {
            editUnlockDate.required = !!useDateTime;
            if (!useDateTime) {
                editUnlockDate.value = "";
            }
        }

        if (editUnlockTime) {
            editUnlockTime.required = !!useDateTime;
            if (!useDateTime) {
                editUnlockTime.value = "";
            }
        }
    }

    if (editUnlockAfterLesson) {
        editUnlockAfterLesson.addEventListener("change", toggleEditQuizUnlockRows);
    }

    if (editUnlockByDateTime) {
        editUnlockByDateTime.addEventListener("change", toggleEditQuizUnlockRows);
    }

    if (editQuizModal) {
        editQuizModal.addEventListener("show.bs.modal", function (event) {
            const trigger = event.relatedTarget;

            const quizTitle = trigger ? trigger.getAttribute("data-quiz-title") : "";
            const quizDescription = trigger ? trigger.getAttribute("data-quiz-description") : "";
            const quizWeek = trigger ? trigger.getAttribute("data-quiz-week") : "week1";
            const unlockRule = trigger ? trigger.getAttribute("data-quiz-unlock-rule") : "after_lesson";
            const unlockLesson = trigger ? trigger.getAttribute("data-quiz-unlock-lesson") : "lesson_1";
            const unlockDateValue = trigger ? trigger.getAttribute("data-quiz-unlock-date") : "";
            const unlockTimeValue = trigger ? trigger.getAttribute("data-quiz-unlock-time") : "";
            const triesCountValue = trigger ? trigger.getAttribute("data-quiz-tries") : "3";

            if (editQuizName) {
                editQuizName.value = quizTitle || "";
            }

            if (editQuizDescription) {
                editQuizDescription.value = quizDescription || "";
            }

            if (editQuizWeek) {
                editQuizWeek.value = quizWeek || "week1";
            }

            if (editTriesCount) {
                editTriesCount.value = triesCountValue || "3";
            }

            if (unlockRule === "by_datetime") {
                if (editUnlockByDateTime) {
                    editUnlockByDateTime.checked = true;
                }
                if (editUnlockDate) {
                    editUnlockDate.value = unlockDateValue || "";
                }
                if (editUnlockTime) {
                    editUnlockTime.value = unlockTimeValue || "";
                }
            } else {
                if (editUnlockAfterLesson) {
                    editUnlockAfterLesson.checked = true;
                }
                if (editUnlockAfterLessonSelect) {
                    editUnlockAfterLessonSelect.value = unlockLesson || "lesson_1";
                }
            }

            toggleEditQuizUnlockRows();
        });
    }

    toggleEditQuizUnlockRows();

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
            const lessonTitle = trigger ? trigger.getAttribute("data-lesson-title") : "Lesson";
            itemLessonName.textContent = lessonTitle || "Lesson";
        });
    }

    if (removeLessonModal && removeLessonName) {
        removeLessonModal.addEventListener("show.bs.modal", function (event) {
            const trigger = event.relatedTarget;
            const lessonTitle = trigger ? trigger.getAttribute("data-lesson-title") : "this lesson";
            removeLessonName.textContent = lessonTitle || "this lesson";
        });
    }

    lessonCardCols.forEach(function (cardCol) {
        cardCol.addEventListener("dragstart", function (event) {
            draggingCard = cardCol;
            cardCol.classList.add("dragging");
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData("text/plain", "lesson-card");
        });

        cardCol.addEventListener("dragend", function () {
            cardCol.classList.remove("dragging");
            draggingCard = null;
        });
    });

    lessonCardGrids.forEach(function (grid) {
        grid.addEventListener("dragover", function (event) {
            if (!draggingCard) {
                return;
            }

            event.preventDefault();
            const targetCard = event.target.closest(".lesson-card-col");

            if (!targetCard || targetCard === draggingCard) {
                return;
            }

            const rect = targetCard.getBoundingClientRect();
            const placeBefore = event.clientX < rect.left + rect.width / 2;

            if (placeBefore) {
                grid.insertBefore(draggingCard, targetCard);
            } else {
                grid.insertBefore(draggingCard, targetCard.nextElementSibling);
            }
        });

        grid.addEventListener("drop", function (event) {
            if (!draggingCard) {
                return;
            }

            event.preventDefault();
            const targetCard = event.target.closest(".lesson-card-col");

            if (!targetCard) {
                grid.appendChild(draggingCard);
            }
        });
    });
});
