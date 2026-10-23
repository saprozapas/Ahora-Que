/* ==========================================================================
   Distancia al lugar del plan

   Cada <span data-dist data-lat data-lon> muestra "a 1,2 km" desde donde está quien mira. La ubicación sale
   del navegador (nunca viaja al servidor) y solo se pide cuando la persona lo toca: "¿A cuánto queda?".
   Si ya la dio antes, se completa sola. Es distancia en línea recta, no recorrido.
   ========================================================================== */

(function () {

  "use strict";

  var CLAVE = "aq-ubicacion";
  var VIGENCIA_MS = 10 * 60 * 1000;
  var posicion = leer();
  var negada = false;
  var pidiendo = false;

  function leer() {
    try {
      var guardada = JSON.parse(sessionStorage.getItem(CLAVE));
      if (guardada && Date.now() - guardada.t < VIGENCIA_MS) {
        return guardada;
      }
    } catch (error) { /* sin sessionStorage: se pide cada vez */ }
    return null;
  }

  function guardar() {
    try {
      sessionStorage.setItem(CLAVE, JSON.stringify(posicion));
    } catch (error) { /* no pasa nada */ }
  }

  function kilometros(lat1, lon1, lat2, lon2) {
    var radio = Math.PI / 180;
    var a = Math.sin((lat2 - lat1) * radio / 2) ** 2
      + Math.cos(lat1 * radio) * Math.cos(lat2 * radio) * Math.sin((lon2 - lon1) * radio / 2) ** 2;
    return 6371 * 2 * Math.asin(Math.sqrt(a));
  }

  function formatear(km) {
    if (km < 1) {
      return "a " + (Math.max(1, Math.round(km * 100)) * 10) + " m";
    }
    if (km < 10) {
      return "a " + km.toFixed(1).replace(".", ",") + " km";
    }
    return "a " + Math.round(km) + " km";
  }

  function pintar(elemento) {

    var lat = parseFloat(elemento.dataset.lat);
    var lon = parseFloat(elemento.dataset.lon);

    if (isNaN(lat) || isNaN(lon)) {
      return;
    }

    if (posicion) {
      elemento.textContent = formatear(kilometros(posicion.lat, posicion.lon, lat, lon));
      elemento.title = "En línea recta desde tu ubicación";
      elemento.classList.add("is-lista");
      return;
    }

    elemento.classList.remove("is-lista");
    elemento.removeAttribute("title");

    if (negada) {
      elemento.textContent = "";
      return;
    }

    if (!elemento.querySelector(".dist__pedir")) {
      var boton = document.createElement("button");
      boton.type = "button";
      boton.className = "dist__pedir";
      boton.textContent = pidiendo ? "Ubicándote…" : "¿A cuánto queda?";
      elemento.textContent = "";
      elemento.appendChild(boton);
    }
  }

  function actualizar() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-dist]"), pintar);
  }

  function pedir() {

    if (pidiendo || !navigator.geolocation) {
      negada = !navigator.geolocation;
      actualizar();
      return;
    }

    pidiendo = true;
    actualizar();

    navigator.geolocation.getCurrentPosition(function (resultado) {
      posicion = { lat: resultado.coords.latitude, lon: resultado.coords.longitude, t: Date.now() };
      pidiendo = false;
      guardar();
      actualizar();
    }, function () {
      pidiendo = false;
      negada = true;
      actualizar();
    }, { enableHighAccuracy: false, maximumAge: 5 * 60 * 1000, timeout: 10000 });
  }

  document.addEventListener("click", function (evento) {
    if (evento.target.closest(".dist__pedir")) {
      evento.preventDefault();
      pedir();
    }
  });

  window.AQDistancia = { actualizar: actualizar };

  function iniciar() {

    actualizar();

    // Si ya dio el permiso en otra pantalla, no hace falta volver a preguntar.
    if (!posicion && navigator.permissions && document.querySelector("[data-dist]")) {
      navigator.permissions.query({ name: "geolocation" }).then(function (permiso) {
        if (permiso.state === "granted") {
          pedir();
        } else if (permiso.state === "denied") {
          negada = true;
          actualizar();
        }
      }).catch(function () { /* navegadores sin Permissions API: queda el botón */ });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }

}());
