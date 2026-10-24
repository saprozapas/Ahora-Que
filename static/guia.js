/* ==========================================================================
   Guía de primera vez

   1. Globos de ayuda: cada elemento con data-guia-id (y data-guia-titulo / data-guia-texto / data-guia-orden)
      muestra, la primera vez que se ve, un globo corto que dice para qué sirve. Se avanza con "Siguiente";
      "Omitir" cierra todos. Lo ya visto se recuerda en este navegador (localStorage).
   2. "Primeros pasos" del Inicio: la tarjeta se puede ocultar y el navegador se acuerda.
   3. Cualquier botón con data-guia-reiniciar vuelve a mostrar los globos.
   ========================================================================== */

(function () {

  "use strict";

  var CLAVE_VISTOS = "aq-guia-vistos";
  var CLAVE_OFF = "aq-guia-omitida";
  var CLAVE_PASOS = "aq-primeros-ocultos";

  function leer(clave) {
    try { return window.localStorage.getItem(clave); } catch (e) { return null; }
  }

  function guardar(clave, valor) {
    try { window.localStorage.setItem(clave, valor); } catch (e) { /* sin almacenamiento: se muestra cada vez */ }
  }

  function borrar(clave) {
    try { window.localStorage.removeItem(clave); } catch (e) { /* nada */ }
  }

  function vistos() {
    try { return JSON.parse(leer(CLAVE_VISTOS)) || []; } catch (e) { return []; }
  }

  function marcarVisto(id) {
    var lista = vistos();
    if (lista.indexOf(id) === -1) { lista.push(id); }
    guardar(CLAVE_VISTOS, JSON.stringify(lista));
  }

  // ---------------------------------------------------------------- Primeros pasos
  var pasos = document.querySelector("[data-primeros]");

  if (pasos) {
    if (leer(CLAVE_PASOS) !== "1") { pasos.hidden = false; }
    var cerrar = pasos.querySelector("[data-primeros-cerrar]");
    if (cerrar) {
      cerrar.addEventListener("click", function () {
        guardar(CLAVE_PASOS, "1");
        pasos.hidden = true;
      });
    }
  }

  // ---------------------------------------------------------------- Reiniciar
  document.addEventListener("click", function (evento) {
    var boton = evento.target.closest("[data-guia-reiniciar]");
    if (!boton) { return; }
    borrar(CLAVE_VISTOS);
    borrar(CLAVE_OFF);
    borrar(CLAVE_PASOS);
    window.location.href = "/dashboard";
  });

  // ---------------------------------------------------------------- Globos
  if (leer(CLAVE_OFF) === "1") { return; }

  var globo = null;
  var cola = [];
  var indice = 0;
  var activo = null;

  function visible(el) {
    var caja = el.getBoundingClientRect();
    return el.offsetParent !== null && caja.width > 0 && caja.height > 0 && !el.closest("[hidden]") && !el.closest("dialog:not([open])");
  }

  function armarCola() {
    var ya = vistos();
    cola = Array.prototype.slice.call(document.querySelectorAll("[data-guia-id]"))
      .filter(function (el) { return ya.indexOf(el.dataset.guiaId) === -1 && visible(el); })
      .sort(function (a, b) { return (Number(a.dataset.guiaOrden) || 99) - (Number(b.dataset.guiaOrden) || 99); });
  }

  function cerrarTodo(omitir) {
    if (activo) { activo.classList.remove("guia-resaltado"); activo = null; }
    if (globo) { globo.remove(); globo = null; }
    if (omitir) { guardar(CLAVE_OFF, "1"); }
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

    cerrarTodo(false);

    if (indice >= cola.length) { return; }

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
    omitir.addEventListener("click", function () { cerrarTodo(true); });

    var siguiente = document.createElement("button");
    siguiente.type = "button";
    siguiente.className = "guia-globo__ok";
    siguiente.textContent = indice === cola.length - 1 ? "Entendido" : "Siguiente";
    siguiente.addEventListener("click", function () {
      marcarVisto(activo.dataset.guiaId);
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
    if (evento.key === "Escape" && globo) { cerrarTodo(true); }
  });

  // Un momento después de cargar, para que la página termine de acomodarse y de traer lo que pide por su cuenta.
  setTimeout(function () {
    armarCola();
    if (cola.length && !document.querySelector("dialog[open]")) { mostrar(); }
  }, 1100);

}());
