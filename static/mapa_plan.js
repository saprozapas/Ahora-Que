/* ==========================================================================
   Mapa del plan confirmado (plan_detalle.html)

   Muestra el lugar del plan y a cada asistente que decidió compartir su ubicación, con la distancia en línea
   recta al lugar. Compartir es opcional y se puede cortar en cualquier momento; mientras está activo, la
   ubicación se manda cada ~20 segundos con la página abierta. El servidor solo le entrega el mapa a quienes
   van al plan, hasta que el plan termina (routes/planes.py, services/plan_ubicacion_service.py).

   El mapa es plano y sobrio: base vectorial de OpenFreeMap (gratuita, sin clave) a la que se le sacan
   edificios, parques, usos del suelo y puntos de interés; quedan el agua, las calles y sus nombres.
   En modo noche el CSS lo invierte.
   ========================================================================== */

(function () {

  "use strict";

  var raiz = document.querySelector("[data-mapa-plan]");

  if (!raiz || !window.maplibregl) {
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
  // De la base solo se dejan estas capas de datos: agua, calles y los nombres de calles, barrios y agua.
  var CAPAS_QUE_QUEDAN = ["water", "waterway", "transportation", "transportation_name", "place", "water_name"];
  // Y de esas, sin vías de tren, escudos de ruta ni fronteras.
  var CAPAS_QUE_SE_VAN = /^(railway|highway-shield|road_shield|airport|boundary|label_country|label_state)/;

  var mapa = new maplibregl.Map({
    container: lienzo,
    style: "https://tiles.openfreemap.org/styles/positron",
    center: [-56.1645, -34.9011],
    zoom: 12,
    attributionControl: false,
    dragRotate: false,
    pitchWithRotate: false,
    touchPitch: false,
    scrollZoom: false,
    maxPitch: 0
  });

  mapa.touchZoomRotate.disableRotation();
  mapa.addControl(new maplibregl.NavigationControl({ showCompass: false, visualizePitch: false }), "top-right");
  mapa.addControl(new maplibregl.AttributionControl({ compact: false }), "bottom-right");

  // Al cargar el estilo se sacan las capas que cargan el mapa (edificios, parques, comercios).
  mapa.on("style.load", function () {
    mapa.getStyle().layers.slice().forEach(function (capa) {
      if (capa.type === "background") { return; }
      var fuente = capa["source-layer"];
      if (!fuente || CAPAS_QUE_QUEDAN.indexOf(fuente) === -1 || CAPAS_QUE_SE_VAN.test(capa.id)) {
        mapa.removeLayer(capa.id);
      }
    });
  });

  // Líneas punteadas de cada persona al primer lugar del plan, con la distancia encima.
  var lineas = { type: "FeatureCollection", features: [] };
  var etiquetasKm = [];

  mapa.on("load", function () {
    mapa.addSource("lineas", { type: "geojson", data: lineas });
    mapa.addLayer({
      id: "lineas",
      type: "line",
      source: "lineas",
      layout: { "line-cap": "round" },
      // Gris oscuro: en modo noche el CSS invierte el mapa y la línea queda clara.
      paint: { "line-color": "#4a4f57", "line-width": 1.6, "line-dasharray": [1.5, 2.5], "line-opacity": 0.85 }
    });
  });

  function textoKm(km) {
    if (km < 1) { return (Math.max(1, Math.round(km * 100)) * 10) + " m"; }
    if (km < 10) { return km.toFixed(1).replace(".", ",") + " km"; }
    return Math.round(km) + " km";
  }

  function pintarLineas(datos) {

    etiquetasKm.forEach(function (m) { m.remove(); });
    etiquetasKm = [];

    var destino = datos.lugares[0];
    var rasgos = [];

    if (destino) {
      datos.personas.forEach(function (persona) {
        if (!persona.comparte) { return; }
        rasgos.push({ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: [[persona.lon, persona.lat], [destino.lon, destino.lat]] } });
        if (persona.km != null) {
          var etiqueta = document.createElement("div");
          etiqueta.className = "mapa-km";
          etiqueta.textContent = textoKm(persona.km);
          etiquetasKm.push(new maplibregl.Marker({ element: etiqueta, anchor: "bottom", offset: [0, -3] })
            .setLngLat([(persona.lon + destino.lon) / 2, (persona.lat + destino.lat) / 2])
            .addTo(mapa));
        }
      });
    }

    lineas = { type: "FeatureCollection", features: rasgos };
    var fuente = mapa.getSource("lineas");
    if (fuente) { fuente.setData(lineas); }
  }

  var ultimosPuntos = [];
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

  function elementoLugar(lugar) {
    var el = document.createElement("div");
    el.className = "mapa-pin";
    el.title = lugar.nombre;
    el.appendChild(document.createElement("span"));
    var etiqueta = document.createElement("em");
    etiqueta.textContent = lugar.nombre;
    el.appendChild(etiqueta);
    return el;
  }

  function elementoPersona(persona) {
    var el = document.createElement("div");
    el.className = "mapa-persona" + (persona.yo ? " is-yo" : "") + (persona.vieja ? " is-vieja" : "");
    el.title = persona.yo ? "Vos" : persona.nombre;
    var inicial = document.createElement("span");
    inicial.textContent = (persona.nombre || "?").charAt(0).toUpperCase();
    el.appendChild(inicial);
    return el;
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
        detalle.textContent = [kilometros(persona.km), hace(persona.hace_segundos)].filter(Boolean).join(" · ");
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

    marcadoresLugares.forEach(function (m) { m.remove(); });
    marcadoresLugares = datos.lugares.map(function (lugar) {
      return new maplibregl.Marker({ element: elementoLugar(lugar), anchor: "center" })
        .setLngLat([lugar.lon, lugar.lat])
        .addTo(mapa);
    });

    var vigentes = {};

    datos.personas.forEach(function (persona) {

      if (!persona.comparte) { return; }

      vigentes[persona.id] = true;

      if (marcadoresPersonas[persona.id]) {
        marcadoresPersonas[persona.id].remove();
      }

      marcadoresPersonas[persona.id] = new maplibregl.Marker({ element: elementoPersona(persona), anchor: "center" })
        .setLngLat([persona.lon, persona.lat])
        .addTo(mapa);
    });

    Object.keys(marcadoresPersonas).forEach(function (id) {
      if (!vigentes[id]) {
        marcadoresPersonas[id].remove();
        delete marcadoresPersonas[id];
      }
    });

    // Se encuadra todo cuando aparece o desaparece alguien (no en cada actualización, para no mover el mapa mientras lo mirás).
    var puntos = marcadoresLugares.concat(Object.keys(marcadoresPersonas).map(function (id) { return marcadoresPersonas[id]; }));

    ultimosPuntos = puntos;

    if (puntos.length !== ultimoConteo) {
      ultimoConteo = puntos.length;
      encuadrar();
    }
  }

  function encuadrar() {
    if (ultimosPuntos.length === 1) {
      mapa.jumpTo({ center: ultimosPuntos[0].getLngLat(), zoom: 15 });
    } else if (ultimosPuntos.length > 1) {
      var limites = new maplibregl.LngLatBounds();
      ultimosPuntos.forEach(function (m) { limites.extend(m.getLngLat()); });
      mapa.fitBounds(limites, { padding: 64, maxZoom: 16, duration: 0 });
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
        pintarLineas(datos);
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

  // Si cambia el tamaño del contenedor (pantalla estática, girar el celular), el mapa se reacomoda.
  if (window.ResizeObserver) {
    var primera = true;
    new ResizeObserver(function () {
      mapa.resize();
      // Con el tamaño ya definitivo se vuelve a encuadrar una vez, para que el zoom no quede de más.
      if (primera) { primera = false; encuadrar(); }
    }).observe(lienzo);
  }

}());
