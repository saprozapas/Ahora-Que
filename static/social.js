/* ==========================================================================
   Social: feed de publicaciones (pestañas Amigos y Descubrir)

   La página trae el armazón y las <template>; acá se piden las
   publicaciones a /social/feed y se arman las tarjetas. Todo el texto de las
   personas entra con textContent, nunca como HTML.

   Los ganchos del HTML son atributos data-soc-*; las clases son solo estilo.
   ========================================================================== */

(() => {
  const raiz = document.getElementById("soc-feed");
  if (!raiz) return;

  const $ = (selector, desde = document) => desde.querySelector(selector);

  const lista = $("[data-soc-lista]", raiz);
  const vacio = $("[data-soc-vacio]", raiz);
  const cargando = $("[data-soc-cargando]", raiz);
  const botonMas = $("[data-soc-mas]", raiz);
  const avisoGeneral = $("[data-soc-error]", raiz);

  const plantillaTarjeta = document.getElementById("soc-tpl-tarjeta");
  const plantillaComentario = document.getElementById("soc-tpl-comentario");
  const plantillaPublicable = document.getElementById("soc-tpl-publicable");

  const modalPublicar = document.getElementById("soc-modal-publicar");
  const modalReportar = document.getElementById("soc-modal-reportar");

  const urls = {
    feed: raiz.dataset.urlFeed,
    publicables: raiz.dataset.urlPublicables,
    publicar: raiz.dataset.urlPublicar,
    reportes: raiz.dataset.urlReportes,
    raiz: raiz.dataset.urlRaiz,
    detalle: raiz.dataset.urlDetalle,
  };

  let siguiente = null;
  let ocupado = false;


  /* --- Pedidos al servidor ------------------------------------------------ */

  const pedir = async (url, cuerpo) => {
    const opciones = { credentials: "same-origin", headers: {} };

    if (cuerpo !== undefined) {
      opciones.method = "POST";
      opciones.headers["Content-Type"] = "application/json";
      opciones.body = JSON.stringify(cuerpo);
    }

    let respuesta;
    try {
      respuesta = await fetch(url, opciones);
    } catch (error) {
      throw new Error("No hay conexión. Intentá de nuevo.");
    }

    if (respuesta.status === 401) {
      window.location.href = "/login";
      throw new Error("Iniciá sesión para continuar.");
    }

    let datos = {};
    try {
      datos = await respuesta.json();
    } catch (error) {
      // Respuesta sin JSON: se informa con el mensaje genérico de abajo.
    }

    if (!respuesta.ok) {
      throw new Error(datos.error || "Algo salió mal. Intentá de nuevo.");
    }

    return datos;
  };

  const mostrarError = (elemento, mensaje) => {
    elemento.textContent = mensaje;
    elemento.hidden = false;
  };

  const limpiarError = (elemento) => {
    elemento.textContent = "";
    elemento.hidden = true;
  };


  /* --- Formatos ------------------------------------------------------------ */

  const dosDigitos = (n) => String(n).padStart(2, "0");

  const hace = (iso) => {
    const fecha = new Date(iso);
    const minutos = Math.floor((Date.now() - fecha.getTime()) / 60000);

    if (minutos < 1) return "ahora";
    if (minutos < 60) return `hace ${minutos} min`;

    const horas = Math.floor(minutos / 60);
    if (horas < 24) return `hace ${horas} h`;

    const dias = Math.floor(horas / 24);
    if (dias < 7) return `hace ${dias} ${dias === 1 ? "día" : "días"}`;

    return `${dosDigitos(fecha.getDate())}/${dosDigitos(fecha.getMonth() + 1)}`;
  };

  const cuando = (plan) => {
    if (!plan.fecha) return "";
    const [, mes, dia] = plan.fecha.split("-");
    return `${dia}/${mes}${plan.hora ? ` · ${plan.hora}` : ""}`;
  };

  const precio = (plan) => {
    const { precio_min: min, precio_max: max } = plan;
    if (min == null && max == null) return "";
    if (min != null && max != null && min !== max) return `$${min} a $${max}`;
    return `$${min != null ? min : max}`;
  };

  const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;


  /* --- Tarjeta ------------------------------------------------------------- */

  const pintarLikes = (tarjeta, publicacion) => {
    const boton = $("[data-soc-like]", tarjeta);
    boton.setAttribute("aria-pressed", String(publicacion.yo_di_like));
    $("[data-soc-like-icono]", boton).textContent = publicacion.yo_di_like ? "♥" : "♡";
    $("[data-soc-like-n]", boton).textContent = publicacion.likes;
  };

  const pintarGuardado = (tarjeta, publicacion) => {
    const boton = $("[data-soc-guardar]", tarjeta);
    boton.setAttribute("aria-pressed", String(publicacion.guardado));
    $("[data-soc-guardar-icono]", boton).textContent = publicacion.guardado ? "★" : "☆";
    $("[data-soc-guardar-texto]", boton).textContent = publicacion.guardado ? "Guardado" : "Guardar";

    // El detalle del plan solo se puede abrir si es tuyo o lo guardaste.
    const enlace = $("[data-soc-ver-plan]", tarjeta);
    const puedeVer = publicacion.es_mio || publicacion.guardado;
    enlace.hidden = !puedeVer;
    if (puedeVer) {
      enlace.href = urls.detalle.replace("__ID__", publicacion.plan.id);
    }
  };

  const pintarContadorComentarios = (tarjeta, publicacion) => {
    $("[data-soc-comentarios-n]", tarjeta).textContent = publicacion.comentarios;
  };

  const rellenarTexto = (tarjeta, selector, texto) => {
    const elemento = $(selector, tarjeta);
    elemento.textContent = texto || "";
    elemento.hidden = !texto;
  };

  const crearTarjeta = (publicacion) => {
    const tarjeta = plantillaTarjeta.content.firstElementChild.cloneNode(true);
    const plan = publicacion.plan;

    tarjeta.dataset.publicacionId = publicacion.id;

    $("[data-soc-avatar]", tarjeta).textContent =
      (publicacion.autor.nombre || "?").trim().charAt(0).toUpperCase();
    $("[data-soc-autor]", tarjeta).textContent = publicacion.es_mio ? "Vos" : publicacion.autor.nombre;
    $("[data-soc-fecha]", tarjeta).textContent = hace(publicacion.creada_en);
    $("[data-soc-visibilidad]", tarjeta).textContent =
      publicacion.visibilidad === "publico" ? "Todos" : "Amigos";

    rellenarTexto(tarjeta, "[data-soc-texto]", publicacion.texto);

    $("[data-soc-plan-nombre]", tarjeta).textContent = plan.nombre;
    $("[data-soc-plan-estado]", tarjeta).textContent = plan.estado_texto;
    rellenarTexto(tarjeta, "[data-soc-plan-descripcion]", plan.descripcion);
    rellenarTexto(tarjeta, "[data-soc-plan-cuando]", cuando(plan) && `Cuándo: ${cuando(plan)}`);
    rellenarTexto(
      tarjeta,
      "[data-soc-plan-lugares]",
      plan.lugares.length ? `Lugares: ${plan.lugares.map((l) => l.nombre).join(" → ")}` : ""
    );
    rellenarTexto(tarjeta, "[data-soc-plan-precio]", precio(plan) && `Precio: ${precio(plan)}`);
    rellenarTexto(
      tarjeta,
      "[data-soc-plan-puntaje]",
      plan.promedio != null ? `★ ${plan.promedio} · ${plural(plan.votos, "voto", "votos")}` : ""
    );

    $("[data-soc-eliminar]", tarjeta).hidden = !publicacion.es_mio;
    $("[data-soc-reportar]", tarjeta).hidden = publicacion.es_mio;

    pintarLikes(tarjeta, publicacion);
    pintarGuardado(tarjeta, publicacion);
    pintarContadorComentarios(tarjeta, publicacion);

    tarjeta._publicacion = publicacion;
    return tarjeta;
  };


  /* --- Comentarios --------------------------------------------------------- */

  const crearComentario = (comentario) => {
    const fila = plantillaComentario.content.firstElementChild.cloneNode(true);

    fila.dataset.comentarioId = comentario.id;
    $("[data-soc-comentario-autor]", fila).textContent = comentario.autor.nombre;
    $("[data-soc-comentario-fecha]", fila).textContent = hace(comentario.creado_en);
    $("[data-soc-comentario-texto]", fila).textContent = comentario.texto;
    $("[data-soc-comentario-eliminar]", fila).hidden = !comentario.puedo_borrar;
    $("[data-soc-comentario-reportar]", fila).hidden = comentario.puedo_borrar;

    return fila;
  };

  const cargarComentarios = async (tarjeta) => {
    const zona = $("[data-soc-zona-comentarios]", tarjeta);
    const listaComentarios = $("[data-soc-comentarios-lista]", tarjeta);
    const error = $("[data-soc-comentario-error]", tarjeta);

    limpiarError(error);

    try {
      const datos = await pedir(
        `${urls.raiz}/publicaciones/${tarjeta.dataset.publicacionId}/comentarios`
      );
      listaComentarios.replaceChildren(...datos.comentarios.map(crearComentario));
      tarjeta._publicacion.comentarios = datos.comentarios.length;
      pintarContadorComentarios(tarjeta, tarjeta._publicacion);
    } catch (e) {
      mostrarError(error, e.message);
    }

    zona.hidden = false;
  };


  /* --- Acciones sobre una tarjeta ------------------------------------------ */

  const alternarComentarios = async (tarjeta, boton) => {
    const zona = $("[data-soc-zona-comentarios]", tarjeta);
    const abrir = zona.hidden;

    boton.setAttribute("aria-expanded", String(abrir));

    if (!abrir) {
      zona.hidden = true;
      return;
    }

    await cargarComentarios(tarjeta);
    $("[data-soc-comentario-input]", tarjeta).focus();
  };

  const darLike = async (tarjeta) => {
    const publicacion = tarjeta._publicacion;
    const quiere = !publicacion.yo_di_like;

    // Se pinta al instante y se corrige si el servidor dice otra cosa.
    const antes = { yo_di_like: publicacion.yo_di_like, likes: publicacion.likes };
    publicacion.yo_di_like = quiere;
    publicacion.likes += quiere ? 1 : -1;
    pintarLikes(tarjeta, publicacion);

    try {
      const datos = await pedir(
        `${urls.raiz}/publicaciones/${publicacion.id}/like`,
        { me_gusta: quiere }
      );
      publicacion.yo_di_like = datos.yo_di_like;
      publicacion.likes = datos.likes;
    } catch (e) {
      Object.assign(publicacion, antes);
      mostrarError(avisoGeneral, e.message);
    }

    pintarLikes(tarjeta, publicacion);
  };

  const guardar = async (tarjeta) => {
    const publicacion = tarjeta._publicacion;
    const quiere = !publicacion.guardado;

    try {
      const datos = await pedir(
        `${urls.raiz}/publicaciones/${publicacion.id}/guardar`,
        { guardar: quiere }
      );
      publicacion.guardado = datos.guardado;
      limpiarError(avisoGeneral);
    } catch (e) {
      mostrarError(avisoGeneral, e.message);
    }

    pintarGuardado(tarjeta, publicacion);
  };

  const mostrarVacioSiHaceFalta = () => {
    vacio.hidden = lista.children.length > 0 || ocupado || siguiente !== null;
  };

  const eliminarPublicacion = async (tarjeta) => {
    const confirmado = await window.preguntar("¿Eliminar esta publicación? El plan no se borra.");
    if (!confirmado) return;

    try {
      await pedir(
        `${urls.raiz}/publicaciones/${tarjeta.dataset.publicacionId}/eliminar`,
        {}
      );
      tarjeta.remove();
      mostrarVacioSiHaceFalta();
    } catch (e) {
      mostrarError(avisoGeneral, e.message);
    }
  };

  const enviarComentario = async (tarjeta, formulario) => {
    const entrada = $("[data-soc-comentario-input]", formulario);
    const error = $("[data-soc-comentario-error]", tarjeta);
    const texto = entrada.value.trim();

    if (!texto) return;

    limpiarError(error);
    entrada.disabled = true;

    try {
      const datos = await pedir(
        `${urls.raiz}/publicaciones/${tarjeta.dataset.publicacionId}/comentarios`,
        { texto }
      );
      $("[data-soc-comentarios-lista]", tarjeta).append(crearComentario(datos.comentario));
      tarjeta._publicacion.comentarios += 1;
      pintarContadorComentarios(tarjeta, tarjeta._publicacion);
      entrada.value = "";
    } catch (e) {
      mostrarError(error, e.message);
    }

    entrada.disabled = false;
    entrada.focus();
  };

  const eliminarComentario = async (tarjeta, fila) => {
    const error = $("[data-soc-comentario-error]", tarjeta);
    const confirmado = await window.preguntar("¿Eliminar este comentario?");
    if (!confirmado) return;

    try {
      await pedir(`${urls.raiz}/comentarios/${fila.dataset.comentarioId}/eliminar`, {});
      fila.remove();
      tarjeta._publicacion.comentarios = Math.max(0, tarjeta._publicacion.comentarios - 1);
      pintarContadorComentarios(tarjeta, tarjeta._publicacion);
    } catch (e) {
      mostrarError(error, e.message);
    }
  };


  /* --- Reportar ------------------------------------------------------------ */

  let reporte = null;

  const abrirReporte = (tipo, id, titulo) => {
    reporte = { tipo, id };
    $("#soc-modal-reportar-titulo", modalReportar).textContent = titulo;
    $("[data-soc-motivo]", modalReportar).value = "";
    limpiarError($("[data-soc-reportar-error]", modalReportar));
    modalReportar.showModal();
  };

  $("[data-soc-form-reportar]", modalReportar).addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (!reporte) return;

    const error = $("[data-soc-reportar-error]", modalReportar);
    limpiarError(error);

    try {
      await pedir(urls.reportes, {
        tipo: reporte.tipo,
        id: reporte.id,
        motivo: $("[data-soc-motivo]", modalReportar).value.trim(),
      });
      modalReportar.close();
      await window.preguntar("Gracias, vamos a revisar el reporte.", false);
    } catch (e) {
      mostrarError(error, e.message);
    }
  });


  /* --- Clics dentro del feed (una sola escucha para todas las tarjetas) ----- */

  lista.addEventListener("click", (evento) => {
    const boton = evento.target.closest("button");
    const tarjeta = evento.target.closest(".soc-tarjeta");
    if (!boton || !tarjeta) return;

    if (boton.matches("[data-soc-like]")) darLike(tarjeta);
    else if (boton.matches("[data-soc-guardar]")) guardar(tarjeta);
    else if (boton.matches("[data-soc-comentarios]")) alternarComentarios(tarjeta, boton);
    else if (boton.matches("[data-soc-eliminar]")) eliminarPublicacion(tarjeta);
    else if (boton.matches("[data-soc-reportar]")) {
      abrirReporte("publicacion", tarjeta.dataset.publicacionId, "Reportar publicación");
    } else {
      const fila = boton.closest(".soc-comentario");
      if (!fila) return;

      if (boton.matches("[data-soc-comentario-eliminar]")) eliminarComentario(tarjeta, fila);
      else if (boton.matches("[data-soc-comentario-reportar]")) {
        abrirReporte("comentario", fila.dataset.comentarioId, "Reportar comentario");
      }
    }
  });

  lista.addEventListener("submit", (evento) => {
    const formulario = evento.target.closest("[data-soc-form-comentar]");
    if (!formulario) return;

    evento.preventDefault();
    enviarComentario(evento.target.closest(".soc-tarjeta"), formulario);
  });


  /* --- Cargar el feed ------------------------------------------------------ */

  const cargarPagina = async () => {
    if (ocupado) return;

    ocupado = true;
    cargando.hidden = false;
    botonMas.hidden = true;
    limpiarError(avisoGeneral);

    const parametros = new URLSearchParams({ pestana: raiz.dataset.pestana });
    if (siguiente) parametros.set("antes", siguiente);

    try {
      const datos = await pedir(`${urls.feed}?${parametros}`);

      lista.append(...datos.publicaciones.map(crearTarjeta));
      siguiente = datos.hay_mas ? datos.siguiente : null;
    } catch (e) {
      mostrarError(avisoGeneral, e.message);
    }

    ocupado = false;
    cargando.hidden = true;
    botonMas.hidden = siguiente === null;
    mostrarVacioSiHaceFalta();
  };

  botonMas.addEventListener("click", cargarPagina);


  /* --- Compartir un plan ---------------------------------------------------- */

  const formularioPublicar = $("[data-soc-form-publicar]", modalPublicar);
  const contenedorPublicables = $("[data-soc-publicables]", modalPublicar);
  const avisoPublicablesVacio = $("[data-soc-publicables-vacio]", modalPublicar);
  const errorPublicar = $("[data-soc-publicar-error]", modalPublicar);
  const campoTexto = $("[data-soc-texto-input]", modalPublicar);
  const cuentaTexto = $("[data-soc-texto-cuenta]", modalPublicar);
  const botonPublicar = $("[data-soc-publicar-enviar]", modalPublicar);

  const crearPublicable = (plan) => {
    const opcion = plantillaPublicable.content.firstElementChild.cloneNode(true);
    const partes = [plan.estado_texto, cuando(plan), plan.resumen_lugares].filter(Boolean);

    $("input", opcion).value = plan.id;
    $("[data-soc-publicable-nombre]", opcion).textContent = plan.nombre;
    $("[data-soc-publicable-detalle]", opcion).textContent = partes.join(" · ");

    return opcion;
  };

  const cargarPublicables = async () => {
    contenedorPublicables.replaceChildren();
    avisoPublicablesVacio.hidden = true;
    botonPublicar.disabled = true;
    limpiarError(errorPublicar);

    try {
      const datos = await pedir(urls.publicables);

      contenedorPublicables.append(...datos.planes.map(crearPublicable));
      avisoPublicablesVacio.hidden = datos.planes.length > 0;
      botonPublicar.disabled = datos.planes.length === 0;
    } catch (e) {
      mostrarError(errorPublicar, e.message);
    }
  };

  $("[data-soc-abrir-publicar]", raiz).addEventListener("click", () => {
    formularioPublicar.reset();
    cuentaTexto.textContent = "0";
    cargarPublicables();
  });

  campoTexto.addEventListener("input", () => {
    cuentaTexto.textContent = campoTexto.value.length;
  });

  formularioPublicar.addEventListener("submit", async (evento) => {
    evento.preventDefault();

    const datos = new FormData(formularioPublicar);
    limpiarError(errorPublicar);
    botonPublicar.disabled = true;

    try {
      const respuesta = await pedir(urls.publicar, {
        plan_id: datos.get("plan_id"),
        texto: datos.get("texto"),
        visibilidad: datos.get("visibilidad"),
      });

      modalPublicar.close();

      // Lo propio siempre figura en la pestaña Amigos: ahí aparece arriba de
      // todo al instante. En Descubrir solo se avisa dónde encontrarlo.
      if (raiz.dataset.pestana === "amigos") {
        lista.prepend(crearTarjeta(respuesta.publicacion));
        vacio.hidden = true;
      } else {
        await window.preguntar("Listo, compartiste tu plan. Lo vas a ver en la pestaña Amigos.", false);
      }
    } catch (e) {
      mostrarError(errorPublicar, e.message);
      botonPublicar.disabled = false;
    }
  });


  /* --- Cerrar modales con los botones "Cancelar" y la cruz ------------------ */

  document.querySelectorAll("dialog.modal [data-soc-cerrar]").forEach((boton) => {
    boton.addEventListener("click", () => boton.closest("dialog").close());
  });


  cargarPagina();
})();
