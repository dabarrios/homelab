document.querySelectorAll(".field-form").forEach((form) => {
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const button = form.querySelector("button[type=submit]");
        const message = form.querySelector(".field-message");
        const originalLabel = button.textContent;
        button.disabled = true;
        button.textContent = "Saving…";
        message.className = "field-message";
        message.textContent = "";
        try {
            const response = await fetch(form.action, {
                method: "POST",
                body: new FormData(form),
                headers: {"X-Requested-With": "XMLHttpRequest"},
            });
            if (!response.ok) throw new Error("Please check this value and try again.");
            await response.json();
            message.textContent = "Saved";
            message.classList.add("is-success");
            button.textContent = "Saved";
            window.setTimeout(() => {
                button.textContent = originalLabel;
                message.textContent = "";
            }, 1800);
        } catch (error) {
            message.textContent = error.message;
            message.classList.add("is-error");
            button.textContent = originalLabel;
        } finally {
            button.disabled = false;
        }
    });
});
