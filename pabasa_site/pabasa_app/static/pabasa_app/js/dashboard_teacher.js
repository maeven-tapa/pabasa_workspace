(function () {
    const createClassForm = document.getElementById("createClassForm");
    const classNameInput = document.getElementById("classNameInput");
    const classHeaderInput = document.getElementById("classHeaderInput");
    const classDescriptionInput = document.getElementById("classDescriptionInput");
    const generatedClassCode = document.getElementById("generatedClassCode");
    const regenerateCodeBtn = document.getElementById("regenerateCodeBtn");
    const classList = document.getElementById("classList");
    const classCount = document.getElementById("classCount");
    const copyClassCodeBtn = document.getElementById("copyClassCodeBtn");

    const activeClassName = document.getElementById("activeClassName");
    const activeClassSubject = document.getElementById("activeClassSubject");
    const activeClassDescription = document.getElementById("activeClassDescription");
    const activeClassCode = document.getElementById("activeClassCode");
    const activeStudentCount = document.getElementById("activeStudentCount");
    const classBanner = document.getElementById("classBanner");

    // Modal elements
    const deleteClassModal = document.getElementById("deleteClassModal");
    const deleteClassNameDisplay = document.getElementById("deleteClassNameDisplay");
    const confirmDeleteBtn = document.getElementById("confirmDeleteBtn");

    if (!createClassForm || !classList || !generatedClassCode) {
        return;
    }

    let classToDelete = null;

    function makeClassCode() {
        const letters = "ABCDEFGHJKLMNPQRSTUVWXYZ";
        let prefix = "";
        for (let i = 0; i < 4; i += 1) {
            prefix += letters[Math.floor(Math.random() * letters.length)];
        }
        const number = String(Math.floor(Math.random() * 1000)).padStart(3, "0");
        return prefix + "-" + number;
    }

    function setGeneratedCode() {
        generatedClassCode.textContent = makeClassCode();
    }

    function updateClassCount() {
        if (classCount) {
            classCount.textContent = String(classList.querySelectorAll(".class-card").length);
        }
    }

    function selectClass(card) {
        classList.querySelectorAll(".class-card").forEach(function (item) {
            item.classList.toggle("is-active", item === card);
        });

        const name = card.getAttribute("data-class-name") || "Reading Class";
        const subject = card.getAttribute("data-subject") || "Reading";
        const code = card.getAttribute("data-code") || "READ-000";
        const header = card.getAttribute("data-header") || "READ";
        const description = card.getAttribute("data-description") || "Class reading workspace.";
        const students = card.getAttribute("data-students") || "0";

        activeClassName.textContent = name;
        activeClassSubject.textContent = subject;
        activeClassDescription.textContent = description;
        activeClassCode.textContent = code;
        activeStudentCount.textContent = students;
        classBanner.setAttribute("data-header", header);
    }

    function createClassCard(name, header, description, code) {
        const card = document.createElement("div");
        card.className = "class-card";
        card.setAttribute("data-class-name", name);
        card.setAttribute("data-subject", name);
        card.setAttribute("data-code", code);
        card.setAttribute("data-header", header);
        card.setAttribute("data-description", description);
        card.setAttribute("data-students", "0");

        const deleteBtn = document.createElement("button");
        deleteBtn.className = "class-card-delete";
        deleteBtn.type = "button";
        deleteBtn.title = "Delete class";
        deleteBtn.setAttribute("aria-label", `Delete ${name} class`);
        deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';

        const head = document.createElement("span");
        head.className = "class-card-head";

        const title = document.createElement("strong");
        title.textContent = name;

        const codePill = document.createElement("span");
        codePill.className = "class-code-pill";
        codePill.textContent = code;

        const meta = document.createElement("span");
        meta.className = "small text-secondary";
        meta.textContent = name + " • 0 students";

        head.appendChild(title);
        head.appendChild(codePill);
        card.appendChild(deleteBtn);
        card.appendChild(head);
        card.appendChild(meta);

        return card;
    }

    function showDeleteConfirmation(card) {
        classToDelete = card;
        const className = card.getAttribute("data-class-name") || "this class";
        deleteClassNameDisplay.textContent = className;
        
        const modal = new bootstrap.Modal(deleteClassModal);
        modal.show();
    }

    function deleteClass(card) {
        const nextCard = card.nextElementSibling || card.previousElementSibling;
        card.remove();
        updateClassCount();
        
        if (nextCard && nextCard.classList && nextCard.classList.contains("class-card")) {
            selectClass(nextCard);
        } else {
            const remaining = classList.querySelector(".class-card");
            if (remaining) {
                selectClass(remaining);
            }
        }
    }

    classList.addEventListener("click", function (event) {
        const deleteBtn = event.target.closest(".class-card-delete");
        if (deleteBtn) {
            event.stopPropagation();
            const card = deleteBtn.closest(".class-card");
            if (card) {
                showDeleteConfirmation(card);
            }
            return;
        }

        const card = event.target.closest(".class-card");
        if (card) {
            selectClass(card);
        }
    });

    confirmDeleteBtn.addEventListener("click", function () {
        if (classToDelete) {
            deleteClass(classToDelete);
            classToDelete = null;
            const modal = bootstrap.Modal.getInstance(deleteClassModal);
            if (modal) {
                modal.hide();
            }
        }
    });

    createClassForm.addEventListener("submit", function (event) {
        event.preventDefault();

        const name = classNameInput.value.trim() || "New Reading Class";
        const header = (classHeaderInput.value.trim() || "READ").toUpperCase();
        const description = classDescriptionInput.value.trim() || "Reading class workspace.";
        const code = generatedClassCode.textContent.trim() || makeClassCode();
        const card = createClassCard(name, header, description, code);

        classList.prepend(card);
        selectClass(card);
        updateClassCount();
        setGeneratedCode();
    });

    regenerateCodeBtn.addEventListener("click", setGeneratedCode);

    if (copyClassCodeBtn) {
        copyClassCodeBtn.addEventListener("click", function () {
            const code = activeClassCode.textContent.trim();
            if (navigator.clipboard && code) {
                navigator.clipboard.writeText(code);
            }
            copyClassCodeBtn.innerHTML = '<i class="bi bi-check2 me-1"></i>Copied';
            window.setTimeout(function () {
                copyClassCodeBtn.innerHTML = '<i class="bi bi-copy me-1"></i>Copy Code';
            }, 1400);
        });
    }

    updateClassCount();
})();
