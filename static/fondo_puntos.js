/* ==========================================================================
   Puntos del fondo que se prenden y apagan, despacio.

   La grilla de puntos es CSS (.landing-fondo::before y .dashboard-main::before, paso de 22 px). Acá se agrega encima una capa con
   unos pocos puntos de esa misma grilla, un poco más marcados, que aparecen y desaparecen con calma.

   Se aplica a:
     - la landing, desde la segunda sección  ([data-fondo-brillos=".landing-demo"])
     - todo el dashboard                     (.dashboard-main, se marca solo)

   Con "reducir movimiento" no se agrega nada.
   ========================================================================== */

(function () {

  "use strict";

  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) { return; }

  var PASO = 22;            // el mismo paso que la grilla de puntos del CSS
  var DENSIDAD = 0.03;      // fracción de los puntos que brillan


  function montar(host, selectorDesde) {

    var capa = document.createElement("div");
    capa.className = "fondo-brillos";
    capa.setAttribute("aria-hidden", "true");
    host.appendChild(capa);

    var ultimoAncho = -1;
    var ultimoAlto = -1;

    function pintar() {

      var desde = selectorDesde ? host.querySelector(selectorDesde) : null;
      var arriba = desde ? desde.getBoundingClientRect().top - host.getBoundingClientRect().top : 0;
      var ancho = host.clientWidth;
      var alto = host.clientHeight - arriba;

      if (alto < PASO * 2 || ancho < PASO * 2) { return; }

      ultimoAncho = host.clientWidth;
      ultimoAlto = host.clientHeight;

      capa.style.top = arriba + "px";
      capa.style.height = alto + "px";
      capa.textContent = "";

      var columnas = Math.floor(ancho / PASO);
      var filas = Math.floor(alto / PASO);
      var cantidad = Math.round(columnas * filas * DENSIDAD);
      var usados = {};
      var fragmento = document.createDocumentFragment();

      for (var n = 0; n < cantidad; n++) {
        var c = Math.floor(Math.random() * columnas);
        var f = Math.floor(Math.random() * filas);
        if (usados[c + "," + f]) { continue; }
        usados[c + "," + f] = true;
        var punto = document.createElement("i");
        punto.style.left = c * PASO + "px";
        punto.style.top = f * PASO + "px";
        punto.style.setProperty("--b-t", (7 + Math.random() * 9).toFixed(1) + "s");
        punto.style.setProperty("--b-d", "-" + (Math.random() * 16).toFixed(1) + "s");
        fragmento.appendChild(punto);
      }

      capa.appendChild(fragmento);
    }

    pintar();

    // Si la página cambia de tamaño (ventana, contenido que carga), se vuelven a repartir los puntos.
    var pendiente = 0;
    function revisar() {
      window.clearTimeout(pendiente);
      pendiente = window.setTimeout(function () {
        if (Math.abs(host.clientWidth - ultimoAncho) > 8 || Math.abs(host.clientHeight - ultimoAlto) > 120) { pintar(); }
      }, 300);
    }

    if ("ResizeObserver" in window) {
      new ResizeObserver(revisar).observe(host);
    } else {
      window.addEventListener("resize", revisar);
    }
  }


  function iniciar() {

    Array.prototype.forEach.call(document.querySelectorAll("[data-fondo-brillos]"), function (host) {
      montar(host, host.getAttribute("data-fondo-brillos") || "");
    });

    var principal = document.querySelector(".dashboard-main");
    if (principal && !principal.hasAttribute("data-fondo-brillos")) { montar(principal, ""); }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }

}());
