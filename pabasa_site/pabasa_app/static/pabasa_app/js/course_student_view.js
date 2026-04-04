document.addEventListener("DOMContentLoaded", function () {
    const lessonIcon = document.getElementById("lessonIcon");
    const lessonIconPreview = document.getElementById("lessonIconPreview");

    if (lessonIcon && lessonIconPreview) {
        lessonIcon.addEventListener("change", function () {
            lessonIconPreview.className = "bi " + lessonIcon.value;
        });
    }
});
