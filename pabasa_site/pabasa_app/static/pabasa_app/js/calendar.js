(function () {
    const monthLabel = document.getElementById("calendarMonthLabel");
    const monthChip = document.getElementById("calendarMonthChip");
    const body = document.getElementById("calendarBody");
    const prevBtn = document.getElementById("calendarPrevBtn");
    const nextBtn = document.getElementById("calendarNextBtn");
    const todayBtn = document.getElementById("calendarTodayBtn");

    if (!monthLabel || !body || !prevBtn || !nextBtn || !todayBtn) {
        return;
    }

    const today = new Date();
    let active = new Date(today.getFullYear(), today.getMonth(), 1);

    function renderCalendar() {
        const year = active.getFullYear();
        const month = active.getMonth();

        const firstDayIndex = new Date(year, month, 1).getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const daysInPrevMonth = new Date(year, month, 0).getDate();

        const title = active.toLocaleDateString("en-US", { month: "long", year: "numeric" });
        monthLabel.textContent = title;
        monthChip.innerHTML = '<i class="bi bi-calendar3"></i> ' + title;

        const cells = [];

        for (let i = firstDayIndex - 1; i >= 0; i -= 1) {
            cells.push({ day: daysInPrevMonth - i, muted: true, today: false });
        }

        for (let d = 1; d <= daysInMonth; d += 1) {
            const isToday = d === today.getDate() && month === today.getMonth() && year === today.getFullYear();
            cells.push({ day: d, muted: false, today: isToday });
        }

        while (cells.length % 7 !== 0) {
            cells.push({ day: cells.length - (firstDayIndex + daysInMonth) + 1, muted: true, today: false });
        }

        let rows = "";
        for (let i = 0; i < cells.length; i += 7) {
            const week = cells.slice(i, i + 7);
            rows += "<tr>" + week.map((cell) => {
                const classes = [];
                if (cell.muted) classes.push("is-muted");
                if (cell.today) classes.push("is-today");
                return '<td class="' + classes.join(" ") + '">' + cell.day + "</td>";
            }).join("") + "</tr>";
        }

        body.innerHTML = rows;
    }

    prevBtn.addEventListener("click", function () {
        active = new Date(active.getFullYear(), active.getMonth() - 1, 1);
        renderCalendar();
    });

    nextBtn.addEventListener("click", function () {
        active = new Date(active.getFullYear(), active.getMonth() + 1, 1);
        renderCalendar();
    });

    todayBtn.addEventListener("click", function () {
        active = new Date(today.getFullYear(), today.getMonth(), 1);
        renderCalendar();
    });

    window.requestAnimationFrame(renderCalendar);
})();
