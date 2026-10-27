/* ==========================================================================
   Landing (home pública)

   1. Aparición: los bloques de la página entran con un fundido suave a medida que se scrollea.
   2. Tipeo: la respuesta del asistente en la demo se escribe sola, como si la IA estuviera respondiendo.

   Sin JavaScript (o con "reducir movimiento") todo se ve completo y quieto.
   ========================================================================== */

(function () {

  "use strict";

  var reducir = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var hayObservador = "IntersectionObserver" in window;

  if (reducir || !hayObservador) { return; }


  // ---- 1. Aparición al scrollear ------------------------------------------------------------------------------

  // [selector, pausa entre hermanos en ms]: los elementos de una misma tanda entran uno después del otro.
  var BLOQUES = [
    [".landing-demo__intro", 0],
    [".landing-demo .window", 0],
    [".landing-demo__filters", 0],
    [".landing-demo__group", 0],
    [".landing-demo__cards .plan-tile", 160],
    [".landing-steps .landing-split > div:first-child", 0],
    [".landing-steps__list > li", 200],
    [".landing-faq h2", 0],
    [".faq__item", 120]
  ];

  var observador = new IntersectionObserver(function (entradas) {
    entradas.forEach(function (entrada) {
      if (!entrada.isIntersecting) { return; }
      entrada.target.classList.add("is-visible");
      observador.unobserve(entrada.target);
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });

  BLOQUES.forEach(function (bloque) {
    Array.prototype.forEach.call(document.querySelectorAll(bloque[0]), function (el, i) {
      el.setAttribute("data-reveal", "");
      el.style.setProperty("--rev-d", i * bloque[1] + "ms");
      observador.observe(el);
    });
  });

  document.documentElement.classList.add("reveal-on");


  // ---- 2. Puntos del fondo que se prenden y apagan (desde la segunda sección) ----------------------------------------

  var fondo = document.querySelector("[data-landing-fondo]");
  var segunda = document.querySelector(".landing-demo");

  if (fondo && segunda) {

    var PASO = 22;           // el mismo paso que la grilla de puntos del CSS
    var capa = document.createElement("div");
    capa.className = "fondo-brillos";
    capa.setAttribute("aria-hidden", "true");
    fondo.appendChild(capa);

    var pintarBrillos = function () {
      var arriba = segunda.getBoundingClientRect().top - fondo.getBoundingClientRect().top;
      var ancho = fondo.clientWidth;
      var alto = fondo.clientHeight - arriba;
      capa.style.top = arriba + "px";
      capa.style.height = alto + "px";
      capa.textContent = "";
      var columnas = Math.floor(ancho / PASO);
      var filas = Math.floor(alto / PASO);
      var cantidad = Math.round(columnas * filas * 0.035);
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
    };

    pintarBrillos();

    var ultimoAncho = fondo.clientWidth;
    var pendiente = 0;
    window.addEventListener("resize", function () {
      window.clearTimeout(pendiente);
      pendiente = window.setTimeout(function () {
        if (fondo.clientWidth !== ultimoAncho) {
          ultimoAncho = fondo.clientWidth;
          pintarBrillos();
        }
      }, 250);
    });
  }


  // ---- 3. Tipeo de la respuesta del asistente -----------------------------------------------------------------

  var voz = document.querySelector(".landing-demo__brief .voice");
  var boton = document.querySelector(".landing-demo__brief .btn");

  if (!voz) { return; }

  var fuerte = voz.querySelector("strong");
  var textoFuerte = fuerte ? fuerte.textContent.trim() : "";
  var textoResto = voz.textContent.replace(textoFuerte, "").replace(/\s+/g, " ").trim();
  var textoTotal = (textoFuerte + " " + textoResto).trim();

  // Se reserva el alto que va a tener la frase completa para que la página no salte mientras se escribe.
  voz.style.minHeight = voz.offsetHeight + "px";
  voz.setAttribute("aria-label", textoTotal);
  voz.textContent = "";

  var tramoFuerte = document.createElement("strong");
  var tramoResto = document.createElement("span");
  var cursor = document.createElement("span");
  var pensando = document.createElement("span");

  tramoFuerte.setAttribute("aria-hidden", "true");
  tramoResto.setAttribute("aria-hidden", "true");
  cursor.className = "tipeo-cursor";
  cursor.setAttribute("aria-hidden", "true");
  pensando.className = "tipeo-pensando";
  pensando.setAttribute("aria-hidden", "true");
  pensando.innerHTML = "<i></i><i></i><i></i>";

  voz.appendChild(tramoFuerte);
  voz.appendChild(tramoResto);
  voz.appendChild(pensando);

  if (boton) { boton.classList.add("tipeo-pendiente"); }

  function pausaPara(caracter) {
    if (".!?".indexOf(caracter) !== -1) { return 200; }
    if (",;:".indexOf(caracter) !== -1) { return 90; }
    return 0;
  }

  function escribir(texto, destino, alTerminar) {
    var i = 0;
    (function siguiente() {
      if (i >= texto.length) { alTerminar(); return; }
      var c = texto.charAt(i++);
      destino.textContent += c;
      window.setTimeout(siguiente, 14 + Math.random() * 18 + pausaPara(c));
    }());
  }

  function empezar() {
    // 1) "pensando…" un momento, 2) la frase fuerte, 3) el resto, 4) aparece el botón.
    window.setTimeout(function () {
      pensando.remove();
      voz.insertBefore(cursor, tramoResto.nextSibling);
      escribir(textoFuerte, tramoFuerte, function () {
        window.setTimeout(function () {
          tramoResto.textContent = " ";
          escribir(textoResto, tramoResto, function () {
            if (boton) { boton.classList.remove("tipeo-pendiente"); }
            window.setTimeout(function () { cursor.classList.add("is-apagado"); }, 2600);
          });
        }, 280);
      });
    }, 800);
  }

  var arranque = new IntersectionObserver(function (entradas) {
    if (!entradas.some(function (e) { return e.isIntersecting; })) { return; }
    arranque.disconnect();
    empezar();
  }, { threshold: 0.7 });

  arranque.observe(voz);

}());
