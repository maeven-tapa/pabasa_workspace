(function () {
    const form = document.getElementById("accountDetailsForm");
    const editBtn = document.getElementById("editAccountDetailsBtn");
    const actions = document.getElementById("accountDetailsActions");
    const profilePhotoInput = document.getElementById("profilePhoto");
    const uploadPhotoBtn = document.getElementById("uploadPhotoBtn");
    const removePhotoBtn = document.getElementById("removePhotoBtn");

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

    // Photo upload and remove logic
    if (profilePhotoInput && uploadPhotoBtn && removePhotoBtn) {
        // Handle file selection
        profilePhotoInput.addEventListener("change", function () {
            const file = this.files[0];
            if (file) {
                // Show file preview
                const reader = new FileReader();
                reader.onload = function (e) {
                    const profileAvatarDisplay = document.getElementById("profileAvatarDisplay");
                    if (profileAvatarDisplay) {
                        profileAvatarDisplay.textContent = "";
                        profileAvatarDisplay.style.backgroundImage = "url('" + e.target.result + "')";
                        profileAvatarDisplay.style.backgroundSize = "cover";
                        profileAvatarDisplay.style.backgroundPosition = "center";
                    }
                };
                reader.readAsDataURL(file);
            }
        });

        // Handle upload photo button
        uploadPhotoBtn.addEventListener("click", function () {
            const file = profilePhotoInput.files[0];
            if (!file) {
                alert("Please select a photo first");
                return;
            }

            const formData = new FormData();
            formData.append("profile_photo", file);
            formData.append("csrfmiddlewaretoken", document.querySelector("[name=csrfmiddlewaretoken]").value || "");

            // Show loading state
            const originalText = uploadPhotoBtn.textContent;
            uploadPhotoBtn.textContent = "Uploading...";
            uploadPhotoBtn.disabled = true;

            fetch(window.location.pathname, {
                method: "POST",
                body: formData,
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert("Photo uploaded successfully!");
                    // Update avatar display with the new photo URL
                    const profileAvatarDisplay = document.getElementById("profileAvatarDisplay");
                    if (profileAvatarDisplay && data.photo_url) {
                        profileAvatarDisplay.textContent = "";
                        profileAvatarDisplay.style.backgroundImage = "url('" + data.photo_url + "?t=" + Date.now() + "')";
                        profileAvatarDisplay.style.backgroundSize = "cover";
                        profileAvatarDisplay.style.backgroundPosition = "center";
                    }
                    setEditMode(false);
                    profilePhotoInput.value = "";
                } else {
                    alert("Error uploading photo: " + (data.error || "Unknown error"));
                }
            })
            .catch(error => {
                alert("Error uploading photo: " + error.message);
            })
            .finally(() => {
                uploadPhotoBtn.textContent = originalText;
                uploadPhotoBtn.disabled = false;
            });
        });

        // Handle remove photo button
        removePhotoBtn.addEventListener("click", function () {
            if (!confirm("Are you sure you want to remove your profile photo?")) {
                return;
            }

            const formData = new FormData();
            formData.append("remove_photo", "true");
            
            // Get CSRF token from the form
            const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
            if (csrfToken) {
                formData.append("csrfmiddlewaretoken", csrfToken);
            }

            // Show loading state
            const originalText = removePhotoBtn.textContent;
            removePhotoBtn.textContent = "Removing...";
            removePhotoBtn.disabled = true;

            fetch(window.location.pathname, {
                method: "POST",
                body: formData,
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert("Photo removed successfully!");
                    // Reset avatar to initials
                    const profileAvatarDisplay = document.getElementById("profileAvatarDisplay");
                    if (profileAvatarDisplay) {
                        profileAvatarDisplay.textContent = "IS";
                        profileAvatarDisplay.style.backgroundImage = "";
                        profileAvatarDisplay.style.backgroundSize = "";
                        profileAvatarDisplay.style.backgroundPosition = "";
                    }
                    setEditMode(false);
                    profilePhotoInput.value = "";
                } else {
                    alert("Error removing photo: " + (data.error || "Unknown error"));
                }
            })
            .catch(error => {
                alert("Error removing photo: " + error.message);
            })
            .finally(() => {
                removePhotoBtn.textContent = originalText;
                removePhotoBtn.disabled = false;
            });
        });
    }
})();
