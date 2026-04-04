(function () {
    const form = document.getElementById("accountDetailsForm");
    const editBtn = document.getElementById("editAccountDetailsBtn");
    const actions = document.getElementById("accountDetailsActions");

    if (!form || !editBtn || !actions) {
        return;
    }

    const accountFields = form.querySelectorAll("[data-account-details-field]");

    function setEditMode(editing) {
        accountFields.forEach(function (field) {
            field.disabled = !editing;
        });
        editBtn.classList.toggle("d-none", editing);
        actions.classList.toggle("d-none", !editing);
    }

    setEditMode(false);

    editBtn.addEventListener("click", function () {
        setEditMode(true);
        const firstField = form.querySelector("[data-account-details-field]");
        if (firstField) {
            firstField.focus();
        }
    });

    form.addEventListener("reset", function () {
        setTimeout(function () {
            setEditMode(false);
        }, 0);
    });
})();
