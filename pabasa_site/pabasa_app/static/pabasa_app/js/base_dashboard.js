(function () {
    const tooltipTargets = document.querySelectorAll("[data-nav-tooltip]");
    tooltipTargets.forEach(function (item) {
        new bootstrap.Tooltip(item, {
            placement: "right",
            trigger: "hover focus",
            container: "body"
        });
    });
})();

(function () {
    const collapseBtn = document.querySelector(".dashboard-sidebar [data-sidebar-collapse-btn]");
    if (!collapseBtn) {
        return;
    }

    const key = "pabasaSidebarCollapsed";

    function setCollapsed(collapsed) {
        document.body.classList.toggle("sidebar-collapsed", collapsed);
        collapseBtn.setAttribute("title", collapsed ? "Expand sidebar" : "Collapse sidebar");
        collapseBtn.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
        collapseBtn.innerHTML = collapsed
            ? '<i class="bi bi-chevron-right"></i>'
            : '<i class="bi bi-chevron-left"></i>';
    }

    setCollapsed(window.localStorage.getItem(key) === "1");

    collapseBtn.addEventListener("click", function () {
        const next = !document.body.classList.contains("sidebar-collapsed");
        setCollapsed(next);
        window.localStorage.setItem(key, next ? "1" : "0");
    });
})();

(function () {
    const helpToggleBtn = document.querySelector("[data-help-toggle]");
    const helpCloseBtn = document.querySelector("[data-help-close]");
    const helpPanel = document.getElementById("helpPanel");

    if (!helpToggleBtn || !helpPanel) {
        return;
    }

    function setHelpPanel(open) {
        document.body.classList.toggle("help-panel-open", open);
        helpPanel.setAttribute("aria-hidden", open ? "false" : "true");
        helpToggleBtn.setAttribute("aria-expanded", open ? "true" : "false");
    }

    helpToggleBtn.addEventListener("click", function () {
        const next = !document.body.classList.contains("help-panel-open");
        setHelpPanel(next);
    });

    if (helpCloseBtn) {
        helpCloseBtn.addEventListener("click", function () {
            setHelpPanel(false);
        });
    }

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && document.body.classList.contains("help-panel-open")) {
            setHelpPanel(false);
        }
    });
})();
