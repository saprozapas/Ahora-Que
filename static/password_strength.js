document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-password-strength]").forEach((input) => {
    const container = input.closest(".auth-form") || document;
    const bar = container.querySelector("[data-strength-bar]");
    const label = container.querySelector("[data-strength-label]");
    const fill = bar?.querySelector("span");

    if (!bar || !label || !fill) return;

    const updateStrength = () => {
      const password = input.value;
      const hasSpecial = /[^\p{L}\p{N}]/u.test(password);
      const hasLettersAndNumbers = /\p{L}/u.test(password) && /\p{N}/u.test(password);
      let strength;
      let message;

      if (password.length < 8) {
        strength = "weak";
        message = "Débil — usá al menos 8 caracteres.";
      } else if (hasSpecial || (password.length >= 12 && hasLettersAndNumbers)) {
        strength = "strong";
        message = "Fuerte";
      } else {
        strength = "medium";
        message = "Media — podés sumar longitud o caracteres especiales.";
      }

      const levels = { weak: 1, medium: 2, strong: 3 };
      bar.setAttribute("aria-valuenow", levels[strength]);
      bar.classList.remove("is-medium", "is-strong");
      label.classList.remove("is-weak", "is-medium", "is-strong");
      if (strength !== "weak") bar.classList.add(`is-${strength}`);
      label.classList.add(`is-${strength}`);
      fill.style.width = `${(levels[strength] / 3) * 100}%`;
      label.textContent = message;
    };

    input.addEventListener("input", updateStrength);
    updateStrength();
  });
});
