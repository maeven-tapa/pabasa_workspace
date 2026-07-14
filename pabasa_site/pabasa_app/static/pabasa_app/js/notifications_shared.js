(function () {
    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value == null ? "" : String(value);
        return div.innerHTML;
    }

    function getNotificationTypeMeta(notificationType, actionUrl) {
        const type = String(notificationType || "").toLowerCase();
        const url = String(actionUrl || "").toLowerCase();

        if (type === "material" || url.includes("/practice/")) {
            return { icon: "bi-book", label: "New reading material" };
        }
        if (type === "class" || url.includes("/manage/") || url.includes("/courses/")) {
            return { icon: "bi-people", label: "Class update" };
        }
        if (type === "assessment" || url.includes("/assessment/")) {
            return { icon: "bi-clipboard-check", label: "Assessment update" };
        }
        if (type === "success") {
            return { icon: "bi-check2-circle", label: "Completed" };
        }
        if (type === "warning") {
            return { icon: "bi-exclamation-circle", label: "Attention needed" };
        }
        if (type === "error") {
            return { icon: "bi-x-circle", label: "Issue detected" };
        }
        return { icon: "bi-bell", label: "General update" };
    }

    function formatNotificationRelativeTime(value) {
        if (!value) return "";
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "";

        const diffMs = Date.now() - date.getTime();
        const diffMinutes = Math.max(0, Math.round(diffMs / 60000));
        if (diffMinutes < 1) return "Just now";
        if (diffMinutes < 60) return diffMinutes + "m ago";

        const diffHours = Math.round(diffMinutes / 60);
        if (diffHours < 24) return diffHours + "h ago";

        const diffDays = Math.round(diffHours / 24);
        if (diffDays < 7) return diffDays + "d ago";

        return date.toLocaleDateString([], { month: "short", day: "numeric" });
    }

    function getNotificationDateGroup(value) {
        const date = value ? new Date(value) : null;
        if (!date || Number.isNaN(date.getTime())) return "Earlier";

        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const target = new Date(date.getFullYear(), date.getMonth(), date.getDate());
        const diffDays = Math.round((today - target) / 86400000);

        if (diffDays <= 0) return "Today";
        if (diffDays === 1) return "Yesterday";
        if (diffDays < 7) return "Earlier this week";
        return "Earlier";
    }

    function groupNotificationsByDate(notifications) {
        const order = ["Today", "Yesterday", "Earlier this week", "Earlier"];
        const grouped = new Map(order.map(function (label) { return [label, []]; }));
        notifications.forEach(function (notification) {
            const label = getNotificationDateGroup(notification.created_at);
            if (!grouped.has(label)) grouped.set(label, []);
            grouped.get(label).push(notification);
        });
        return Array.from(grouped.entries()).filter(function (entry) {
            return entry[1].length;
        });
    }

    function renderNotificationEmptyState() {
        return [
            '<div class="notif-empty">',
            '<div class="notif-empty-icon"><i class="bi bi-stars"></i></div>',
            '<p class="notif-empty-title">You\'re all caught up!</p>',
            '<p class="notif-empty-copy">New updates will appear here as soon as they arrive.</p>',
            "</div>",
        ].join("");
    }

    function renderNotificationErrorState(message) {
        return [
            '<div class="notif-error">',
            '<div class="notif-error-icon"><i class="bi bi-wifi-off"></i></div>',
            '<p class="notif-error-title">Notifications unavailable</p>',
            '<p class="notif-error-copy">', escapeHtml(message || "Please try again in a moment."), "</p>",
            "</div>",
        ].join("");
    }

    function renderNotificationCard(notification) {
        const actionUrl = notification.action_url || "";
        const meta = getNotificationTypeMeta(notification.notification_type, actionUrl);
        const relativeTime = formatNotificationRelativeTime(notification.created_at);
        const fullTime = notification.created_at
            ? new Date(notification.created_at).toLocaleString([], {
                month: "short",
                day: "numeric",
                year: "numeric",
                hour: "numeric",
                minute: "2-digit"
            })
            : "";
        const isRead = Boolean(notification.is_read);

        return [
            '<article class="notif-item ', isRead ? "is-read" : "is-unread", '" data-notification-card data-notification-id="', escapeHtml(notification.id), '" data-action-url="', escapeHtml(actionUrl), '" role="button" tabindex="0" aria-label="', escapeHtml(notification.title || "Notification"), '">',
            '<div class="notif-type-icon" aria-hidden="true"><i class="bi ', meta.icon, '"></i></div>',
            '<div class="notif-body">',
            '<div class="notif-title-row"><p class="notif-title">', escapeHtml(notification.title || "Notification"), "</p></div>",
            '<p class="notif-message">', escapeHtml(notification.message || ""), "</p>",
            '<div class="notif-meta">',
            '<span class="notif-status-pill">', isRead ? "Read" : "Unread", "</span>",
            '<time class="notif-time" datetime="', escapeHtml(notification.created_at || ""), '" title="', escapeHtml(fullTime), '">', escapeHtml(relativeTime || fullTime), "</time>",
            "</div>",
            "</div>",
            '<button class="notif-read-toggle ', isRead ? "is-read" : "", '" type="button" data-mark-read data-notification-id="', escapeHtml(notification.id), '" aria-pressed="', isRead ? "true" : "false", '" aria-label="', isRead ? "Notification already read" : "Mark notification as read", '" title="', isRead ? "Read" : "Mark as read", '"><i class="bi bi-check2-circle"></i></button>',
            "</article>",
        ].join("");
    }

    function renderNotificationsMarkup(notifications) {
        if (!notifications.length) {
            return renderNotificationEmptyState();
        }

        const groups = groupNotificationsByDate(notifications);
        return [
            '<div class="notif-list">',
            groups.map(function (group) {
                const label = group[0];
                const items = group[1];
                return [
                    '<section class="notif-group" aria-label="', escapeHtml(label), '">',
                    '<p class="notif-group-label">', escapeHtml(label), "</p>",
                    '<div class="notif-cards">',
                    items.map(renderNotificationCard).join(""),
                    "</div></section>",
                ].join("");
            }).join(""),
            "</div>",
        ].join("");
    }

    function updateHeaderBadge(root, unreadCount) {
        const scope = root || document;
        scope.querySelectorAll("[data-notification-header-badge]").forEach(function (badge) {
            const count = Number(unreadCount) || 0;
            badge.textContent = count > 99 ? "99+" : String(count);
            badge.classList.toggle("is-hidden", count <= 0);
        });
    }

    function confirmClearAll(modalId) {
        return new Promise(function (resolve) {
            const targetId = modalId || "clearNotificationsConfirmModal";
            const modalEl = document.getElementById(targetId);
            if (!modalEl || !window.bootstrap || !bootstrap.Modal) {
                resolve(false);
                return;
            }

            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            let settled = false;

            function finish(result) {
                if (settled) return;
                settled = true;
                modalEl.removeEventListener("hidden.bs.modal", onHidden);
                confirmBtn?.removeEventListener("click", onConfirm);
                resolve(result);
            }

            function onHidden() {
                finish(false);
            }

            function onConfirm() {
                finish(true);
                modal.hide();
            }

            const confirmBtn = modalEl.querySelector("[data-notification-clear-confirm]");
            modalEl.addEventListener("hidden.bs.modal", onHidden);
            confirmBtn?.addEventListener("click", onConfirm, { once: true });
            modal.show();
        });
    }

    window.PabasaNotificationsShared = {
        renderNotificationsMarkup: renderNotificationsMarkup,
        renderNotificationErrorState: renderNotificationErrorState,
        renderNotificationEmptyState: renderNotificationEmptyState,
        updateHeaderBadge: updateHeaderBadge,
        confirmClearAll: confirmClearAll,
    };
})();
