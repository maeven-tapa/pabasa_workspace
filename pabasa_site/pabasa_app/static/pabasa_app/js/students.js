document.addEventListener("DOMContentLoaded", function () {
    const assignSectionModal = document.getElementById("assignSectionModal");
    const studentNameInput = document.getElementById("assignSectionStudentName");
    const currentSectionInput = document.getElementById("assignSectionCurrentSection");
    const changeStatusModal = document.getElementById("changeStatusModal");
    const changeStatusStudentName = document.getElementById("changeStatusStudentName");
    const changeStatusCurrent = document.getElementById("changeStatusCurrent");

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
});
