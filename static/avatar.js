/* ==========================================================================
   Foto de perfil (perfil.html)

   Dos caminos: un avatar genérico (uno de cinco) o una foto del dispositivo. La foto se recorta en cuadrado y se
   achica en el navegador (JPEG de 320 px) antes de mandarla, para que pese poco. Al guardar, la página se
   recarga y la foto nueva aparece en todos lados (perfil, barra lateral, mapa de los planes).
   ========================================================================== */

(function () {

  "use strict";

  var modal = document.querySelector("[data-avatar-modal]");

  if (!modal) { return; }

  var url = modal.dataset.url;
  var archivo = modal.querySelector("[data-foto-archivo]");
  var quitar = modal.querySelector("[data-foto-quitar]");
  var estado = modal.querySelector("[data-foto-estado]");
  var LADO = 320;
  var MAX_BYTES = 140 * 1024;

  function avisar(texto, esError) {
    estado.textContent = texto || "";
    estado.hidden = !texto;
    estado.classList.toggle("is-error", Boolean(esError));
  }

  function ocupado(si) {
    modal.classList.toggle("is-ocupado", si);
    Array.prototype.forEach.call(modal.querySelectorAll("button, input"), function (el) { el.disabled = si; });
  }

  function enviar(cuerpo) {

    ocupado(true);
    avisar("Guardando…");

    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo)
    })
      .then(function (respuesta) { return respuesta.json().catch(function () { return {}; }); })
      .then(function (datos) {
        if (!datos.ok) { throw new Error(datos.error || "No se pudo guardar la foto."); }
        avisar("Listo.");
        window.setTimeout(function () { window.location.reload(); }, 250);
      })
      .catch(function (error) {
        ocupado(false);
        avisar(error.message || "No se pudo guardar la foto.", true);
      });
  }

  // ---- Avatares genéricos
  Array.prototype.forEach.call(modal.querySelectorAll("[data-preset]"), function (boton) {
    boton.addEventListener("click", function () {
      enviar({ tipo: "preset", preset: Number(boton.dataset.preset) });
    });
  });

  // ---- Quitar
  if (quitar) {
    quitar.addEventListener("click", function () { enviar({ tipo: "quitar" }); });
  }

  // ---- Foto del dispositivo: recorte cuadrado centrado, JPEG chico
  function recortar(imagen) {

    var lienzo = document.createElement("canvas");
    lienzo.width = LADO;
    lienzo.height = LADO;

    var contexto = lienzo.getContext("2d");
    var lado = Math.min(imagen.naturalWidth || imagen.width, imagen.naturalHeight || imagen.height);
    var x = ((imagen.naturalWidth || imagen.width) - lado) / 2;
    var y = ((imagen.naturalHeight || imagen.height) - lado) / 2;

    contexto.fillStyle = "#ffffff";
    contexto.fillRect(0, 0, LADO, LADO);
    contexto.drawImage(imagen, x, y, lado, lado, 0, 0, LADO, LADO);

    var calidad = 0.88;
    var datos = lienzo.toDataURL("image/jpeg", calidad);

    while (datos.length * 0.75 > MAX_BYTES && calidad > 0.4) {
      calidad -= 0.1;
      datos = lienzo.toDataURL("image/jpeg", calidad);
    }

    return datos;
  }

  if (archivo) {
    archivo.addEventListener("change", function () {

      var elegido = archivo.files && archivo.files[0];

      if (!elegido) { return; }

      if (elegido.type.indexOf("image/") !== 0) {
        avisar("Elegí una imagen (JPG, PNG o WebP).", true);
        return;
      }

      avisar("Preparando la foto…");

      var direccion = URL.createObjectURL(elegido);
      var imagen = new Image();

      imagen.onload = function () {
        URL.revokeObjectURL(direccion);
        enviar({ tipo: "foto", datos: recortar(imagen) });
      };

      imagen.onerror = function () {
        URL.revokeObjectURL(direccion);
        avisar("No pudimos leer esa imagen. Probá con otra.", true);
      };

      imagen.src = direccion;
      archivo.value = "";
    });
  }

}());
