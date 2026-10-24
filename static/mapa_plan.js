/* ==========================================================================
   Mapa del plan confirmado (plan_detalle.html)

   Muestra el lugar del plan y a cada asistente que decidió compartir su ubicación, con la distancia en línea
   recta al lugar. Compartir es opcional y se puede cortar en cualquier momento; mientras está activo, la
   ubicación se manda cada ~20 segundos con la página abierta. El servidor solo le entrega el mapa a quienes
   van al plan, hasta que el plan termina (routes/planes.py, services/plan_ubicacion_service.py).
   ========================================================================== */

(function () {

  "use strict";

  var raiz = document.querySelector("[data-mapa-plan]");

  if (!raiz || !window.L) {
    return;
  }

  var planId = raiz.dataset.planId;
  var lienzo = raiz.querySelector("[data-mapa-lienzo]");
  var boton = raiz.querySelector("[data-mapa-compartir]");
  var botonDetener = raiz.querySelector("[data-mapa-detener]");
  var estado = raiz.querySelector("[data-mapa-estado]");
  var lista = raiz.querySelector("[data-mapa-personas]");

  var CADA_MS = 20000;
  var RECARGA_MS = 15000;

  // Sin el logo ni el prefijo de Leaflet; queda solo el crédito de los datos, que los proveedores piden y va en letra mínima.
  var mapa = L.map(lienzo, { scrollWheelZoom: false, attributionControl: false, zoomControl: false });
  L.control.attribution({ prefix: false, position: "bottomright" }).addTo(mapa);
  L.control.zoom({ position: "topright", zoomInText: "+", zoomOutText: "−" }).addTo(mapa);

  // Base de OpenStreetMap (gratuita, sin clave). El estilo sobrio (gris, y oscuro en modo noche) lo da el CSS.
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>'
  }).addTo(mapa);

  mapa.setView([-34.9011, -56.1645], 12);

  var marcadoresLugares = [];
  var marcadoresPersonas = {};
  var ultimoConteo = -1;
  var comparte = false;
  var vigilando = null;
  var ultimoEnvio = 0;

  function kilometros(km) {
    if (km == null) { return ""; }
    if (km < 1) { return "a " + (Math.max(1, Math.round(km * 100)) * 10) + " m del lugar"; }
    if (km < 10) { return "a " + km.toFixed(1).replace(".", ",") + " km del lugar"; }
    return "a " + Math.round(km) + " km del lugar";
  }

  function hace(segundos) {
    if (segundos < 90) { return "ahora"; }
    var minutos = Math.round(segundos / 60);
    if (minutos < 60) { return "hace " + minutos + " min"; }
    return "hace " + Math.round(minutos / 60) + " h";
  }

  function iconoLugar() {
    return L.divIcon({ className: "mapa-pin", html: "<span></span>", iconSize: [18, 18], iconAnchor: [9, 9] });
  }

  function iconoPersona(persona) {
    var clase = "mapa-persona" + (persona.yo ? " is-yo" : "") + (persona.vieja ? " is-vieja" : "");
    return L.divIcon({
      className: clase,
      html: "<span>" + (persona.nombre || "?").charAt(0).toUpperCase() + "</span>",
      iconSize: [26, 26],
      iconAnchor: [13, 13]
    });
  }

  function limpiarHijos(nodo) {
    while (nodo.firstChild) { nodo.removeChild(nodo.firstChild); }
  }

  function pintarLista(personas) {

    limpiarHijos(lista);

    personas.forEach(function (persona) {

      var item = document.createElement("li");
      item.className = "mapa-plan__persona" + (persona.comparte ? "" : " is-sin");

      var cara = document.createElement("span");
      cara.className = "avatar";
      cara.style.setProperty("--size", "32px");
      cara.style.setProperty("--h", String(((persona.nombre || "").length * 47) % 360));
      cara.textContent = (persona.nombre || "?").charAt(0).toUpperCase();

      var cuerpo = document.createElement("span");
      cuerpo.className = "mapa-plan__persona-texto";

      var nombre = document.createElement("strong");
      nombre.textContent = persona.yo ? "Vos" : persona.nombre;

      var detalle = document.createElement("small");

      if (persona.comparte) {
        var partes = [kilometros(persona.km), hace(persona.hace_segundos)].filter(Boolean);
        detalle.textContent = partes.join(" · ");
      } else {
        detalle.textContent = "No comparte su ubicación";
      }

      cuerpo.appendChild(nombre);
      cuerpo.appendChild(detalle);
      item.appendChild(cara);
      item.appendChild(cuerpo);
      lista.appendChild(item);
    });
  }

  function pintarMapa(datos) {

    marcadoresLugares.forEach(function (m) { mapa.removeLayer(m); });
    marcadoresLugares = datos.lugares.map(function (lugar) {
      return L.marker([lugar.lat, lugar.lon], { icon: iconoLugar(), title: lugar.nombre, keyboard: false })
        .bindTooltip(lugar.nombre, { direction: "top", offset: [0, -8], className: "mapa-etiqueta" })
        .addTo(mapa);
    });

    var vigentes = {};

    datos.personas.forEach(function (persona) {

      if (!persona.comparte) { return; }

      vigentes[persona.id] = true;
      var posicion = [persona.lat, persona.lon];
      var existente = marcadoresPersonas[persona.id];

      if (existente) {
        existente.setLatLng(posicion).setIcon(iconoPersona(persona));
      } else {
        marcadoresPersonas[persona.id] = L.marker(posicion, { icon: iconoPersona(persona), keyboard: false }).addTo(mapa);
      }

      marcadoresPersonas[persona.id].bindTooltip(persona.yo ? "Vos" : persona.nombre, { direction: "top", offset: [0, -10], className: "mapa-etiqueta" });
    });

    Object.keys(marcadoresPersonas).forEach(function (id) {
      if (!vigentes[id]) {
        mapa.removeLayer(marcadoresPersonas[id]);
        delete marcadoresPersonas[id];
      }
    });

    // Se encuadra todo cuando aparece o desaparece alguien (no en cada actualización, para no mover el mapa mientras lo mirás).
    var conteo = marcadoresLugares.length + Object.keys(marcadoresPersonas).length;

    if (conteo !== ultimoConteo) {
      ultimoConteo = conteo;
      var todos = marcadoresLugares.concat(Object.keys(marcadoresPersonas).map(function (id) { return marcadoresPersonas[id]; }));
      if (todos.length === 1) {
        mapa.setView(todos[0].getLatLng(), 15);
      } else if (todos.length > 1) {
        mapa.fitBounds(L.featureGroup(todos).getBounds().pad(0.25), { maxZoom: 16 });
      }
    }
  }

  function avisar(texto) {
    estado.textContent = texto || "";
  }

  function textoBoton() {
    // Compartiendo y vigilando: solo "Dejar de compartir". Compartida pero en pausa: "Retomar" o "Dejar de compartir".
    var activa = comparte && vigilando !== null;
    boton.hidden = activa;
    boton.textContent = comparte ? "Retomar mi ubicación" : "Compartir mi ubicación";
    botonDetener.hidden = !comparte;
  }

  function cargar() {

    return fetch("/planes/" + planId + "/mapa", { credentials: "same-origin", cache: "no-store" })
      .then(function (respuesta) {
        if (respuesta.status === 403 || respuesta.status === 404) {
          raiz.hidden = true;
          return null;
        }
        return respuesta.ok ? respuesta.json() : null;
      })
      .then(function (datos) {

        if (!datos || !datos.ok) { return; }

        pintarMapa(datos);
        pintarLista(datos.personas);

        if (vigilando === null && datos.yo_comparto !== comparte) {
          comparte = datos.yo_comparto;
          textoBoton();
          // Si ya estaba compartiendo (otra vez que abrió la página), se retoma sola cuando el navegador ya tiene el permiso.
          if (comparte && !vigilando) { retomar(); }
        }
      })
      .catch(function () { /* sin conexión por un rato: se reintenta */ });
  }

  function enviar(posicion) {

    var ahora = Date.now();

    if (ahora - ultimoEnvio < CADA_MS) { return; }

    ultimoEnvio = ahora;

    fetch("/planes/" + planId + "/ubicacion", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat: posicion.coords.latitude, lon: posicion.coords.longitude })
    })
      .then(function (respuesta) { return respuesta.json().catch(function () { return {}; }); })
      .then(function (datos) {
        if (datos && datos.ok) {
          avisar("Compartiendo tu ubicación. Se actualiza mientras tengas esta página abierta.");
          cargar();
        } else {
          avisar((datos && datos.error) || "No se pudo guardar tu ubicación.");
        }
      })
      .catch(function () { avisar("No se pudo guardar tu ubicación."); });
  }

  function empezar() {

    if (!navigator.geolocation) {
      avisar("Tu navegador no permite compartir la ubicación.");
      return;
    }

    avisar("Pidiendo tu ubicación…");

    vigilando = navigator.geolocation.watchPosition(enviar, function (error) {
      vigilando = null;
      comparte = false;
      textoBoton();
      avisar(error && error.code === 1 ? "No diste permiso de ubicación en el navegador." : "No pudimos ubicarte ahora.");
    }, { enableHighAccuracy: true, maximumAge: 10000, timeout: 20000 });

    comparte = true;
    textoBoton();
  }

  function retomar() {

    if (!navigator.permissions) { avisar("Tocá el botón para retomar tu ubicación."); return; }

    navigator.permissions.query({ name: "geolocation" }).then(function (permiso) {
      if (permiso.state === "granted") {
        empezar();
      } else {
        avisar("Tu ubicación sigue compartida, pero está pausada. Tocá el botón para retomarla o dejar de compartir.");
      }
    }).catch(function () { avisar("Tocá el botón para retomar tu ubicación."); });
  }

  function detener() {

    if (vigilando !== null) {
      navigator.geolocation.clearWatch(vigilando);
      vigilando = null;
    }

    comparte = false;
    textoBoton();
    avisar("Dejaste de compartir tu ubicación.");

    fetch("/planes/" + planId + "/ubicacion/detener", { method: "POST", credentials: "same-origin" })
      .then(cargar)
      .catch(function () { /* se borra igual cuando el plan termina */ });
  }

  boton.addEventListener("click", empezar);
  botonDetener.addEventListener("click", detener);

  textoBoton();
  cargar();
  setInterval(function () { if (!document.hidden) { cargar(); } }, RECARGA_MS);

  // El mapa se arma con el contenedor visible; si llegaron por el enlace "Ver mapa" hay que recalcular el tamaño.
  setTimeout(function () { mapa.invalidateSize(); }, 300);

}());
