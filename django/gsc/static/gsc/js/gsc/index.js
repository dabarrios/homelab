const searchInput = document.querySelector("#server-search");
const serverCards = [...document.querySelectorAll("[data-server-card]")];
const emptyMessage = document.querySelector("#search-empty");

if (searchInput) {
    searchInput.addEventListener("input", (event) => {
        const query = event.target.value.trim().toLowerCase();
        let visibleCards = 0;
        serverCards.forEach((card) => {
            const matches = card.dataset.search.includes(query);
            card.hidden = !matches;
            if (matches) visibleCards += 1;
        });
        emptyMessage?.classList.toggle("is-hidden", visibleCards !== 0 || query === "");
    });
}
