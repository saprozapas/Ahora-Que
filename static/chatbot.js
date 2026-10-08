/* Chatbot para armar ideas de plan (ver templates/_chatbot_panel.html).
   Habla con los endpoints de routes/chatbot.py. Todo el texto se pone
   con textContent: nada de lo que escribe el usuario o el bot se
   interpreta como HTML. */
(function () {
  "use strict";

  var panel = document.getElementById("chatbot");
  if (!panel) { return; }

  var caja      = document.getElementById("chatbot-mensajes");
  var vacio     = document.getElementById("chatbot-vacio");
  var form      = document.getElementById("chatbot-form");
  var input     = document.getElementById("chatbot-input");
  var enviar    = document.getElementById("chatbot-enviar");
  var botonNueva = document.getElementById("chatbot-nueva");
  var ocupado   = false;
  // Si el chat está dentro de un grupo, el servidor sabe cuántos son y al
  // guardar ofrece postular la idea en ese grupo.
  var grupoId   = panel.getAttribute("data-grupo-id") || "";

  function bajarAlFinal() {
    caja.scrollTop = caja.scrollHeight;
  }

  function mostrarVacio() {
    vacio.hidden = caja.querySelectorAll(".chatbot-mensaje, .chatbot-borrador").length > 0;
  }

  function agregarMensaje(rol, texto) {
    var div = document.createElement("div");
    div.className = "chatbot-mensaje chatbot-mensaje-" + rol;
    div.textContent = texto;
    caja.appendChild(div);
    mostrarVacio();
    bajarAlFinal();
    return div;
  }

  function precio(nivel) {
    if (nivel === null || nivel === undefined || nivel === "") { return ""; }
    nivel = parseInt(nivel, 10);
    return nivel > 0 ? new Array(nivel + 1).join("$") : "Gratis";
  }

  function pedirJSON(url, opciones) {
    return fetch(url, opciones).then(function (respuesta) {
      return respuesta.json().catch(function () { return {}; }).then(function (datos) {
        if (!respuesta.ok) {
          throw new Error(datos.error || "Algo salió mal. Probá de nuevo.");
        }
        return datos;
      });
    });
  }

  function postJSON(url, cuerpo) {
    return pedirJSON(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo || {})
    });
  }

  // --- Tarjeta de borrador ---------------------------------------------------

  function agregarBorrador(borrador) {
    var tarjeta = document.createElement("div");
    tarjeta.className = "chatbot-borrador";

    var etiqueta = document.createElement("p");
    etiqueta.className = "chatbot-borrador-etiqueta";
    etiqueta.textContent = "Borrador de idea";
    tarjeta.appendChild(etiqueta);

    var nombre = document.createElement("p");
    nombre.className = "chatbot-borrador-nombre";
    nombre.textContent = borrador.nombre;
    tarjeta.appendChild(nombre);

    if (borrador.descripcion) {
      var descripcion = document.createElement("p");
      descripcion.className = "chatbot-borrador-descripcion";
      descripcion.textContent = borrador.descripcion;
      tarjeta.appendChild(descripcion);
    }

    var lista = document.createElement("ol");
    lista.className = "chatbot-borrador-lugares";
    (borrador.lugares || []).forEach(function (lugar) {
      var item = document.createElement("li");
      item.className = "chatbot-borrador-lugar";

      var nombreLugar = document.createElement("strong");
      nombreLugar.textContent = lugar.nombre;
      item.appendChild(nombreLugar);

      var detalle = [];
      if (lugar.hora) { detalle.push(lugar.hora); }
      if (lugar.direccion) { detalle.push(lugar.direccion); }
      if (precio(lugar.nivel_precio)) { detalle.push(precio(lugar.nivel_precio)); }
      if (detalle.length) {
        var sub = document.createElement("small");
        sub.textContent = detalle.join(" · ");
        item.appendChild(sub);
      }
      lista.appendChild(item);
    });
    tarjeta.appendChild(lista);

    var acciones = document.createElement("div");
    acciones.className = "chatbot-borrador-acciones";

    var guardar = document.createElement("button");
    guardar.type = "button";
    guardar.className = "chatbot-accion chatbot-accion-principal";
    guardar.textContent = "Guardar como idea";
    acciones.appendChild(guardar);

    // Solo en la página de crear idea: carga el borrador en el formulario
    // para editarlo a mano antes de guardarlo.
    if (typeof window.crearIdeaCargarBorrador === "function") {
      var alFormulario = document.createElement("button");
      alFormulario.type = "button";
      alFormulario.className = "chatbot-accion";
      alFormulario.textContent = "Pasar al formulario";
      alFormulario.addEventListener("click", function () {
        window.crearIdeaCargarBorrador(borrador);
      });
      acciones.appendChild(alFormulario);
    }

    var estado = document.createElement("span");
    estado.className = "chatbot-borrador-estado";
    acciones.appendChild(estado);

    guardar.addEventListener("click", function () {
      guardar.disabled = true;
      guardar.textContent = "Guardando...";
      postJSON("/chatbot/confirmar_plan", { mensaje_id: borrador.mensaje_id, grupo_id: grupoId })
        .then(function (datos) {
          guardar.textContent = "Guardada";
          estado.textContent = "";
          var link = document.createElement("a");
          if (datos.postular_url) {
            link.href = datos.postular_url;
            link.textContent = "Elegir fecha y postular al grupo →";
          } else {
            link.href = datos.url;
            link.textContent = "Ver la idea →";
          }
          estado.appendChild(link);
        })
        .catch(function (error) {
          guardar.disabled = false;
          guardar.textContent = "Guardar como idea";
          estado.textContent = error.message;
        });
    });

    tarjeta.appendChild(acciones);
    caja.appendChild(tarjeta);
    mostrarVacio();
    bajarAlFinal();
  }

  // --- Enviar ----------------------------------------------------------------

  function bloquear(valor) {
    ocupado = valor;
    input.disabled = valor;
    enviar.disabled = valor;
    botonNueva.disabled = valor;
    enviar.setAttribute("aria-busy", valor ? "true" : "false");
  }

  function enviarMensaje(evento) {
    evento.preventDefault();
    var texto = input.value.trim();
    if (!texto || ocupado) { return; }

    agregarMensaje("user", texto);
    input.value = "";
    bloquear(true);

    var escribiendo = agregarMensaje("assistant", "Pensando...");
    escribiendo.classList.add("chatbot-escribiendo");

    postJSON("/chatbot/mensaje", { mensaje: texto, grupo_id: grupoId })
      .then(function (datos) {
        escribiendo.remove();
        agregarMensaje("assistant", datos.respuesta);
        if (datos.borrador) { agregarBorrador(datos.borrador); }
      })
      .catch(function (error) {
        escribiendo.remove();
        agregarMensaje("error", error.message);
        // Se devuelve el texto al campo para poder reintentar.
        if (!input.value) { input.value = texto; }
      })
      .then(function () {
        bloquear(false);
        input.focus();
      });
  }

  function nuevaConversacion() {
    if (ocupado) { return; }
    preguntar("¿Borrar esta conversación y empezar de cero?").then(function (si) {
      if (!si) { return; }
      bloquear(true);
      postJSON("/chatbot/nueva")
        .then(function () {
          var viejos = caja.querySelectorAll(".chatbot-mensaje, .chatbot-borrador");
          for (var i = 0; i < viejos.length; i++) { viejos[i].remove(); }
          mostrarVacio();
        })
        .catch(function (error) { agregarMensaje("error", error.message); })
        .then(function () { bloquear(false); });
    });
  }

  function cargarHistorial() {
    pedirJSON("/chatbot/historial")
      .then(function (datos) {
        (datos.mensajes || []).forEach(function (mensaje) {
          if (mensaje.tipo === "borrador") {
            agregarBorrador(mensaje.borrador);
          } else {
            agregarMensaje(mensaje.role, mensaje.content);
          }
        });
      })
      .catch(function (error) { agregarMensaje("error", error.message); });
  }

  form.addEventListener("submit", enviarMensaje);
  botonNueva.addEventListener("click", nuevaConversacion);
  cargarHistorial();
})();