/* Moderación de Social: descartar un reporte o eliminar lo reportado. */

(() => {
  const raiz = document.getElementById("moderacion");
  if (!raiz) return;

  const lista = raiz.querySelector("[data-mod-lista]");
  const vacio = raiz.querySelector("[data-mod-vacio]");
  const error = raiz.querySelector("[data-mod-error]");

  const resolver = async (item, accion) => {
    const pregunta = accion === "eliminar"
      ? "¿Eliminar este contenido? Deja de verse para todos."
      : "¿Descartar el reporte? El contenido queda como está.";
    if (!(await window.preguntar(pregunta))) return;

    error.hidden = true;

    try {
      const respuesta = await fetch(raiz.dataset.urlResolver, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tipo: item.dataset.tipo, id: item.dataset.id, accion }),
      });
      const datos = await respuesta.json().catch(() => ({}));
      if (!respuesta.ok) throw new Error(datos.error || "Algo salió mal. Intentá de nuevo.");

      item.remove();
      vacio.hidden = lista.children.length > 0;
    } catch (e) {
      error.textContent = e.message;
      error.hidden = false;
    }
  };

  lista.addEventListener("click", (evento) => {
    const boton = evento.target.closest("[data-mod-accion]");
    if (boton) resolver(boton.closest(".mod-item"), boton.dataset.modAccion);
  });
})();
