function initProfilePage() {
    const form = document.getElementById("accountDetailsForm");
    const editBtn = document.getElementById("editAccountDetailsBtn");
    const actions = document.getElementById("accountDetailsActions");
    const profilePhotoInput = document.getElementById("profilePhoto");
    const uploadPhotoBtn = document.getElementById("uploadPhotoBtn");
    const removePhotoBtn = document.getElementById("removePhotoBtn");
    const profileUsername = JSON.parse(document.getElementById("profileUsername")?.textContent || "\"user\"");
    const profileFullName = JSON.parse(document.getElementById("profileFullName")?.textContent || "\"\"");
    const profileEmail = JSON.parse(document.getElementById("profileEmail")?.textContent || "\"\"");
    const profilePabasaId = JSON.parse(document.getElementById("profilePabasaId")?.textContent || "\"\"");
    const profileRoleDisplay = JSON.parse(document.getElementById("profileRoleDisplay")?.textContent || "\"\"");
    const profileStorageKey = "pabasa_profile_settings_" + profileUsername;

    const accountFields = form ? form.querySelectorAll("[data-account-details-field]") : [];

    function setEditMode(editing) {
        accountFields.forEach(function (field) {
            field.disabled = !editing;
        });
        editBtn.classList.toggle("d-none", editing);
        actions.classList.toggle("d-none", !editing);
    }

    if (form && editBtn && actions) {
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
    }

    function getCsrfToken() {
        return document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
    }

    function postProfileAction(actionName, fields) {
        const formData = new FormData();
        formData.append(actionName, "true");
        formData.append("csrfmiddlewaretoken", getCsrfToken());
        Object.entries(fields || {}).forEach(function ([key, value]) {
            formData.append(key, value);
        });

        return fetch(window.location.pathname, {
            method: "POST",
            body: formData,
            headers: {
                "X-Requested-With": "XMLHttpRequest"
            }
        }).then(function (response) {
            return response.json();
        });
    }

    function loadProfileSettings() {
        try {
            return JSON.parse(localStorage.getItem(profileStorageKey) || "{}");
        } catch (error) {
            return {};
        }
    }

    function saveProfileSettings(settings) {
        localStorage.setItem(profileStorageKey, JSON.stringify(settings));
    }

    function setTwoFactorState(enabled) {
        const status = document.getElementById("twoFactorStatus");
        const button = document.getElementById("toggleTwoFactorBtn");
        if (status) {
            status.textContent = enabled ? "Enabled" : "Not Enabled";
            status.classList.toggle("bg-success", enabled);
            status.classList.toggle("bg-secondary", !enabled);
        }
        if (button) {
            button.textContent = enabled ? "Disable 2FA" : "Enable 2FA";
        }
    }

    function updatePreferenceState(toggle, enabled) {
        if (!toggle) return;
        const row = toggle.closest(".profile-info-row");
        const value = row ? row.querySelector(".profile-info-value") : null;
        toggle.checked = enabled;
        if (value) {
            value.textContent = enabled ? "On" : "Off";
        }
    }

    function getStoredValue(key, fallback) {
        try {
            const stored = localStorage.getItem(key);
            return stored ? JSON.parse(stored) : fallback;
        } catch (error) {
            return fallback;
        }
    }

    function getStoredArray(key) {
        const value = getStoredValue(key, []);
        return Array.isArray(value) ? value : [];
    }

    function countStoredCollection(key) {
        const value = getStoredValue(key, []);
        if (Array.isArray(value)) {
            return value.length;
        }
        if (value && typeof value === "object") {
            return Object.values(value).reduce(function (total, item) {
                return total + (Array.isArray(item) ? item.length : 1);
            }, 0);
        }
        return 0;
    }

    function countClassReadings() {
        const readingsByClass = getStoredValue("pabasa_class_readings", {});
        if (!readingsByClass || typeof readingsByClass !== "object" || Array.isArray(readingsByClass)) {
            return 0;
        }

        return Object.values(readingsByClass).reduce(function (total, readings) {
            if (!readings || typeof readings !== "object") {
                return total;
            }
            return total + ["word", "sentence", "paragraph", "story"].reduce(function (typeTotal, type) {
                const sing = Array.isArray(readings[type]) ? readings[type].length : 0;
                const plur = Array.isArray(readings[type + "s"]) ? readings[type + "s"].length : 0;
                return typeTotal + sing + plur;
            }, 0);
        }, 0);
    }

    function getTeacherOverviewStats() {
        const sampleClassCodes = ["RRG-9154", "AFC-7302", "ESL-5601"];
        const classes = getStoredArray("pabasa_teacher_classes").filter(function (classData) {
            return !sampleClassCodes.includes(classData.code);
        });
        const students = getStoredArray("pabasa_added_students").filter(function (student) {
            return student.name !== "Jay Park";
        });
        const storedStudentCount = students.length;
        const classStudentCount = classes.reduce(function (total, classData) {
            return total + (Number.parseInt(classData.students, 10) || 0);
        }, 0);
        const overviewStats = getStoredValue("pabasa_teacher_overview_stats", {});
        const storedMaterialsPosted = Number.parseInt(overviewStats.materialsPosted, 10) || 0;

        return {
            activeClasses: classes.length,
            totalStudents: Math.max(storedStudentCount, classStudentCount),
            materialsPosted: Math.max(countClassReadings(), countStoredCollection("pabasa_materials"), storedMaterialsPosted),
            reportsGenerated: countStoredCollection("pabasa_generated_reports")
        };
    }

    function updateClassOverview() {
        const stats = getTeacherOverviewStats();
        const activeClassesCount = document.getElementById("profileActiveClassesCount");
        const totalStudentsCount = document.getElementById("profileTotalStudentsCount");
        const materialsPostedCount = document.getElementById("profileMaterialsPostedCount");
        const reportsGeneratedCount = document.getElementById("profileReportsGeneratedCount");

        if (activeClassesCount) activeClassesCount.textContent = String(stats.activeClasses);
        if (totalStudentsCount) totalStudentsCount.textContent = String(stats.totalStudents);
        if (materialsPostedCount) materialsPostedCount.textContent = String(stats.materialsPosted);
        if (reportsGeneratedCount) reportsGeneratedCount.textContent = String(stats.reportsGenerated);
    }

    function updateStudentProgress() {
        try {
            // Get class codes with case-insensitive deduplication
            const codesArray = getStoredArray("pabasaStudentClassCodes").map(c => String(c).toUpperCase());
            const legacyCode = localStorage.getItem("pabasaStudentClassCode");
            if (legacyCode && !codesArray.includes(legacyCode.toUpperCase())) {
                codesArray.push(legacyCode.toUpperCase());
            }
            const studentCodes = codesArray.filter(Boolean);

            const seenIds = getStoredArray("pabasa_seen_material_ids").map(String);
            const readings = getStoredValue("pabasa_class_readings", {});
            
            // Build a normalized lookup map
            const readingsMap = {};
            Object.keys(readings).forEach(k => readingsMap[k.toUpperCase()] = readings[k]);

            let totalAvailable = 0;
            let completedCount = 0;

            studentCodes.forEach(code => {
                const classData = readingsMap[code];
                if (!classData) return;

                // Scan all possible material categories
                ['word', 'sentence', 'paragraph', 'story', 'all'].forEach(type => {
                    // Support both singular and plural keys
                    [type, type + 's'].forEach(key => {
                        const list = classData[key];
                        if (Array.isArray(list)) {
                            list.forEach(m => {
                                if (!m || !m.id) return;
                                totalAvailable++;
                                // Check if this specific material ID is in the "seen" list
                                if (seenIds.includes(String(m.id).trim())) {
                                    completedCount++;
                                }
                            });
                        }
                    });
                });
            });

            const percentage = totalAvailable > 0 ? Math.min(100, Math.round((completedCount / totalAvailable) * 100)) : 0;

            // Update the UI elements
            const classesEl = document.getElementById("profileStudentClassesCount");
            const completedEl = document.getElementById("profileStudentCompletedCount");
            const percentEl = document.getElementById("profileStudentProgressPercent");

            // "Total Lessons" should show the count of materials/lessons, not classes
            if (classesEl) classesEl.textContent = totalAvailable;
            if (completedEl) completedEl.textContent = completedCount;
            if (percentEl) percentEl.textContent = percentage + "%";

            // Update level and other persistent stats
            const totalStars = parseInt(localStorage.getItem("pabasa_total_stars") || "0", 10);
            const assessmentsCompleted = parseInt(localStorage.getItem("pabasa_assessments_completed") || "0", 10);
            
            const progressBar = document.getElementById("profileStudentProgressBar");
            if (progressBar) {
                progressBar.style.width = percentage + "%";
                progressBar.setAttribute("aria-valuenow", percentage);
            }

            const levelDisplay = document.getElementById("profileStudentLevel");
            if (levelDisplay) {
                // Level logic based on total progress
                let level = "Novice";
                if (completedCount >= 50 || totalStars >= 500 || assessmentsCompleted >= 10) level = "Expert Reader";
                else if (completedCount >= 20 || totalStars >= 200 || assessmentsCompleted >= 5) level = "Advanced";
                else if (completedCount >= 10 || totalStars >= 100 || assessmentsCompleted >= 2) level = "Intermediate";
                else if (completedCount > 0 || totalStars > 0) level = "Developing";
                
                levelDisplay.textContent = level;
            }

            console.log("PABASA Progress Sync:", { lessons: totalAvailable, completed: completedCount, progress: percentage + "%" });
        } catch (e) {
            console.error("PABASA: Error updating student progress", e);
        }
    }

    function updateDashboardClassStats() {
        const readings = getStoredValue("pabasa_class_readings", {});
        
        // Normalize readings map for case-insensitive class code lookups
        const readingsMap = {};
        Object.keys(readings).forEach(key => {
            readingsMap[key.toUpperCase()] = readings[key];
        });

        const cards = document.querySelectorAll("[data-class-card-code]");
        
        cards.forEach(card => {
            const code = card.getAttribute("data-class-card-code").toUpperCase();
            const classData = readingsMap[code];
            
            let practiceCount = 0;
            let assessmentCount = 0;
            
            if (classData) {
                ['word', 'sentence', 'paragraph', 'story'].forEach(type => {
                    [type, type + 's'].forEach(key => {
                        const materials = classData[key];
                        if (Array.isArray(materials)) {
                            materials.forEach(m => {
                                if (!m || !m.type) return;
                                const mType = m.type.toLowerCase();
                                if (mType === 'assessment' || mType === 'both') assessmentCount++;
                                if (mType === 'practice' || mType === 'both') practiceCount++;
                            });
                        }
                    });
                });
            }
            
            const pEl = card.querySelector(".practice-count");
            const aEl = card.querySelector(".assessment-count");
            if (pEl) pEl.textContent = `${practiceCount} set${practiceCount !== 1 ? 's' : ''}`;
            if (aEl) aEl.textContent = String(assessmentCount);

            // Update View Details link to point to the real student course view
            const viewBtn = card.querySelector(".view-details-btn") || card.querySelector(".view-class-btn") || card.querySelector("a.btn-primary");
            if (viewBtn) {
                viewBtn.setAttribute("href", `/dashboard/courses/student-view/?code=${code}`);
            }
        });
    }

    const savedSettings = loadProfileSettings();
    const emailNotifToggle = document.getElementById("emailNotifToggle");
    const pushNotifToggle = document.getElementById("pushNotifToggle");
    const digestToggle = document.getElementById("digestToggle");
    const passwordLastChanged = document.getElementById("passwordLastChanged");

    updatePreferenceState(emailNotifToggle, savedSettings.emailNotifications !== false);
    updatePreferenceState(pushNotifToggle, savedSettings.pushNotifications !== false);
    updatePreferenceState(digestToggle, savedSettings.weeklyDigest === true);
    if (passwordLastChanged && savedSettings.passwordLastChanged) {
        passwordLastChanged.textContent = savedSettings.passwordLastChanged;
    }
    setTwoFactorState(savedSettings.twoFactorEnabled === true);
    
    // Only run overview if we find teacher stats containers
    if (document.getElementById("profileActiveClassesCount")) {
        updateClassOverview();
    }
    updateStudentProgress();
    updateDashboardClassStats();

    [emailNotifToggle, pushNotifToggle, digestToggle].forEach(function (toggle) {
        if (!toggle) return;
        toggle.addEventListener("change", function () {
            const settings = loadProfileSettings();
            settings.emailNotifications = emailNotifToggle ? emailNotifToggle.checked : true;
            settings.pushNotifications = pushNotifToggle ? pushNotifToggle.checked : true;
            settings.weeklyDigest = digestToggle ? digestToggle.checked : false;
            saveProfileSettings(settings);
            updatePreferenceState(toggle, toggle.checked);
        });
    });

    const toggleTwoFactorBtn = document.getElementById("toggleTwoFactorBtn");
    if (toggleTwoFactorBtn) {
        toggleTwoFactorBtn.addEventListener("click", function () {
            const settings = loadProfileSettings();
            if (!confirm(settings.twoFactorEnabled ? "Disable two-factor authentication?" : "Enable two-factor authentication for this profile?")) {
                return;
            }
            settings.twoFactorEnabled = !settings.twoFactorEnabled;
            saveProfileSettings(settings);
            setTwoFactorState(settings.twoFactorEnabled);
        });
    }

    const changePasswordForm = document.getElementById("changePasswordForm");
    if (changePasswordForm) {
        changePasswordForm.addEventListener("submit", function (event) {
            event.preventDefault();
            const submitBtn = changePasswordForm.querySelector("button[type='submit']");
            const originalText = submitBtn ? submitBtn.textContent : "";
            if (submitBtn) {
                submitBtn.textContent = "Saving...";
                submitBtn.disabled = true;
            }

            postProfileAction("change_password", {
                current_password: document.getElementById("currentPassword")?.value || "",
                new_password: document.getElementById("newPassword")?.value || "",
                confirm_password: document.getElementById("confirmPassword")?.value || ""
            }).then(function (data) {
                if (!data.success) {
                    alert(data.error || "Could not change password");
                    return;
                }

                const settings = loadProfileSettings();
                settings.passwordLastChanged = "Just now";
                saveProfileSettings(settings);
                if (passwordLastChanged) passwordLastChanged.textContent = "Just now";
                changePasswordForm.reset();
                bootstrap.Modal.getInstance(document.getElementById("changePasswordModal"))?.hide();
                alert("Password changed successfully.");
            }).catch(function (error) {
                alert("Error changing password: " + error.message);
            }).finally(function () {
                if (submitBtn) {
                    submitBtn.textContent = originalText;
                    submitBtn.disabled = false;
                }
            });
        });
    }

    const downloadDataBtn = document.getElementById("downloadDataBtn");
    if (downloadDataBtn) {
        downloadDataBtn.addEventListener("click", function () {
            const data = {
                name: profileFullName,
                username: profileUsername,
                email: profileEmail,
                pabasa_id: profilePabasaId,
                role: profileRoleDisplay,
                preferences: loadProfileSettings(),
                exported_at: new Date().toISOString()
            };
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = "pabasa-profile-data.json";
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
        });
    }

    const deactivateAccountBtn = document.getElementById("deactivateAccountBtn");
    if (deactivateAccountBtn) {
        deactivateAccountBtn.addEventListener("click", function () {
            if (!confirm("Deactivate this account and sign out?")) return;
            const originalText = deactivateAccountBtn.textContent;
            deactivateAccountBtn.textContent = "Deactivating...";
            deactivateAccountBtn.disabled = true;
            postProfileAction("deactivate_account").then(function (data) {
                if (!data.success) {
                    alert(data.error || "Could not deactivate account");
                    return;
                }
                window.location.href = data.redirect_url || "/";
            }).catch(function (error) {
                alert("Error deactivating account: " + error.message);
            }).finally(function () {
                deactivateAccountBtn.textContent = originalText;
                deactivateAccountBtn.disabled = false;
            });
        });
    }

    const deleteAccountBtn = document.getElementById("deleteAccountBtn");
    if (deleteAccountBtn) {
        deleteAccountBtn.addEventListener("click", function () {
            if (!confirm("Delete this account permanently? This cannot be undone.")) return;
            const typed = prompt("Type DELETE to confirm account deletion.");
            if (typed !== "DELETE") return;
            const originalText = deleteAccountBtn.textContent;
            deleteAccountBtn.textContent = "Deleting...";
            deleteAccountBtn.disabled = true;
            postProfileAction("delete_account").then(function (data) {
                if (!data.success) {
                    alert(data.error || "Could not delete account");
                    return;
                }
                localStorage.removeItem(profileStorageKey);
                window.location.href = data.redirect_url || "/";
            }).catch(function (error) {
                alert("Error deleting account: " + error.message);
            }).finally(function () {
                deleteAccountBtn.textContent = originalText;
                deleteAccountBtn.disabled = false;
            });
        });
    }

    window.addEventListener("storage", function (event) {
        if (
            event.key === "pabasa_teacher_classes" ||
            event.key === "pabasa_added_students" ||
            event.key === "pabasa_class_readings" ||
            event.key === "pabasa_materials" ||
            event.key === "pabasa_teacher_overview_stats" ||
            event.key === "pabasa_generated_reports"
        ) {
            updateClassOverview();
        }
        if (
            event.key === "pabasa_seen_material_ids" ||
            event.key === "pabasa_class_readings" ||
            event.key === "pabasaStudentClassCodes" ||
            event.key === "pabasaStudentClassCode" ||
            event.key === "pabasa_total_stars" ||
            event.key === "pabasa_assessments_completed"
        ) {
            updateStudentProgress();
            updateDashboardClassStats();
        }
    });
    
    window.addEventListener("pabasa:student-class-updated", function() {
        updateStudentProgress();
        updateDashboardClassStats();
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
            formData.append("csrfmiddlewaretoken", getCsrfToken());

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
                        const photoUrl = data.photo_url + "?t=" + Date.now();
                        profileAvatarDisplay.style.background = "none";
                        profileAvatarDisplay.style.backgroundImage = "url('" + photoUrl + "')";
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
                        profileAvatarDisplay.textContent = profileAvatarDisplay.getAttribute("data-initials") || "";
                        profileAvatarDisplay.style.background = "";
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

    function initMicSettings() {
        const btnRequestMic = document.getElementById("btnRequestMic");
        const btnTestMic = document.getElementById("btnTestMic");
        const micStatusBadge = document.getElementById("micStatusBadge");
        const micDeviceSelect = document.getElementById("micDeviceSelect");
        const speakerDeviceSelect = document.getElementById("speakerDeviceSelect");
        const speakerVolumeInput = document.getElementById("speakerVolumeInput");
        const volumeValueDisplay = document.getElementById("volumeValue");
        const micVisualizerBar = document.getElementById("micVisualizerBar");
        
        let audioContext;
        let analyser;
        let microphone;
        let isTesting = false;
        let animationId;

        async function updateDeviceList() {
            try {
                const devices = await navigator.mediaDevices.enumerateDevices();
                const audioInputs = devices.filter(device => device.kind === 'audioinput');
                const audioOutputs = devices.filter(device => device.kind === 'audiooutput');
                
                if (micDeviceSelect) {
                    const savedMic = localStorage.getItem("pabasa_mic_device_id");
                    micDeviceSelect.innerHTML = audioInputs.map(device => 
                        `<option value="${device.deviceId}" ${device.deviceId === savedMic ? 'selected' : ''}>${device.label || 'Microphone ' + device.deviceId.slice(0, 5)}</option>`
                    ).join('') || '<option value="">No microphone detected</option>';
                }

                if (speakerDeviceSelect) {
                    const savedSpeaker = localStorage.getItem("pabasa_speaker_device_id");
                    speakerDeviceSelect.innerHTML = audioOutputs.map(device => 
                        `<option value="${device.deviceId}" ${device.deviceId === savedSpeaker ? 'selected' : ''}>${device.label || 'Speaker ' + device.deviceId.slice(0, 5)}</option>`
                    ).join('') || '<option value="">No speaker detected</option>';
                }
            } catch (err) {
                console.error("Error listing devices:", err);
            }
        }

        function updateMicStatus(state) {
            if (!micStatusBadge) return;
            micStatusBadge.textContent = state.charAt(0).toUpperCase() + state.slice(1);
            micStatusBadge.className = 'badge ' + (state === 'granted' ? 'bg-success' : state === 'denied' ? 'bg-danger' : 'bg-secondary');
            if (state === 'granted') updateDeviceList();
        }

        async function checkPermission() {
            try {
                const result = await navigator.permissions.query({ name: 'microphone' });
                updateMicStatus(result.state);
                result.onchange = () => updateMicStatus(result.state);
            } catch (err) {
                console.warn("Permissions API check failed for microphone");
            }
        }

        function draw() {
            if (!isTesting) return;
            const array = new Uint8Array(analyser.frequencyBinCount);
            analyser.getByteFrequencyData(array);
            let values = 0;
            for (let i = 0; i < array.length; i++) {
                values += array[i];
            }
            const average = values / array.length;
            if (micVisualizerBar) {
                micVisualizerBar.style.width = Math.min(100, average * 1.5) + "%";
            }
            animationId = requestAnimationFrame(draw);
        }

        async function startMicTest() {
            if (isTesting) return stopMicTest();

            try {
                const constraints = {
                    audio: micDeviceSelect.value ? { deviceId: { exact: micDeviceSelect.value } } : true
                };
                const stream = await navigator.mediaDevices.getUserMedia(constraints);
                
                updateMicStatus('granted');
                isTesting = true;
                if (btnTestMic) {
                    btnTestMic.innerHTML = '<i class="bi bi-stop-fill"></i> Stop Test';
                    btnTestMic.classList.replace('btn-outline-primary', 'btn-danger');
                }

                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                analyser = audioContext.createAnalyser();
                microphone = audioContext.createMediaStreamSource(stream);
                analyser.smoothingTimeConstant = 0.8;
                analyser.fftSize = 1024;
                microphone.connect(analyser);
                
                window._micStream = stream;
                draw();
            } catch (err) {
                alert("Could not access microphone: " + err.message);
                updateMicStatus('denied');
            }
        }

        function stopMicTest() {
            isTesting = false;
            cancelAnimationFrame(animationId);
            if (btnTestMic) {
                btnTestMic.innerHTML = '<i class="bi bi-play-fill"></i> Test Mic';
                btnTestMic.classList.replace('btn-danger', 'btn-outline-primary');
            }
            if (micVisualizerBar) micVisualizerBar.style.width = "0%";
            if (window._micStream) window._micStream.getTracks().forEach(t => t.stop());
            if (audioContext) audioContext.close();
        }

        btnRequestMic?.addEventListener("click", () => {
            navigator.mediaDevices.getUserMedia({ audio: true })
                .then(stream => {
                    stream.getTracks().forEach(t => t.stop());
                    updateMicStatus('granted');
                })
                .catch(err => {
                    alert("Permission denied: " + err.message);
                    updateMicStatus('denied');
                });
        });

        micDeviceSelect?.addEventListener("change", () => {
            localStorage.setItem("pabasa_mic_device_id", micDeviceSelect.value);
        });

        speakerDeviceSelect?.addEventListener("change", () => {
            localStorage.setItem("pabasa_speaker_device_id", speakerDeviceSelect.value);
        });

        speakerVolumeInput?.addEventListener("input", function() {
            if (volumeValueDisplay) volumeValueDisplay.textContent = this.value + "%";
            localStorage.setItem("pabasa_speaker_volume", this.value);
        });

        // Load initial volume
        (function loadInitialSpeakerSettings() {
            const savedVolume = localStorage.getItem("pabasa_speaker_volume");
            if (savedVolume && speakerVolumeInput) {
                speakerVolumeInput.value = savedVolume;
                if (volumeValueDisplay) volumeValueDisplay.textContent = savedVolume + "%";
            }
        })();

        btnTestMic?.addEventListener("click", startMicTest);
        checkPermission();
        updateDeviceList();
    }

    initMicSettings();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initProfilePage);
} else {
    initProfilePage();
}
