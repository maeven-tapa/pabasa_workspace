(function () {
    const sortSelect = document.getElementById("rankingSort");
    const rankingList = document.getElementById("rankingList");

    if (!sortSelect || !rankingList) {
        return;
    }

    function rerank(order) {
        const items = Array.from(rankingList.querySelectorAll("[data-score]"));
        items.sort(function (a, b) {
            const aScore = Number(a.getAttribute("data-score"));
            const bScore = Number(b.getAttribute("data-score"));
            return order === "asc" ? aScore - bScore : bScore - aScore;
        });

        items.forEach(function (item, index) {
            const chip = item.querySelector(".rank-chip");
            if (chip) {
                chip.textContent = String(index + 1);
            }
            rankingList.appendChild(item);
        });
    }

    sortSelect.addEventListener("change", function () {
        rerank(sortSelect.value);
    });
})();
