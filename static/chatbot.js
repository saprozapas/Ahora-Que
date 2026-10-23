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

  // La caja no tiene scroll propio: se lleva a la vista el último mensaje scrolleando la pantalla.
  function bajarAlFinal() {
    var ultimo = caja.lastElementChild;
    if (ultimo && ultimo.scrollIntoView) { ultimo.scrollIntoView({ block: "nearest" }); }
  }

  // Durante el streaming solo se baja solo si la persona ya estaba abajo: si
  // subió a leer algo, no se la arrastra de vuelta con cada fragmento.
  function bajarSiEstaAbajo() {
    if (caja.getBoundingClientRect().bottom - window.innerHeight < 80) { bajarAlFinal(); }
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
    guardar.className = "btn btn--primary btn--sm chatbot-accion";
    guardar.textContent = "Guardar como idea";
    acciones.appendChild(guardar);

    // Solo en la página de crear idea: carga el borrador en el formulario
    // para editarlo a mano antes de guardarlo.
    if (typeof window.crearIdeaCargarBorrador === "function") {
      var alFormulario = document.createElement("button");
      alFormulario.type = "button";
      alFormulario.className = "btn btn--secondary btn--sm chatbot-accion";
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

  // --- Respuesta en vivo (streaming) -----------------------------------------
  // /chatbot/mensaje_stream manda Server-Sent Events: una línea "data: {json}"
  // por evento. Tipos: estado (usando una herramienta), razonamiento (un pedazo
  // de lo que el modelo "piensa"), texto (un pedazo de la respuesta),
  // reiniciar (borrar lo mostrado), fin y error.

  function hayStreaming() {
    return !!(window.fetch && window.ReadableStream && window.TextDecoder);
  }

  function leerEventos(respuesta, alEvento) {
    var lector = respuesta.body.getReader();
    var decoder = new TextDecoder("utf-8");
    var pendiente = "";

    function procesarBloque(bloque) {
      var datos = "";
      bloque.split("\n").forEach(function (linea) {
        if (linea.indexOf("data: ") === 0) { datos += linea.slice(6); }
      });
      if (!datos) { return; }
      var evento;
      try { evento = JSON.parse(datos); } catch (e) { return; }
      alEvento(evento);
    }

    function leer() {
      return lector.read().then(function (lectura) {
        if (lectura.done) {
          if (pendiente.trim()) { procesarBloque(pendiente); }
          return;
        }
        pendiente += decoder.decode(lectura.value, { stream: true });
        var bloques = pendiente.split("\n\n");
        pendiente = bloques.pop();  // lo último puede estar incompleto
        bloques.forEach(procesarBloque);
        return leer();
      });
    }
    return leer();
  }

  // Lo que se ve mientras el bot trabaja. NO es una burbuja: es un bloque
  // chico y apagado con dos líneas, y desaparece cuando empieza la respuesta.
  //   estado:  qué está haciendo ("Buscando lugares...")
  //   pensar:  el razonamiento del modelo, que se va escribiendo en vivo
  // La burbuja de la respuesta recién se crea cuando llega el primer texto.
  function crearVista() {
    var pensamiento = null, lineaEstado = null, lineaTexto = null, nodoPensar = null;
    var burbuja = null, nodoTexto = null;
    var colaPensar = "", colaTexto = "", programado = false;

    function mostrarPensamiento() {
      if (pensamiento) { return; }
      pensamiento = document.createElement("div");
      pensamiento.className = "chatbot-pensamiento";
      pensamiento.setAttribute("aria-hidden", "true");
      lineaEstado = document.createElement("p");
      lineaEstado.className = "chatbot-pensamiento-estado";
      lineaTexto = document.createElement("p");
      lineaTexto.className = "chatbot-pensamiento-texto";
      nodoPensar = document.createTextNode("");
      lineaTexto.appendChild(nodoPensar);
      pensamiento.appendChild(lineaEstado);
      pensamiento.appendChild(lineaTexto);
      caja.appendChild(pensamiento);
      mostrarVacio();
      bajarAlFinal();
    }

    function ocultarPensamiento() {
      if (pensamiento) { pensamiento.remove(); }
      pensamiento = lineaEstado = lineaTexto = nodoPensar = null;
      colaPensar = "";
    }

    function crearBurbuja() {
      if (burbuja) { return; }
      ocultarPensamiento();
      burbuja = agregarMensaje("assistant", "");
      nodoTexto = document.createTextNode("");
      burbuja.appendChild(nodoTexto);
      burbuja.classList.add("chatbot-transmitiendo");
    }

    // Los fragmentos llegan muy seguidos: en vez de tocar la página con cada
    // uno, se juntan y se pintan una sola vez por cuadro (requestAnimationFrame).
    function volcar() {
      programado = false;
      if (colaPensar && nodoPensar) {
        nodoPensar.appendData(colaPensar);
        lineaTexto.scrollTop = lineaTexto.scrollHeight;  // se ve siempre lo último
      }
      colaPensar = "";
      if (colaTexto && nodoTexto) { nodoTexto.appendData(colaTexto); }
      colaTexto = "";
      bajarSiEstaAbajo();
    }

    function programar() {
      if (programado) { return; }
      programado = true;
      window.requestAnimationFrame(volcar);
    }

    return {
      // Qué está haciendo el bot. Empieza una "vuelta" nueva: se borra el
      // razonamiento anterior para que el bloque no crezca sin parar.
      estado: function (texto) {
        if (burbuja) { return; }
        mostrarPensamiento();
        lineaEstado.textContent = texto;
        nodoPensar.data = "";
        colaPensar = "";
      },
      pensar: function (fragmento) {
        if (burbuja) { return; }
        mostrarPensamiento();
        colaPensar += fragmento;
        programar();
      },
      escribir: function (fragmento) {
        crearBurbuja();
        colaTexto += fragmento;
        programar();
      },
      // El servidor descartó lo escrito (por ejemplo, el modelo iba a llamar a
      // una herramienta): se vuelve al estado de "trabajando".
      reiniciar: function () {
        if (burbuja) { burbuja.remove(); }
        burbuja = nodoTexto = null;
        colaTexto = "";
        mostrarPensamiento();
      },
      // Texto definitivo: el que guardó el servidor (puede tener la pregunta
      // final agregada).
      terminar: function (respuesta) {
        crearBurbuja();
        nodoTexto.data = respuesta;
        colaTexto = "";
        burbuja.classList.remove("chatbot-transmitiendo");
        bajarAlFinal();
      },
      cancelar: function () {
        ocultarPensamiento();
        if (burbuja) { burbuja.remove(); }
        burbuja = nodoTexto = null;
        colaTexto = "";
      },
      arrancar: mostrarPensamiento
    };
  }

  // Va llenando la vista a medida que llegan los eventos. Devuelve una promesa
  // con {respuesta, borrador}; falla si el servidor avisa un error o si la
  // conexión se corta antes del final (en ese caso el servidor no guardó nada).
  function pedirRespuestaEnVivo(texto, vista) {
    var fin = null;
    var errorServidor = null;

    function alEvento(evento) {
      if (evento.tipo === "estado") {
        vista.estado(evento.texto);
      } else if (evento.tipo === "razonamiento") {
        vista.pensar(evento.texto);
      } else if (evento.tipo === "texto") {
        vista.escribir(evento.texto);
      } else if (evento.tipo === "reiniciar") {
        vista.reiniciar();
      } else if (evento.tipo === "fin") {
        fin = evento;
      } else if (evento.tipo === "error") {
        errorServidor = evento.error;
      }
    }

    return fetch("/chatbot/mensaje_stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mensaje: texto, grupo_id: grupoId })
    }).then(function (respuesta) {
      if (!respuesta.ok) {
        // Errores de validación o de sesión: llegan como JSON normal.
        return respuesta.json().catch(function () { return {}; }).then(function (datos) {
          throw new Error(datos.error || "Algo salió mal. Probá de nuevo.");
        });
      }
      return leerEventos(respuesta, alEvento);
    }).then(function () {
      if (errorServidor) { throw new Error(errorServidor); }
      if (!fin) { throw new Error("Se cortó la conexión con el asistente. Probá de nuevo."); }
      return { respuesta: fin.respuesta, borrador: fin.borrador };
    });
  }

  function enviarMensaje(evento) {
    evento.preventDefault();
    var texto = input.value.trim();
    if (!texto || ocupado) { return; }

    agregarMensaje("user", texto);
    input.value = "";
    bloquear(true);

    // No hay burbuja de espera: la vista muestra un bloque apagado con lo que
    // el bot está haciendo, y la burbuja de la respuesta aparece con el primer
    // texto. Mientras se escribe, los lectores de pantalla esperan al final
    // en vez de leer cada pedazo.
    var vista = crearVista();
    vista.arrancar();
    caja.setAttribute("aria-busy", "true");

    var pedido = hayStreaming()
      ? pedirRespuestaEnVivo(texto, vista)
      : postJSON("/chatbot/mensaje", { mensaje: texto, grupo_id: grupoId });

    pedido
      .then(function (datos) {
        vista.terminar(datos.respuesta);  // el texto definitivo que guardó el servidor
        if (datos.borrador) { agregarBorrador(datos.borrador); }
      })
      .catch(function (error) {
        vista.cancelar();
        agregarMensaje("error", error.message);
        // Se devuelve el texto al campo para poder reintentar.
        if (!input.value) { input.value = texto; }
      })
      .then(function () {
        caja.setAttribute("aria-busy", "false");
        bajarAlFinal();
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