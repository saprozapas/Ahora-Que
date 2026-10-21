/* ==========================================================================
   Social: feed de publicaciones (pestañas Amigos y Descubrir) y grilla de
   "Planes publicados" de los perfiles.

   Tres modos, según data-modo del contenedor #soc-feed:
     lista    tarjetas una debajo de otra (Amigos).
     grilla   miniaturas de fotos; al tocar una se abre la tarjeta en un
              diálogo (Descubrir y perfiles). Con data-autor se muestran solo
              las publicaciones de esa persona.
     unica    una sola publicación (data-publicacion): a donde llevan los
              avisos del Inbox. Con data-abrir-comentarios abre el hilo.

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
  const plantillaMiniatura = document.getElementById("soc-tpl-miniatura");
  const plantillaPublicable = document.getElementById("soc-tpl-publicable");   // solo en /social

  const modalPublicar = document.getElementById("soc-modal-publicar");         // solo en /social
  const modalReportar = document.getElementById("soc-modal-reportar");
  const modalGrupo = document.getElementById("soc-modal-grupo");
  const modalPost = document.getElementById("soc-modal-post");
  const contenedorPost = $("[data-soc-post-contenedor]", modalPost);

  const modoGrilla = raiz.dataset.modo === "grilla";
  const modoUnica = raiz.dataset.modo === "unica";
  const autorId = raiz.dataset.autor || null;

  const urls = {
    feed: raiz.dataset.urlFeed,
    publicables: raiz.dataset.urlPublicables,
    publicar: raiz.dataset.urlPublicar,
    reportes: raiz.dataset.urlReportes,
    raiz: raiz.dataset.urlRaiz,
    detalle: raiz.dataset.urlDetalle,
    perfil: raiz.dataset.urlPerfil,
    miPerfil: raiz.dataset.urlMiPerfil,
    grupos: raiz.dataset.urlGrupos,
    postular: raiz.dataset.urlPostular,
    fotos: `${raiz.dataset.urlRaiz}/fotos/`,
  };

  let siguiente = null;
  let ocupado = false;

  let totalPublicaciones = null;     // solo en los perfiles ("Planes publicados (N)")
  const publicaciones = new Map();   // id -> publicación (para abrirla desde la grilla)
  const tarjetas = new Map();        // id -> tarjeta ya armada (grilla)
  const miniaturas = new Map();      // id -> celda de la grilla

  if (modoGrilla) {
    lista.classList.remove("soc-lista");
    lista.classList.add("soc-grilla");
  }


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

  // Tres colores de portada, según el id (siempre el mismo para una publicación).
  const varianteDe = (publicacion) => parseInt(publicacion.id.slice(0, 2), 16) % 3;


  /* --- Tarjeta ------------------------------------------------------------- */

  // "Les gusta a Ana, Beto y 3 más". El servidor manda los nombres de hasta
  // 2 personas (sin contar al usuario, sus amigos primero); "vos" va al frente
  // si diste me gusta.
  const textoLikes = (p) => {
    if (p.likes <= 0) return "";
    const nombres = [...(p.yo_di_like ? ["vos"] : []), ...(p.likes_nombres || [])];
    const resto = p.likes - nombres.length;

    if (nombres.length === 0) return `${p.likes} me gusta`;
    if (p.likes === 1) return nombres[0] === "vos" ? "Te gusta" : `Le gusta a ${nombres[0]}`;
    if (resto > 0) return `Les gusta a ${nombres.join(", ")} y ${resto} más`;
    if (nombres.length === 1) return `Les gusta a ${nombres[0]}`;
    return `Les gusta a ${nombres.slice(0, -1).join(", ")} y ${nombres[nombres.length - 1]}`;
  };

  // Los números que aparecen al pasar el mouse sobre la miniatura de la grilla.
  const actualizarMiniatura = (publicacion) => {
    const miniatura = miniaturas.get(publicacion.id);
    if (!miniatura) return;
    $("[data-soc-mini-likes]", miniatura).textContent = publicacion.likes;
    $("[data-soc-mini-comentarios]", miniatura).textContent = publicacion.comentarios;
  };

  const pintarLikes = (tarjeta, publicacion) => {
    const boton = $("[data-soc-like]", tarjeta);
    boton.setAttribute("aria-pressed", String(publicacion.yo_di_like));
    boton.title = publicacion.yo_di_like ? "Quitar me gusta" : "Me gusta";
    $("[data-soc-like-n]", boton).textContent = publicacion.likes;

    const texto = $("[data-soc-likes-texto]", tarjeta);
    texto.textContent = textoLikes(publicacion);
    texto.hidden = publicacion.likes <= 0;
    actualizarMiniatura(publicacion);
  };

  const pintarGuardado = (tarjeta, publicacion) => {
    const boton = $("[data-soc-guardar]", tarjeta);
    boton.setAttribute("aria-pressed", String(publicacion.guardado));
    boton.title = publicacion.guardado ? "Quitar de guardados" : "Guardar plan";
    boton.setAttribute("aria-label", boton.title);

    // El detalle del plan solo se puede abrir si es tuyo o lo guardaste: si
    // no, el nombre queda como texto, sin enlace.
    const enlaces = [
      $("[data-soc-plan-nombre]", tarjeta),
      $("[data-soc-portada-nombre]", tarjeta),
    ];
    for (const enlace of enlaces) {
      if (publicacion.es_mio || publicacion.guardado) {
        enlace.href = urls.detalle.replace("__ID__", publicacion.plan.id);
      } else {
        enlace.removeAttribute("href");
      }
    }
  };

  // Debajo de la descripción: los últimos 2 comentarios y "Ver los N
  // comentarios". Se oculta mientras el hilo completo está abierto.
  const pintarPrevia = (tarjeta, publicacion) => {
    const bloque = $("[data-soc-previa]", tarjeta);
    const ver = $("[data-soc-ver-comentarios]", bloque);
    const previa = publicacion.comentarios_previa || [];
    const hiloAbierto = !$("[data-soc-zona-comentarios]", tarjeta).hidden;

    $("[data-soc-previa-lista]", bloque).replaceChildren(
      ...previa.map((comentario) => {
        const linea = document.createElement("p");
        const autor = document.createElement("strong");
        autor.textContent = comentario.autor;
        linea.append(autor, " ", comentario.texto);   // strings: entran como texto, no como HTML
        return linea;
      })
    );

    const faltan = publicacion.comentarios > previa.length;
    ver.hidden = !faltan;
    if (faltan) ver.textContent = `Ver los ${publicacion.comentarios} comentarios`;
    bloque.hidden = hiloAbierto || publicacion.comentarios === 0;
  };

  const pintarContadorComentarios = (tarjeta, publicacion) => {
    $("[data-soc-comentarios-n]", tarjeta).textContent = publicacion.comentarios;
    pintarPrevia(tarjeta, publicacion);
    actualizarMiniatura(publicacion);
  };

  // Al cerrar el hilo, la vista previa pasa a mostrar lo último que hay en él.
  const previaDesdeHilo = (tarjeta) =>
    [...tarjeta.querySelectorAll(".soc-comentario")].slice(-2).map((fila) => ({
      id: fila.dataset.comentarioId,
      autor: $("[data-soc-comentario-autor]", fila).textContent,
      texto: $("[data-soc-comentario-texto]", fila).textContent,
    }));

  const rellenarTexto = (tarjeta, selector, texto) => {
    const elemento = $(selector, tarjeta);
    elemento.textContent = texto || "";
    elemento.hidden = !texto;
  };

  // Las fotos van en un carrusel horizontal con "snap". Sin fotos, el plan
  // se muestra sobre una portada de color (3 variantes, según el id).
  const pintarMedia = (tarjeta, publicacion) => {
    const contenedor = $("[data-soc-fotos]", tarjeta);
    const puntos = $("[data-soc-puntos]", tarjeta);
    const portada = $("[data-soc-portada]", tarjeta);
    const nombre = publicacion.plan.nombre;

    if (publicacion.fotos.length === 0) {
      const variante = varianteDe(publicacion);
      portada.className = `soc-portada soc-portada-${variante}`;
      portada.hidden = false;
      $("[data-soc-portada-nombre]", portada).textContent = nombre;
      // El nombre ya está en la portada: no se repite como título.
      $(".soc-plan-nombre", tarjeta).hidden = true;
      return;
    }

    contenedor.hidden = false;
    contenedor.dataset.aspecto = publicacion.aspecto || "cuadrada";
    contenedor.replaceChildren(
      ...publicacion.fotos.map((id, i) => {
        const imagen = document.createElement("img");
        imagen.src = urls.fotos + id;
        imagen.alt = `Foto ${i + 1} de ${nombre}`;
        imagen.loading = "lazy";
        imagen.decoding = "async";
        return imagen;
      })
    );

    if (publicacion.fotos.length > 1) {
      // Se recorre con las flechas del teclado; los puntos son solo un indicador visual.
      contenedor.tabIndex = 0;
      contenedor.setAttribute("role", "group");
      contenedor.setAttribute("aria-roledescription", "carrusel");
      contenedor.setAttribute("aria-label", `Fotos de ${nombre}`);
      puntos.setAttribute("aria-hidden", "true");
      puntos.hidden = false;
      puntos.replaceChildren(
        ...publicacion.fotos.map((_, i) => {
          const punto = document.createElement("span");
          punto.className = i === 0 ? "is-activo" : "";
          return punto;
        })
      );
      contenedor.addEventListener("scroll", () => {
        const actual = Math.round(contenedor.scrollLeft / contenedor.clientWidth);
        [...puntos.children].forEach((p, i) => p.classList.toggle("is-activo", i === actual));
      }, { passive: true });
    }
  };

  const crearTarjeta = (publicacion) => {
    const tarjeta = plantillaTarjeta.content.firstElementChild.cloneNode(true);
    const plan = publicacion.plan;
    const autor = publicacion.es_mio ? "Vos" : publicacion.autor.nombre;

    tarjeta.dataset.publicacionId = publicacion.id;

    $("[data-soc-avatar]", tarjeta).textContent =
      (publicacion.autor.nombre || "?").trim().charAt(0).toUpperCase();
    $("[data-soc-autor]", tarjeta).textContent = autor;
    $("[data-soc-autor-enlace]", tarjeta).href = publicacion.es_mio
      ? urls.miPerfil
      : urls.perfil.replace("__ID__", publicacion.autor.id);
    $("[data-soc-fecha]", tarjeta).textContent = hace(publicacion.creada_en);

    const esPublico = publicacion.visibilidad === "publico";
    const visibilidad = $("[data-soc-visibilidad]", tarjeta);
    visibilidad.title = esPublico ? "Visible para todos" : "Visible para tus amigos";
    $("[data-soc-vis-publico]", tarjeta).hidden = !esPublico;
    $("[data-soc-vis-amigos]", tarjeta).hidden = esPublico;

    pintarMedia(tarjeta, publicacion);

    $("[data-soc-plan-nombre]", tarjeta).textContent = plan.nombre;
    $("[data-soc-plan-estado]", tarjeta).textContent = plan.estado_texto;
    rellenarTexto(tarjeta, "[data-soc-plan-cuando]", cuando(plan));
    rellenarTexto(tarjeta, "[data-soc-plan-precio]", precio(plan));
    rellenarTexto(
      tarjeta,
      "[data-soc-plan-lugares]",
      plan.lugares.map((l) => l.nombre).join(" → ")
    );
    rellenarTexto(
      tarjeta,
      "[data-soc-plan-puntaje]",
      plan.promedio != null ? `★ ${plan.promedio} · ${plural(plan.votos, "voto", "votos")}` : ""
    );
    rellenarTexto(tarjeta, "[data-soc-plan-descripcion]", plan.descripcion);

    $("[data-soc-texto-autor]", tarjeta).textContent = publicacion.texto ? autor : "";
    $("[data-soc-texto]", tarjeta).textContent = publicacion.texto || "";
    $(".soc-texto", tarjeta).hidden = !publicacion.texto;

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
      tarjeta._publicacion.comentarios_previa = previaDesdeHilo(tarjeta);
      pintarPrevia(tarjeta, tarjeta._publicacion);
      return;
    }

    await cargarComentarios(tarjeta);
    pintarPrevia(tarjeta, tarjeta._publicacion);   // con el hilo abierto, la vista previa se oculta
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

  // Doble toque (o doble clic) sobre la foto: me gusta, con el corazón que
  // aparece un instante. Se detecta con dos clics seguidos y no con "dblclick"
  // porque en el celular ese evento no siempre llega.
  let ultimoToque = { tarjeta: null, instante: 0 };

  const latido = (tarjeta) => {
    const corazon = $("[data-soc-pop]", tarjeta);
    if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      corazon.classList.remove("is-pop");
      void corazon.offsetWidth;   // reinicia la animación si se toca otra vez
      corazon.classList.add("is-pop");
    }
    if (!tarjeta._publicacion.yo_di_like) darLike(tarjeta);
  };

  const toqueEnFoto = (tarjeta, instante) => {
    if (ultimoToque.tarjeta === tarjeta && instante - ultimoToque.instante < 350) {
      ultimoToque = { tarjeta: null, instante: 0 };
      latido(tarjeta);
    } else {
      ultimoToque = { tarjeta, instante };
    }
  };

  const mostrarVacioSiHaceFalta = () => {
    vacio.hidden = lista.children.length > 0 || ocupado || siguiente !== null;
  };

  const pintarTotal = (n) => {
    totalPublicaciones = Math.max(0, n);
    const elemento = $("[data-soc-total]", raiz);
    if (elemento) elemento.textContent = `(${totalPublicaciones})`;
  };

  const quitarDeVista = (tarjeta) => {
    const id = tarjeta.dataset.publicacionId;
    tarjeta.remove();
    const miniatura = miniaturas.get(id);
    if (miniatura) miniatura.remove();
    miniaturas.delete(id);
    tarjetas.delete(id);
    publicaciones.delete(id);
    if (modalPost.open) modalPost.close();
    if (totalPublicaciones !== null) pintarTotal(totalPublicaciones - 1);
    mostrarVacioSiHaceFalta();
  };

  const eliminarPublicacion = async (tarjeta) => {
    const confirmado = await window.preguntar("¿Eliminar esta publicación? El plan no se borra.");
    if (!confirmado) return;

    try {
      await pedir(
        `${urls.raiz}/publicaciones/${tarjeta.dataset.publicacionId}/eliminar`,
        {}
      );
      quitarDeVista(tarjeta);
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

  const alClic = (evento) => {
    const miniatura = evento.target.closest(".soc-miniatura");
    if (miniatura) {
      abrirPost(miniatura.dataset.publicacionId);
      return;
    }

    const tarjeta = evento.target.closest(".soc-tarjeta");
    if (!tarjeta) return;

    const boton = evento.target.closest("button");
    if (!boton) {
      if (evento.target.closest("[data-soc-media]") && !evento.target.closest("a[href]")) {
        toqueEnFoto(tarjeta, evento.timeStamp);
      }
      return;
    }

    if (boton.matches("[data-soc-like]")) darLike(tarjeta);
    else if (boton.matches("[data-soc-guardar]")) guardar(tarjeta);
    else if (boton.matches("[data-soc-proponer]")) abrirProponer(tarjeta);
    else if (boton.matches("[data-soc-comentarios], [data-soc-ver-comentarios]")) {
      alternarComentarios(tarjeta, $("[data-soc-comentarios]", tarjeta));
    } else if (boton.matches("[data-soc-eliminar]")) eliminarPublicacion(tarjeta);
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
  };

  const alEnviar = (evento) => {
    const formulario = evento.target.closest("[data-soc-form-comentar]");
    if (!formulario) return;

    evento.preventDefault();
    enviarComentario(evento.target.closest(".soc-tarjeta"), formulario);
  };

  // Las tarjetas viven en la lista o, en modo grilla, dentro del diálogo.
  for (const zona of [lista, contenedorPost]) {
    zona.addEventListener("click", alClic);
    zona.addEventListener("submit", alEnviar);
  }


  /* --- Proponer el plan a un grupo ------------------------------------------------
     Se elige un grupo y se sigue a la pantalla de "Postular idea" de ese grupo con
     el plan ya elegido. Postular exige tener el plan en Guardados, así que si todavía
     no lo está se guarda antes (es lo mismo que tocar el marcador). */

  const listaGrupos = $("[data-soc-grupos-lista]", modalGrupo);
  const grupoVacio = $("[data-soc-grupos-vacio]", modalGrupo);
  const grupoError = $("[data-soc-grupo-error]", modalGrupo);
  let gruposCargados = null;
  let tarjetaAProponer = null;

  const elegirGrupo = async (grupo, boton) => {
    const publicacion = tarjetaAProponer._publicacion;
    limpiarError(grupoError);
    boton.disabled = true;

    try {
      if (!publicacion.guardado) {
        const datos = await pedir(
          `${urls.raiz}/publicaciones/${publicacion.id}/guardar`,
          { guardar: true }
        );
        publicacion.guardado = datos.guardado;
        pintarGuardado(tarjetaAProponer, publicacion);
      }
      window.location.href =
        `${urls.postular.replace("__GID__", grupo.id)}?idea_id=${encodeURIComponent(publicacion.plan.id)}`;
    } catch (e) {
      mostrarError(grupoError, e.message);
      boton.disabled = false;
    }
  };

  const pintarGrupos = (grupos) => {
    listaGrupos.replaceChildren(
      ...grupos.map((grupo) => {
        const boton = document.createElement("button");
        boton.type = "button";
        boton.className = "soc-grupo";
        boton.textContent = grupo.nombre;
        boton.addEventListener("click", () => elegirGrupo(grupo, boton));
        return boton;
      })
    );
    grupoVacio.hidden = grupos.length > 0;
  };

  const abrirProponer = async (tarjeta) => {
    tarjetaAProponer = tarjeta;
    $("[data-soc-grupo-plan]", modalGrupo).textContent =
      `Plan: ${tarjeta._publicacion.plan.nombre}. Elegí a qué grupo se lo proponés; después ponés la fecha y el grupo lo vota.`;
    limpiarError(grupoError);
    modalGrupo.showModal();

    if (gruposCargados === null) {
      listaGrupos.replaceChildren();
      grupoVacio.hidden = true;
      try {
        gruposCargados = (await pedir(urls.grupos)).grupos;
      } catch (e) {
        mostrarError(grupoError, e.message);
        return;
      }
    }
    pintarGrupos(gruposCargados);
  };


  /* --- Grilla: miniaturas que abren la publicación en un diálogo ------------- */

  const crearMiniatura = (publicacion) => {
    const miniatura = plantillaMiniatura.content.firstElementChild.cloneNode(true);
    const imagen = $("[data-soc-mini-img]", miniatura);
    const portada = $("[data-soc-mini-portada]", miniatura);

    miniatura.dataset.publicacionId = publicacion.id;
    miniatura.setAttribute("aria-label", `Ver publicación: ${publicacion.plan.nombre}`);

    if (publicacion.fotos.length > 0) {
      imagen.src = urls.fotos + publicacion.fotos[0];
      imagen.hidden = false;
    } else {
      portada.className = `soc-mini-portada soc-portada-${varianteDe(publicacion)}`;
      portada.textContent = publicacion.plan.nombre;
      portada.hidden = false;
    }
    $("[data-soc-mini-varias]", miniatura).hidden = publicacion.fotos.length < 2;

    publicaciones.set(publicacion.id, publicacion);
    miniaturas.set(publicacion.id, miniatura);
    actualizarMiniatura(publicacion);
    return miniatura;
  };

  const abrirPost = (id) => {
    const publicacion = publicaciones.get(id);
    if (!publicacion) return;

    let tarjeta = tarjetas.get(id);
    if (!tarjeta) {
      tarjeta = crearTarjeta(publicacion);
      tarjetas.set(id, tarjeta);
    }
    contenedorPost.replaceChildren(tarjeta);
    if (!modalPost.open) modalPost.showModal();
  };

  // Si el evento "close" llega después de haber abierto otra publicación, no
  // se vacía el diálogo: solo se limpia cuando de verdad quedó cerrado.
  modalPost.addEventListener("close", () => {
    if (!modalPost.open) contenedorPost.replaceChildren();
  });


  /* --- Cargar el feed ------------------------------------------------------ */

  const cargarPagina = async () => {
    if (ocupado) return;

    ocupado = true;
    cargando.hidden = false;
    botonMas.hidden = true;
    limpiarError(avisoGeneral);

    const parametros = new URLSearchParams(
      autorId ? { autor: autorId } : { pestana: raiz.dataset.pestana }
    );
    if (siguiente) parametros.set("antes", siguiente);

    try {
      const datos = await pedir(`${urls.feed}?${parametros}`);

      lista.append(...datos.publicaciones.map(modoGrilla ? crearMiniatura : crearTarjeta));
      siguiente = datos.hay_mas ? datos.siguiente : null;

      if (datos.total != null) pintarTotal(datos.total);
    } catch (e) {
      mostrarError(avisoGeneral, e.message);
    }

    ocupado = false;
    cargando.hidden = true;
    botonMas.hidden = siguiente === null;
    mostrarVacioSiHaceFalta();
  };

  botonMas.addEventListener("click", cargarPagina);

  // Modo "unica": una publicación puntual (la página a la que llevan los avisos).
  const cargarUnica = async () => {
    botonMas.hidden = true;

    try {
      const datos = await pedir(`${urls.raiz}/publicaciones/${raiz.dataset.publicacion}`);
      const tarjeta = crearTarjeta(datos.publicacion);
      lista.append(tarjeta);
      if (raiz.dataset.abrirComentarios) {
        alternarComentarios(tarjeta, $("[data-soc-comentarios]", tarjeta));
      }
    } catch (e) {
      vacio.hidden = false;
      if (!e.message.startsWith("No encontramos")) mostrarError(avisoGeneral, e.message);
    }

    cargando.hidden = true;
  };


  /* --- Compartir un plan (solo en /social) ------------------------------------ */

  const iniciarPublicar = () => {

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
    reiniciarFotos();
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
        fotos: fotosElegidas.map((foto) => foto.dataUrl),
        aspecto: datos.get("aspecto"),
      });

      modalPublicar.close();

      // Lo propio siempre figura en la pestaña Amigos: ahí aparece arriba de
      // todo al instante. En Descubrir (grilla) solo se avisa dónde encontrarlo.
      if (!modoGrilla) {
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


  /* --- Fotos del modal ------------------------------------------------------ */

  const MAX_FOTOS = 2;
  const MAX_BYTES = 380 * 1024;   // el servidor acepta hasta 400 KB
  const LADO_MAXIMO = 1080;

  const previas = $("[data-soc-previas]", modalPublicar);
  const botonSubir = $("[data-soc-subir]", modalPublicar);
  const entradaArchivos = $("[data-soc-archivos]", modalPublicar);
  const ayudaFotos = $("[data-soc-fotos-ayuda]", modalPublicar);
  const plantillaPrevia = document.getElementById("soc-tpl-previa");

  let fotosElegidas = [];   // [{ dataUrl }]

  // Achica la imagen a un JPEG de hasta LADO_MAXIMO px y MAX_BYTES: baja la
  // calidad primero y, si hace falta, el tamaño.
  const comprimir = (archivo) => new Promise((resolver, rechazar) => {
    const origen = URL.createObjectURL(archivo);
    const imagen = new Image();

    imagen.onerror = () => {
      URL.revokeObjectURL(origen);
      rechazar(new Error("No pudimos leer una de las imágenes."));
    };

    imagen.onload = () => {
      URL.revokeObjectURL(origen);

      let escala = Math.min(1, LADO_MAXIMO / Math.max(imagen.width, imagen.height));
      let calidad = 0.85;
      const lienzo = document.createElement("canvas");

      const intentar = () => {
        lienzo.width = Math.max(1, Math.round(imagen.width * escala));
        lienzo.height = Math.max(1, Math.round(imagen.height * escala));

        const contexto = lienzo.getContext("2d");
        contexto.fillStyle = "#fff";   // el JPEG no tiene transparencia
        contexto.fillRect(0, 0, lienzo.width, lienzo.height);
        contexto.drawImage(imagen, 0, 0, lienzo.width, lienzo.height);

        lienzo.toBlob((blob) => {
          if (!blob) {
            rechazar(new Error("No pudimos procesar una de las imágenes."));
          } else if (blob.size <= MAX_BYTES) {
            const lector = new FileReader();
            lector.onload = () => resolver(lector.result);
            lector.onerror = () => rechazar(new Error("No pudimos leer una de las imágenes."));
            lector.readAsDataURL(blob);
          } else if (calidad > 0.5) {
            calidad -= 0.1;
            intentar();
          } else if (escala > 0.3) {
            escala *= 0.8;
            intentar();
          } else {
            rechazar(new Error("Una de las imágenes es demasiado pesada."));
          }
        }, "image/jpeg", calidad);
      };

      intentar();
    };

    imagen.src = origen;
  });

  const pintarPrevias = () => {
    previas.replaceChildren(
      ...fotosElegidas.map((foto, i) => {
        const previa = plantillaPrevia.content.firstElementChild.cloneNode(true);
        $("img", previa).src = foto.dataUrl;
        $("button", previa).addEventListener("click", () => {
          fotosElegidas.splice(i, 1);
          pintarPrevias();
        });
        return previa;
      })
    );
    botonSubir.hidden = fotosElegidas.length >= MAX_FOTOS;
  };

  const reiniciarFotos = () => {
    fotosElegidas = [];
    entradaArchivos.value = "";
    ayudaFotos.hidden = true;
    pintarPrevias();
  };

  entradaArchivos.addEventListener("change", async () => {
    const archivos = [...entradaArchivos.files].slice(0, MAX_FOTOS - fotosElegidas.length);
    entradaArchivos.value = "";
    ayudaFotos.hidden = true;

    botonSubir.setAttribute("aria-busy", "true");
    for (const archivo of archivos) {
      try {
        fotosElegidas.push({ dataUrl: await comprimir(archivo) });
      } catch (e) {
        ayudaFotos.textContent = e.message;
        ayudaFotos.hidden = false;
      }
    }
    botonSubir.removeAttribute("aria-busy");
    pintarPrevias();
  });


  };

  if (modalPublicar) iniciarPublicar();


  /* --- Cerrar modales con los botones "Cancelar" y la cruz ------------------ */

  document.querySelectorAll("dialog.modal [data-soc-cerrar]").forEach((boton) => {
    boton.addEventListener("click", () => boton.closest("dialog").close());
  });


  if (modoUnica) cargarUnica();
  else cargarPagina();
})();
