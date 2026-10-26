/* ==========================================================================
   Guía de bienvenida (solo para cuentas nuevas)

   El servidor solo carga este archivo en el navegador donde se creó la cuenta, mientras la guía no se haya
   terminado (base.html, variable guia_nueva). Dura una sola vez:

   1. En el Inicio, globos cortos que apuntan a lo principal (cada elemento con data-guia-id,
      data-guia-titulo, data-guia-texto y data-guia-orden). "Siguiente" avanza; "Entendido" en el último
      o "Omitir" en cualquiera la terminan.
   2. La tarjeta "Primeros pasos" del Inicio forma parte de la guía: se oculta al terminarla.
   Al terminar, el navegador le avisa al servidor (POST /guia/terminada) y no vuelve a aparecer.
   ========================================================================== */

(function () {

  "use strict";

  // La guía vive en el Inicio: en otras pantallas no hace nada.
  if (window.location.pathname.replace(/\/$/, "") !== "/dashboard") { return; }

  var pasos = document.querySelector("[data-primeros]");
  var globo = null;
  var cola = [];
  var indice = 0;
  var activo = null;
  var terminada = false;

  if (pasos) {
    pasos.hidden = false;
    var cerrar = pasos.querySelector("[data-primeros-cerrar]");
    if (cerrar) { cerrar.addEventListener("click", terminar); }
  }

  function terminar() {

    if (terminada) { return; }
    terminada = true;

    cerrarGlobo();
    if (pasos) { pasos.hidden = true; }

    try {
      fetch("/guia/terminada", { method: "POST", credentials: "same-origin" });
    } catch (e) { /* si no llega, se vuelve a ofrecer en la próxima visita */ }
  }

  function visible(el) {
    var caja = el.getBoundingClientRect();
    return el.offsetParent !== null && caja.width > 0 && caja.height > 0 && !el.closest("[hidden]") && !el.closest("dialog:not([open])");
  }

  function armarCola() {
    cola = Array.prototype.slice.call(document.querySelectorAll("[data-guia-id]"))
      .filter(visible)
      .sort(function (a, b) { return (Number(a.dataset.guiaOrden) || 99) - (Number(b.dataset.guiaOrden) || 99); });
  }

  function cerrarGlobo() {
    if (activo) { activo.classList.remove("guia-resaltado"); activo = null; }
    if (globo) { globo.remove(); globo = null; }
  }

  function colocar() {

    if (!globo || !activo) { return; }

    var objetivo = activo.getBoundingClientRect();
    var ancho = globo.offsetWidth;
    var alto = globo.offsetHeight;
    var margen = 12;

    var abajo = objetivo.bottom + margen + alto <= window.innerHeight - 8;
    var arriba = objetivo.top - margen - alto >= 8;
    var lado = abajo || !arriba ? "abajo" : "arriba";
    var y = lado === "abajo" ? objetivo.bottom + margen : objetivo.top - margen - alto;
    y = Math.max(8, Math.min(window.innerHeight - alto - 8, y));

    var x = objetivo.left + objetivo.width / 2 - ancho / 2;
    x = Math.max(12, Math.min(window.innerWidth - ancho - 12, x));

    globo.style.left = x + "px";
    globo.style.top = y + "px";
    globo.dataset.lado = lado;

    var flecha = objetivo.left + objetivo.width / 2 - x;
    globo.style.setProperty("--flecha", Math.max(18, Math.min(ancho - 18, flecha)) + "px");
  }

  function mostrar() {

    cerrarGlobo();

    if (indice >= cola.length) { terminar(); return; }

    activo = cola[indice];
    activo.classList.add("guia-resaltado");
    activo.scrollIntoView({ block: "nearest", behavior: "smooth" });

    globo = document.createElement("div");
    globo.className = "guia-globo";
    globo.setAttribute("role", "dialog");
    globo.setAttribute("aria-label", "Ayuda");

    var titulo = document.createElement("strong");
    titulo.textContent = activo.dataset.guiaTitulo || "Ayuda";

    var texto = document.createElement("p");
    texto.textContent = activo.dataset.guiaTexto || "";

    var pie = document.createElement("div");
    pie.className = "guia-globo__pie";

    var contador = document.createElement("span");
    contador.textContent = cola.length > 1 ? (indice + 1) + " de " + cola.length : "";

    var omitir = document.createElement("button");
    omitir.type = "button";
    omitir.className = "guia-globo__omitir";
    omitir.textContent = "Omitir";
    omitir.addEventListener("click", terminar);

    var siguiente = document.createElement("button");
    siguiente.type = "button";
    siguiente.className = "guia-globo__ok";
    siguiente.textContent = indice === cola.length - 1 ? "Entendido" : "Siguiente";
    siguiente.addEventListener("click", function () {
      indice += 1;
      mostrar();
    });

    pie.appendChild(contador);
    pie.appendChild(omitir);
    pie.appendChild(siguiente);
    globo.appendChild(titulo);
    globo.appendChild(texto);
    globo.appendChild(pie);
    document.body.appendChild(globo);

    colocar();
    setTimeout(colocar, 350);  // después del scroll suave
    siguiente.focus({ preventScroll: true });
  }

  window.addEventListener("resize", colocar);
  window.addEventListener("scroll", colocar, true);
  document.addEventListener("keydown", function (evento) {
    if (evento.key === "Escape" && globo) { terminar(); }
  });

  // Un momento después de cargar, para que la página termine de acomodarse y de traer lo que pide por su cuenta.
  setTimeout(function () {
    armarCola();
    if (cola.length && !document.querySelector("dialog[open]")) { mostrar(); }
  }, 1100);

}());
