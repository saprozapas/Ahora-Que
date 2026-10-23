/* ==========================================================================
   AHORA QUÉ — Comportamiento de la interfaz
   --------------------------------------------------------------------------
   ÍNDICE

     01. Utilidades
     03. Modo noche
     04. Menú de navegación en celular
     06. Barra lateral del dashboard
     07. Máscara de fecha de nacimiento
     08. Estado "enviando" en los formularios
     09. Filtros de la página Explorar
     10. Carrusel de grupos
     11. Copiar el enlace del grupo
     12. Editar Perfil
     13. Modales

   --------------------------------------------------------------------------
   NOTAS

     · Este archivo se carga con `defer`, así que el DOM ya está armado
       cuando corre. No hace falta envolver nada en DOMContentLoaded.

     · Cada bloque empieza buscando sus elementos y sale si no los
       encuentra. Eso permite tener un único archivo para todas las
       páginas sin que tiren errores las que no usan un componente.

     · El tema se aplica ANTES de este archivo, con el script chico que
       está en el <head> de base.html. Si se hiciera acá, la página
       parpadearía en blanco antes de pasar a modo noche.

   ========================================================================== */

(() => {
  "use strict";


  /* ========================================================================
     01. UTILIDADES
     ======================================================================== */

  const $ = (selector, scope = document) => scope.querySelector(selector);

  const $$ = (selector, scope = document) =>
    Array.from(scope.querySelectorAll(selector));

  const prefiereMenosMovimiento = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;


  /* ========================================================================
     03. MODO NOCHE

     El tema vive en localStorage bajo la clave "ahoraque-theme" y se
     escribe en el atributo data-theme del <html>. Todo el CSS de color
     cuelga de ese atributo.
     ======================================================================== */

  const CLAVE_TEMA = "ahoraque-theme";

  const iniciarModoNoche = () => {

    const boton = $("[data-theme-toggle]");

    if (!boton) {
      return;
    }

    const favicon = $("#theme-favicon");
    const etiqueta = $("[data-theme-label]", boton);

    /*
     * El tema vivo se guarda acá y no se lee del DOM en cada clic.
     *
     * startViewTransition() no ejecuta su callback en el momento: espera a
     * capturar la pantalla. Si se leyera data-theme al hacer clic, dos
     * clics seguidos podrían calcular el mismo destino, porque el primero
     * todavía no escribió el atributo.
     */
    let temaActual =
      document.documentElement.dataset.theme === "night" ? "night" : "light";

    const aplicarTema = (tema) => {

      const esNoche = tema === "night";

      document.documentElement.dataset.theme = esNoche ? "night" : "light";

      boton.setAttribute("aria-pressed", String(esNoche));

      boton.setAttribute(
        "aria-label",
        esNoche ? "Activar modo claro" : "Activar modo noche"
      );

      if (etiqueta) {
        etiqueta.textContent = esNoche ? "Modo claro" : "Modo noche";
      }

      // El ícono (luna / sol) lo intercambia el CSS según data-theme.

      if (favicon) {
        favicon.href = esNoche
          ? "/static/favicon-night.svg"
          : "/static/favicon.svg";
      }

      // Los logos que aparecen dentro de la página también cambian.

      $$('img[src*="favicon"]').forEach((imagen) => {

        imagen.src = esNoche
          ? imagen.src.replace("favicon.svg", "favicon-night.svg")
          : imagen.src.replace("favicon-night.svg", "favicon.svg");
      });
    };

    /*
     * La onda expansiva.
     *
     * Con la View Transitions API el navegador saca una foto de la
     * pantalla antes y después del cambio. El CSS apaga el fundido que
     * hace por defecto, y acá recortamos la foto nueva con un círculo
     * que crece desde el centro del botón hasta cubrir la esquina más
     * lejana: eso es lo que se ve como una onda.
     *
     * Si el navegador no soporta la API, o si la persona pidió menos
     * movimiento, el tema cambia igual, solo que de golpe.
     */
    const animarOnda = (cambiar) => {

      if (!document.startViewTransition || prefiereMenosMovimiento) {
        cambiar();
        return;
      }

      const caja = boton.getBoundingClientRect();
      const x = caja.left + caja.width / 2;
      const y = caja.top + caja.height / 2;

      // Distancia del botón a la esquina más lejana de la ventana.
      const distancia = Math.hypot(
        Math.max(x, window.innerWidth - x),
        Math.max(y, window.innerHeight - y)
      );

      /*
       * El círculo crece un 12% más allá de esa esquina.
       *
       * Sin ese margen, la esquina más lejana se descubre justo en el
       * último fotograma, que es donde cualquier curva de salida va más
       * lenta: se veía como si la onda se trabara ahí. Con el margen, la
       * esquina queda cubierta cuando la animación todavía va a buen
       * ritmo, y lo que sobra crece fuera de la pantalla, sin verse.
       */
      const radio = distancia * 1.12;

      const transicion = document.startViewTransition(cambiar);

      transicion.ready.then(() => {

        document.documentElement.animate(
          {
            clipPath: [
              "circle(0px at " + x + "px " + y + "px)",
              "circle(" + radio + "px at " + x + "px " + y + "px)"
            ]
          },
          {
            duration: 640,

            // Curva de arranque suave pero sin frenada brusca al final.
            // La de salida fuerte que había antes llegaba al 96% del radio
            // a mitad de camino y después se arrastraba.
            easing: "cubic-bezier(0.45, 0.05, 0.4, 1)",

            pseudoElement: "::view-transition-new(root)"
          }
        );

      }).catch(() => {
        // Si la transición se interrumpe (por ejemplo, dos clics
        // seguidos), el tema ya quedó aplicado igual.
      });
    };

    aplicarTema(temaActual);

    boton.addEventListener("click", () => {

      const siguiente = temaActual === "night" ? "light" : "night";

      // Se actualiza ya, sin esperar a que corra la transición.
      temaActual = siguiente;

      try {
        localStorage.setItem(CLAVE_TEMA, siguiente);
      } catch (error) {
        // Si el navegador bloquea el almacenamiento, el tema igual cambia
        // en esta visita; solo no se recuerda para la próxima.
      }

      animarOnda(() => aplicarTema(siguiente));
    });
  };


  /* ========================================================================
     04. MENÚ DE NAVEGACIÓN EN CELULAR

     Debajo de 900px la navegación y las acciones de cuenta se guardan en
     un panel desplegable. Sin esto, el contenido del header medía 410px
     dentro de una pantalla de 375px y se cortaba sin scroll posible.
     ======================================================================== */

  const iniciarMenuMovil = () => {

    const header = $("[data-header]");
    const boton = $("[data-menu-toggle]");

    if (!header || !boton) {
      return;
    }

    const cerrar = () => {
      header.removeAttribute("data-menu");
      boton.setAttribute("aria-expanded", "false");
      boton.setAttribute("aria-label", "Abrir menú");
    };

    const abrir = () => {
      header.setAttribute("data-menu", "abierto");
      boton.setAttribute("aria-expanded", "true");
      boton.setAttribute("aria-label", "Cerrar menú");
    };

    boton.addEventListener("click", () => {

      const estaAbierto = header.getAttribute("data-menu") === "abierto";

      if (estaAbierto) {
        cerrar();
      } else {
        abrir();
      }
    });

    // Cerrar con Escape.

    document.addEventListener("keydown", (evento) => {

      if (evento.key === "Escape") {
        cerrar();
      }
    });

    // Cerrar al tocar fuera del header.

    document.addEventListener("click", (evento) => {

      if (!header.contains(evento.target)) {
        cerrar();
      }
    });

    // Cerrar al pasar a ancho de escritorio, para no dejar el estado
    // colgado cuando el panel ya no existe.

    window.matchMedia("(min-width: 901px)").addEventListener("change", cerrar);
  };


  /* ========================================================================
     06. BARRA LATERAL DEL DASHBOARD

     Solo aplica en escritorio. En celular la barra se convierte en una
     fila de pestañas y el botón de contraer queda oculto por CSS.
     ======================================================================== */

  const iniciarBarraLateral = () => {

    $$(".dashboard-layout").forEach((layout) => {

      const boton = $(".dashboard-sidebar-toggle", layout);

      if (!boton) {
        return;
      }

      boton.addEventListener("click", () => {

        const contraida = layout.classList.toggle("is-collapsed");

        boton.setAttribute("aria-expanded", String(!contraida));

        boton.setAttribute(
          "aria-label",
          contraida ? "Expandir navegación" : "Contraer navegación"
        );

        // La flecha no cambia de carácter: el CSS la rota 180°, que se
        // lee mucho más suave que un salto de "←" a "→".
      });
    });
  };


  /* ========================================================================
     07. MÁSCARA DE FECHA DE NACIMIENTO

     El campo es de texto (no date) para poder forzar el formato
     dd/mm/aaaa que espera el backend.
     ======================================================================== */

  const iniciarFechaDeNacimiento = () => {

    const campo = $("#birth_date");

    if (!campo) {
      return;
    }

    campo.addEventListener("input", () => {

      const digitos = campo.value.replace(/\D/g, "").slice(0, 8);

      const partes = [
        digitos.slice(0, 2),
        digitos.slice(2, 4),
        digitos.slice(4, 8)
      ].filter(Boolean);

      campo.value = partes.join("/");
    });

    campo.addEventListener("blur", () => {

      const valor = campo.value;

      if (valor === "") {
        campo.setCustomValidity("");
        return;
      }

      if (!/^\d{2}\/\d{2}\/\d{4}$/.test(valor)) {

        campo.setCustomValidity(
          "Usá una fecha válida con el formato dd/mm/aaaa."
        );

        return;
      }

      const [dia, mes, anio] = valor.split("/").map(Number);

      const fecha = new Date(anio, mes - 1, dia);

      // Date() acepta 31/02 y lo corre a marzo. Comparar los tres campos
      // contra el objeto resultante descarta esas fechas inventadas.

      const esValida =
        fecha.getFullYear() === anio &&
        fecha.getMonth() === mes - 1 &&
        fecha.getDate() === dia &&
        fecha <= new Date();

      campo.setCustomValidity(
        esValida ? "" : "Ingresá una fecha de nacimiento válida y no futura."
      );
    });
  };


  /* ========================================================================
     08. ESTADO "ENVIANDO" EN LOS FORMULARIOS

     Marca el botón mientras el navegador hace el POST, para que el
     usuario vea que algo pasó y no vuelva a apretar.
     ======================================================================== */

  const iniciarEstadoDeEnvio = () => {

    $$("form").forEach((formulario) => {

      formulario.addEventListener("submit", () => {

        if (!formulario.checkValidity()) {
          return;
        }

        const boton = $('button[type="submit"], button:not([type])', formulario);

        if (boton) {
          boton.setAttribute("aria-busy", "true");
        }
      });
    });
  };


  /* ========================================================================
     09. FILTROS DE LA PÁGINA EXPLORAR

     Filtrado del lado del cliente sobre los planes ya renderizados. Los
     botones anteriores no tenían ningún comportamiento asociado.
     ======================================================================== */

  const iniciarFiltrosDePlanes = () => {

    const barra = $("[data-filtros]");
    const grilla = $("[data-planes]");

    if (!barra || !grilla) {
      return;
    }

    const botones = $$("[data-filtro]", barra);
    const tarjetas = $$("[data-tipo]", grilla);
    const vacio = $("[data-vacio]");

    if (botones.length === 0 || tarjetas.length === 0) {
      return;
    }

    const aplicarFiltro = (filtro) => {

      let visibles = 0;

      tarjetas.forEach((tarjeta) => {

        const coincide = filtro === "todos" || tarjeta.dataset.tipo === filtro;

        tarjeta.hidden = !coincide;

        if (coincide) {
          visibles += 1;
        }
      });

      if (vacio) {
        vacio.hidden = visibles > 0;
      }
    };

    botones.forEach((boton) => {

      boton.addEventListener("click", () => {

        botones.forEach((otro) => {
          otro.setAttribute("aria-pressed", String(otro === boton));
        });

        aplicarFiltro(boton.dataset.filtro);
      });
    });
  };


  /* ========================================================================
     10a. AVISOS DE VOTACIÓN DEL INICIO ("Te toca a vos")

     El panel se vuelve a pedir al servidor cada pocos segundos (y al volver a la pestaña), así que una
     votación nueva de cualquier grupo aparece sola. Son solo avisos: cada tarjeta lleva al grupo, donde
     se vota, se elige el horario o se puntúa.
     ======================================================================== */

  const iniciarPendientes = () => {

    const cuerpo = $("[data-pend]");

    if (!cuerpo) {
      return;
    }

    const url = cuerpo.dataset.url;
    const intervalo = Number(cuerpo.dataset.intervalo) || 8000;
    const contador = $("[data-pend-contador]");
    const nav = $("[data-pend-nav]");
    const etiquetaPagina = $("[data-pend-pagina]");

    let ultimo = cuerpo.innerHTML.trim();
    let pidiendo = false;

    const pista = () => $(".pend-lista", cuerpo);

    // Las votaciones van en una fila que se recorre hacia los costados: de a tres, dos o una según el ancho.
    const paso = () => {
      const fila = pista();
      return fila ? fila.clientWidth + parseFloat(getComputedStyle(fila).columnGap || 0) : 1;
    };

    const actualizarContador = (total) => {

      if (!contador) {
        return;
      }

      contador.textContent = total;
      contador.hidden = !Number(total);
    };

    const actualizarNavegacion = () => {

      const fila = pista();

      if (!nav) {
        return;
      }

      const desborda = Boolean(fila) && fila.scrollWidth > fila.clientWidth + 2;
      nav.hidden = !desborda;

      if (!desborda) {
        return;
      }

      const paginas = Math.max(1, Math.round(fila.scrollWidth / paso()));
      const actual = Math.min(paginas, Math.round(fila.scrollLeft / paso()) + 1);

      etiquetaPagina.textContent = actual + " de " + paginas;
      $("[data-pend-prev]", nav).disabled = fila.scrollLeft <= 2;
      $("[data-pend-next]", nav).disabled = fila.scrollLeft + fila.clientWidth >= fila.scrollWidth - 2;
    };

    const refrescar = async () => {

      if (pidiendo || document.hidden) {
        return;
      }

      pidiendo = true;

      try {

        const respuesta = await fetch(url, { cache: "no-store", credentials: "same-origin", headers: { "X-Requested-With": "fetch" } });

        if (respuesta.status === 401) {
          window.location.href = "/login";
          return;
        }

        if (!respuesta.ok) {
          return;
        }

        const html = (await respuesta.text()).trim();
        actualizarContador(respuesta.headers.get("X-Pendientes") || 0);

        if (html === ultimo) {
          return;
        }

        const antes = new Set($$("[data-pend-clave]", cuerpo).map((item) => item.dataset.pendClave));
        const desplazado = pista() ? pista().scrollLeft : 0;

        cuerpo.innerHTML = html;
        ultimo = html;

        // La fila sigue en la misma página después de actualizarse.
        if (pista() && desplazado) {
          pista().scrollLeft = desplazado;
        }

        $$("[data-pend-clave]", cuerpo).forEach((item) => {
          if (!antes.has(item.dataset.pendClave)) {
            item.classList.add("is-nueva");
          }
        });

        actualizarNavegacion();

        if (window.AQDistancia) {
          window.AQDistancia.actualizar();
        }

      } catch (error) {
        // Sin conexión por un rato: se reintenta en el próximo ciclo.
      } finally {
        pidiendo = false;
      }
    };

    const anterior = nav && $("[data-pend-prev]", nav);
    const siguiente = nav && $("[data-pend-next]", nav);

    if (anterior && siguiente) {
      anterior.addEventListener("click", () => pista() && pista().scrollBy({ left: -paso(), behavior: "smooth" }));
      siguiente.addEventListener("click", () => pista() && pista().scrollBy({ left: paso(), behavior: "smooth" }));
    }

    // "scroll" no burbujea: se escucha en la fase de captura para enterarse del de la fila.
    cuerpo.addEventListener("scroll", actualizarNavegacion, true);
    window.addEventListener("resize", actualizarNavegacion);
    actualizarNavegacion();

    setInterval(refrescar, intervalo);

    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) {
        refrescar();
      }
    });

    window.addEventListener("online", refrescar);
  };


  /* ========================================================================
     10b. PISTAS DE PLANES DEL GRUPO

     Cada sección del tablero (en votación, confirmados…) es una fila que
     se recorre hacia los costados: de a dos planes en escritorio y tablet y
     de a uno en celular. Las flechas mueven una página; también se
     puede arrastrar o deslizar. Sin desborde, la navegación se oculta.
     ======================================================================== */

  const iniciarPistasDePlanes = () => {

    $$("[data-carrusel]").forEach((seccion) => {

      const pista = $("[data-pista]", seccion);
      const nav = $("[data-pista-nav]", seccion);
      const anterior = $("[data-pista-prev]", seccion);
      const siguiente = $("[data-pista-next]", seccion);
      const etiqueta = $("[data-pista-pagina]", seccion);

      if (!pista || !nav || !anterior || !siguiente) {
        return;
      }

      const paso = () => pista.clientWidth + parseFloat(getComputedStyle(pista).columnGap || 0);

      const actualizar = () => {

        const desborda = pista.scrollWidth > pista.clientWidth + 2;
        nav.hidden = !desborda;

        const paginas = Math.max(1, Math.round(pista.scrollWidth / paso()));
        const actual = Math.min(paginas, Math.round(pista.scrollLeft / paso()) + 1);

        if (etiqueta) {
          etiqueta.textContent = actual + " de " + paginas;
        }

        anterior.disabled = pista.scrollLeft <= 2;
        siguiente.disabled = pista.scrollLeft + pista.clientWidth >= pista.scrollWidth - 2;
      };

      anterior.addEventListener("click", () => pista.scrollBy({ left: -paso(), behavior: "smooth" }));
      siguiente.addEventListener("click", () => pista.scrollBy({ left: paso(), behavior: "smooth" }));

      pista.addEventListener("scroll", actualizar, { passive: true });
      window.addEventListener("resize", actualizar);

      actualizar();
    });
  };


  /* ========================================================================
     10. CARRUSEL DE GRUPOS

     Muestra los grupos de a página: tres en escritorio, dos en tablet,
     uno en celular — los mismos tres escalones que usa la grilla de
     .groups-grid en el CSS. Usa el atributo hidden en lugar de
     style.display para no pelear con el display:flex que define el CSS.
     ======================================================================== */

  const iniciarCarruselDeGrupos = () => {

    const grilla = $("#groupsGrid");

    if (!grilla) {
      return;
    }

    const tarjetas = $$("[data-grupo]", grilla);
    const anterior = $("#groupsPrev");
    const siguiente = $("#groupsNext");
    const paginaActual = $("#groupsCurrentPage");
    const totalDePaginas = $("#groupsTotalPages");
    const navegacion = $("[data-grupos-nav]");

    if (!anterior || !siguiente || !paginaActual || !totalDePaginas) {
      return;
    }

    let pagina = 0;

    // Los mismos cortes que .groups-list en el CSS: 1 / 2 / 3 columnas.
    const tarjetasPorPagina = () => {

      if (window.innerWidth <= 650) {
        return 1;
      }

      if (window.innerWidth <= 900) {
        return 2;
      }

      return 3;
    };

    const conDosDigitos = (numero) => String(numero).padStart(2, "0");

    const renderizar = () => {

      const porPagina = tarjetasPorPagina();
      const paginas = Math.max(1, Math.ceil(tarjetas.length / porPagina));

      if (pagina > paginas - 1) {
        pagina = paginas - 1;
      }

      const desde = pagina * porPagina;
      const hasta = desde + porPagina;

      tarjetas.forEach((tarjeta, indice) => {
        tarjeta.hidden = indice < desde || indice >= hasta;
      });

      paginaActual.textContent = conDosDigitos(pagina + 1);
      totalDePaginas.textContent = conDosDigitos(paginas);

      anterior.disabled = pagina === 0;
      siguiente.disabled = pagina >= paginas - 1;

      if (navegacion) {
        navegacion.hidden = paginas <= 1;
      }
    };

    anterior.addEventListener("click", () => {

      if (pagina > 0) {
        pagina -= 1;
        renderizar();
      }
    });

    siguiente.addEventListener("click", () => {

      const porPagina = tarjetasPorPagina();
      const paginas = Math.ceil(tarjetas.length / porPagina);

      if (pagina < paginas - 1) {
        pagina += 1;
        renderizar();
      }
    });

    // Al cambiar el ancho cambia la cantidad de tarjetas por página, así
    // que hay que recalcular. No se resetea a la primera página: se
    // mantiene la actual y renderizar() la acota si quedó fuera de rango.

    window.addEventListener("resize", renderizar);

    renderizar();
  };


    /* ========================================================================
     11. COPIAR EL ENLACE DEL GRUPO

     Copia la dirección de la página al portapapeles y confirma en el
     propio botón. Es la forma de invitar gente mientras no exista un
     sistema de invitaciones en el backend.
     ======================================================================== */

  const iniciarCopiarEnlace = () => {

    const boton = $("[data-copiar-enlace]");

    if (!boton) {
      return;
    }

    const etiqueta = $("[data-copiar-texto]", boton) || boton;
    const textoOriginal = etiqueta.textContent;
    let volverATexto = null;

    const confirmar = (mensaje) => {

      etiqueta.textContent = mensaje;

      clearTimeout(volverATexto);
      volverATexto = setTimeout(() => {
        etiqueta.textContent = textoOriginal;
      }, 2200);
    };

    const copiar = async (texto) => {

      try {
        await navigator.clipboard.writeText(texto);
        return true;
      } catch (error) {
        // Se intenta con el metodo de reserva.
      }

      try {
        const campo = document.createElement("textarea");

        campo.value = texto;
        campo.setAttribute("readonly", "");
        campo.style.cssText = "position:fixed;top:0;left:-9999px;opacity:0";

        document.body.appendChild(campo);
        campo.select();

        const copiado = document.execCommand("copy");
        campo.remove();

        return copiado;
      } catch (error) {
        return false;
      }
    };

    boton.addEventListener("click", async () => {

      const copiado = await copiar(window.location.href);

      confirmar(copiado ? "Enlace copiado" : "No se pudo copiar");
    });
  };

  /* ========================================================================
     12. MODALES

     Se apoyan en <dialog> nativo (showModal / close), que da gratis el
     cierre con Escape y el foco atrapado adentro mientras está abierto.
     Lo único que hace falta escribir a mano es:

       · abrirlo desde el botón que lo dispara
       · cerrarlo al tocar afuera (el clic cae sobre el propio <dialog>,
         que es lo que ocupa toda la "cortina" detrás del contenido)
       · devolver el foco al botón que lo abrió, al cerrarse

     Los botones de ADENTRO del modal (cerrar, cancelar, confirmar) no
     necesitan JS: viven en un <form method="dialog">, así que cualquier
     click ahí cierra el modal solo, sin mandar nada a ningún lado.
     ======================================================================== */

  const iniciarModales = () => {

    // Un mismo <dialog> puede tener varios disparadores (por ejemplo "Invitar a
    // un grupo" en cada fila de amigos): se guarda cuál lo abrió, para devolverle
    // el foco a ESE al cerrar.
    const abrir = (dialogo, disparador) => {

      dialogo._disparador = disparador;
      dialogo.showModal();

      // En los diálogos con formulario el foco va al primer campo y no al
      // botón de cerrar, que es lo primero que aparece en el HTML.
      const campo = dialogo.querySelector(
        '[autofocus], input:not([type="hidden"]):not([type="radio"]):not([type="checkbox"]):not([type="file"]), textarea, select'
      );

      if (campo && !campo.disabled) {
        campo.focus();
      }
    };

    $$("[data-modal-open]").forEach((disparador) => {

      const dialogo = document.getElementById(disparador.dataset.modalOpen);

      if (!dialogo) {
        return;
      }

      disparador.addEventListener("click", () => abrir(dialogo, disparador));

      if (!dialogo.dataset.cierreListo) {

        dialogo.dataset.cierreListo = "1";

        dialogo.addEventListener("close", () => {
          const origen = dialogo._disparador;

          if (origen && document.contains(origen)) {
            origen.focus();
          }
        });
      }
    });

    // Botones de cerrar/cancelar adentro de un diálogo (sin handlers en línea).
    document.addEventListener("click", (evento) => {
      const cerrar = evento.target.closest("[data-cerrar-dialogo]");

      if (cerrar) {
        cerrar.closest("dialog")?.close();
      }
    });

    $$("dialog.modal").forEach((dialogo) => {

      dialogo.addEventListener("click", (evento) => {

        if (evento.target === dialogo) {
          dialogo.close();
        }
      });
    });
  };

  /* Reemplazo de confirm() y alert() con el mismo <dialog class="modal".
     preguntar(msg) -> Promise<boolean>; preguntar(msg, false) es un aviso
     con solo "Aceptar". Escape o tocar afuera cuentan como cancelar.      */

  const preguntar = (mensaje, conCancelar = true) => new Promise((resolver) => {

    const dialogo = document.createElement("dialog");
    dialogo.className = "modal";
    dialogo.setAttribute("role", "alertdialog");
    dialogo.setAttribute("aria-labelledby", "preguntar-texto");
    dialogo.innerHTML = `
      <form method="dialog">
        <div class="modal-body"><p id="preguntar-texto"></p></div>
        <div class="modal-actions">
          ${conCancelar
            ? '<button class="btn btn--secondary" value="no" autofocus>Cancelar</button>'
            : ""}
          <button class="btn btn--primary" value="si"${conCancelar ? "" : " autofocus"}>Aceptar</button>
        </div>
      </form>`;
    $("p", dialogo).textContent = mensaje;

    dialogo.addEventListener("click", (evento) => {
      if (evento.target === dialogo) { dialogo.close(); }
    });
    dialogo.addEventListener("close", () => {
      dialogo.remove();
      resolver(dialogo.returnValue === "si" || !conCancelar);
    });

    document.body.append(dialogo);
    dialogo.showModal();
  });

  window.preguntar = preguntar;


      /* ========================================================================
     13. CAMPOS EDITABLES DEL PERFIL
     ======================================================================== */

  const iniciarCamposEditables = () => {

    const mostrarError = (formulario, mensaje) => {
      const parrafo = formulario.querySelector('[data-role="error"]');
      if (!parrafo) return;
      parrafo.textContent = mensaje || "";
      parrafo.hidden = !mensaje;
    };

    const manejarEnvio = (formulario, alGuardar) => {
      formulario.addEventListener("submit", async (evento) => {
        evento.preventDefault();

        const boton = formulario.querySelector('[type="submit"]');
        if (boton) boton.setAttribute("aria-busy", "true");

        try {
          const respuesta = await fetch(formulario.action, {
            method: "POST",
            headers: { "X-Requested-With": "XMLHttpRequest" },
            body: new FormData(formulario),
          });

          const datos = await respuesta.json();
          alGuardar(datos);
        } catch (error) {
          alGuardar({ ok: false, error: "No se pudo guardar. Probá de nuevo." });
        } finally {
          if (boton) boton.removeAttribute("aria-busy");
        }
      });
    };

    // Nombre, username y descripción: alternan entre vista y edición.
    document.querySelectorAll(".field-editable").forEach((formulario) => {

      const vista = formulario.querySelector(".field-view");
      const edicion = formulario.querySelector(".field-edit");
      const botonEditar = formulario.querySelector(".field-edit-btn");
      const valorMostrado = formulario.querySelector('[data-role="value"]');
      const campo = edicion ? edicion.querySelector("input, textarea") : null;

      if (!vista || !edicion || !botonEditar) return;

      botonEditar.addEventListener("click", () => {
        vista.hidden = true;
        edicion.hidden = false;
        if (campo) campo.focus();
      });

      manejarEnvio(formulario, (datos) => {
        if (datos.ok) {
          if (valorMostrado) {
            valorMostrado.textContent = datos.value || valorMostrado.dataset.empty || "";
            valorMostrado.classList.toggle("is-empty", !datos.value);
          }
          mostrarError(formulario, "");
          edicion.hidden = true;
          vista.hidden = false;
        } else {
          mostrarError(formulario, datos.error);
        }
      });
    });
  };


  /* ========================================================================
     14. BUSCADOR DE AMIGOS

     Debounce sobre el input de /amigos: manda la búsqueda a
     /amigos/buscar y arma la lista de resultados. El botón "Agregar"
     manda la solicitud por fetch, sin recargar la página, y se
     deshabilita apenas se envía.
     ======================================================================== */

  const iniciarBuscarAmigos = () => {

    const contenedor = $("[data-friend-search]");
    if (!contenedor) return;

    const input = $("#buscar-amigos-input", contenedor);
    const resultados = $("#buscar-amigos-resultados", contenedor);

    if (!input || !resultados) return;

    let temporizador = null;
    let controlador = null;

    const etiquetaEstado = (usuario) => {

      if (usuario.ya_amigos) {
        return { texto: "Ya son amigos", deshabilitado: true };
      }

      if (usuario.solicitud_enviada) {
        return { texto: "Solicitud enviada", deshabilitado: true };
      }

      if (usuario.solicitud_recibida) {
        return { texto: "Te invitó · revisá tu inbox", deshabilitado: true };
      }

      return { texto: "Agregar", deshabilitado: false };
    };

    const renderizarResultados = (usuarios) => {

      resultados.innerHTML = "";

      if (usuarios.length === 0) {
        const vacio = document.createElement("p");
        vacio.className = "friend-result__empty";
        vacio.textContent = "No encontramos a nadie con ese nombre o usuario.";
        resultados.appendChild(vacio);
        resultados.hidden = false;
        return;
      }

      usuarios.forEach((usuario) => {

        const fila = document.createElement("div");
        fila.className = "friend-result";

        const identidad = document.createElement("a");
        identidad.className = "friend-result__who";
        identidad.href = `/usuarios/${usuario.id}`;

        const avatar = document.createElement("span");
        avatar.className = "avatar";
        // El mismo tono que en el resto de la app: sale del largo del nombre.
        avatar.style.setProperty("--h", String(((usuario.nombre || "").length * 47) % 360));
        avatar.style.setProperty("--size", "36px");
        avatar.setAttribute("aria-hidden", "true");
        avatar.textContent = (usuario.nombre || "?").slice(0, 1).toUpperCase();

        const nombres = document.createElement("span");
        nombres.className = "friend-result__names";

        const nombre = document.createElement("strong");
        nombre.textContent = usuario.nombre;
        nombres.appendChild(nombre);

        if (usuario.username) {
          const username = document.createElement("small");
          username.textContent = `@${usuario.username}`;
          nombres.appendChild(username);
        }

        identidad.appendChild(avatar);
        identidad.appendChild(nombres);

        const estado = etiquetaEstado(usuario);

        const boton = document.createElement("button");
        boton.type = "button";
        boton.className = "btn btn--secondary btn--sm";
        boton.textContent = estado.texto;
        boton.disabled = estado.deshabilitado;

        if (!estado.deshabilitado) {
          boton.addEventListener("click", async () => {

            boton.disabled = true;
            boton.textContent = "Enviando…";

            try {
              const respuesta = await fetch(input.dataset.solicitarUrl, {
                method: "POST",
                headers: {
                  "X-Requested-With": "XMLHttpRequest",
                  "Content-Type": "application/x-www-form-urlencoded",
                },
                body: `user_id=${encodeURIComponent(usuario.id)}`,
              });

              const datos = await respuesta.json();

              if (datos.ok) {
                boton.textContent = datos.estado === "amigos" ? "Ya son amigos" : "Solicitud enviada";
              } else {
                boton.disabled = false;
                boton.textContent = datos.error || "Reintentar";
              }
            } catch (error) {
              boton.disabled = false;
              boton.textContent = "Reintentar";
            }
          });
        }

        fila.appendChild(identidad);
        fila.appendChild(boton);
        resultados.appendChild(fila);
      });

      resultados.hidden = false;
    };

    const buscar = async (consulta) => {

      if (controlador) controlador.abort();
      controlador = new AbortController();

      try {
        const respuesta = await fetch(
          `${input.dataset.buscarUrl}?q=${encodeURIComponent(consulta)}`,
          { signal: controlador.signal }
        );
        const datos = await respuesta.json();
        renderizarResultados(datos.resultados || []);
      } catch (error) {
        // Búsqueda cancelada por una más nueva, o error de red: no hacemos nada.
      }
    };

    input.addEventListener("input", () => {

      const consulta = input.value.trim();

      clearTimeout(temporizador);

      if (consulta.length < 2) {
        resultados.hidden = true;
        resultados.innerHTML = "";
        return;
      }

      temporizador = setTimeout(() => buscar(consulta), 300);
    });

    document.addEventListener("click", (evento) => {
      if (!contenedor.contains(evento.target)) {
        resultados.hidden = true;
      }
    });
  };


  /* ========================================================================
     15. INVITAR A UN AMIGO A UN GRUPO

     El modal es único y se reutiliza para cualquier amigo: al abrirlo
     desde su botón se actualiza a qué URL apunta el form y el nombre
     que aparece en el título.
     ======================================================================== */

  const iniciarInvitarAmigoAGrupo = () => {

    const form = $("#modal-invitar-grupo-form");
    const nombreSpan = $("#modal-invitar-grupo-nombre");

    $$("[data-invite-url]").forEach((boton) => {

      boton.addEventListener("click", () => {
        if (form) form.action = boton.dataset.inviteUrl;
        if (nombreSpan) nombreSpan.textContent = boton.dataset.friendName || "tu amigo";
      });
    });

    const buscador = $("[data-buscar-en-modal-grupos]");
    const lista = $$(".modal-group-item");
    const vacio = $("#modal-invitar-grupo-vacio");

    if (!buscador || lista.length === 0) return;

    buscador.addEventListener("input", () => {

      const consulta = buscador.value.trim().toLowerCase();
      let visibles = 0;

      lista.forEach((item) => {

        const coincide = item.dataset.nombreGrupo.includes(consulta);
        item.closest("li").hidden = !coincide;

        if (coincide) visibles += 1;
      });

      if (vacio) vacio.hidden = visibles !== 0;
    });
  };


  /* ========================================================================
     16. ELIMINAR AMIGO

     Confirmación antes de mandar el form, usando el mensaje que trae
     el propio form en data-confirmar.
     ======================================================================== */

  const iniciarConfirmaciones = () => {

    $$("form[data-confirmar]").forEach((formulario) => {

      formulario.addEventListener("submit", async (evento) => {

        if (formulario.dataset.ok) {
          return;
        }

        evento.preventDefault();

        if (await preguntar(formulario.dataset.confirmar)) {
          formulario.dataset.ok = "1";
          formulario.requestSubmit(evento.submitter);
        } else {
          // El estado "enviando" (08) ya marcó el botón antes de preguntar.
          $("[aria-busy]", formulario)?.removeAttribute("aria-busy");
        }
      });
    });
  };


  /* ========================================================================
     MENÚS DESPLEGABLES (<details class="idea-menu">)

     Se cierran con Escape (y el foco vuelve al botón) y al tocar afuera.
     ======================================================================== */

  const iniciarMenusDesplegables = () => {

    const menus = $$("details.idea-menu");
    if (!menus.length) return;

    menus.forEach((menu) => {
      menu.addEventListener("keydown", (evento) => {
        if (evento.key === "Escape" && menu.open) {
          menu.open = false;
          $("summary", menu)?.focus();
        }
      });
    });

    document.addEventListener("click", (evento) => {
      menus.forEach((menu) => {
        if (menu.open && !menu.contains(evento.target)) menu.open = false;
      });
    });
  };


  /* ========================================================================
     AVISOS (flash)

     base.html los pinta en .flash-stack. Acá se les agrega la cruz y se
     van solos; si el mouse está encima, esperan a que salga.
     ======================================================================== */

  const iniciarAvisos = () => {

    const pila = $(".flash-stack");
    if (!pila) return;

    const cerrar = (aviso) => {

      if (aviso.classList.contains("is-leaving")) return;
      aviso.classList.add("is-leaving");

      setTimeout(() => {
        aviso.remove();
        if (!pila.children.length) pila.remove();
      }, prefiereMenosMovimiento ? 0 : 420);
    };

    $$(".flash-message", pila).forEach((aviso, indice) => {

      const boton = document.createElement("button");
      boton.type = "button";
      boton.className = "flash-message-cerrar";
      boton.setAttribute("aria-label", "Cerrar aviso");
      boton.textContent = "×";
      boton.addEventListener("click", () => cerrar(aviso));
      aviso.appendChild(boton);

      let temporizador = setTimeout(() => cerrar(aviso), 4500 + indice * 600);

      aviso.addEventListener("mouseenter", () => clearTimeout(temporizador));
      aviso.addEventListener("mouseleave", () => {
        temporizador = setTimeout(() => cerrar(aviso), 2000);
      });
    });
  };


  /* ========================================================================
     ACTUALIZACIÓN AUTOMÁTICA (pantalla de un grupo)

     Si alguien propone un plan, vota o responde una encuesta, no hace falta
     apretar F5: la pantalla pregunta cada tanto al servidor y, si el contenido
     cambió, se recarga sola. No lo hace cuando:
       - la pestaña está en segundo plano;
       - hay un diálogo abierto;
       - la persona tocó algún formulario (para no borrarle lo que escribió).
     Al recargar vuelve a la misma posición. Se activa con data-autorecarga="ms"
     en el contenedor del contenido.
     ======================================================================== */

  const iniciarActualizacionAutomatica = () => {

    const zona = $("[data-autorecarga]");
    if (!zona) return;

    const cada = Math.max(5000, Number(zona.dataset.autorecarga) || 15000);
    const clave = `ahoraque-scroll:${location.pathname}`;

    // Vuelve a donde estaba antes de la recarga automática.
    try {
      const guardado = sessionStorage.getItem(clave);
      if (guardado !== null) {
        zona.scrollTop = Number(guardado) || 0;
        sessionStorage.removeItem(clave);
      }
    } catch (error) {
      // Sin sessionStorage solo se pierde la posición.
    }

    let sucio = false;
    const marcar = (evento) => {
      if (evento.isTrusted && evento.target.closest("form")) sucio = true;
    };
    document.addEventListener("input", marcar);
    document.addEventListener("change", marcar);

    // Huella del contenido tal como lo manda el servidor (sin scripts ni avisos).
    const huella = (html) => {
      const doc = new DOMParser().parseFromString(html, "text/html");
      const contenido = doc.querySelector("[data-autorecarga]");
      if (!contenido) return null;
      contenido.querySelectorAll("script, [data-ignorar-recarga]").forEach((el) => el.remove());
      return contenido.innerHTML.replace(/\s+/g, " ");
    };

    const traer = async () => {
      const respuesta = await fetch(location.href, {
        credentials: "same-origin",
        cache: "no-store",
        headers: { "X-Requested-With": "autorecarga" },
      });
      if (!respuesta.ok || respuesta.redirected) return null;
      return huella(await respuesta.text());
    };

    let base = null;
    let revisando = false;

    const revisar = async () => {
      if (revisando || document.hidden || sucio || $("dialog[open]")) return;
      revisando = true;
      try {
        const nueva = await traer();
        if (nueva === null) return;
        if (base === null) {
          base = nueva;
        } else if (nueva !== base && !sucio && !$("dialog[open]")) {
          try {
            sessionStorage.setItem(clave, String(zona.scrollTop));
          } catch (error) {
            // Sin sessionStorage vuelve arriba.
          }
          location.reload();
        }
      } catch (error) {
        // Sin conexión: se vuelve a intentar en la próxima vuelta.
      } finally {
        revisando = false;
      }
    };

    revisar();
    setInterval(revisar, cada);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) revisar();
    });
  };


  /* ========================================================================
     ARRANQUE
     ======================================================================== */

  iniciarModoNoche();
  iniciarMenuMovil();
  iniciarBarraLateral();
  iniciarFechaDeNacimiento();
  iniciarEstadoDeEnvio();
  iniciarFiltrosDePlanes();
  iniciarCarruselDeGrupos();
  iniciarPistasDePlanes();
  iniciarPendientes();
  iniciarCopiarEnlace();
  iniciarCamposEditables();
  iniciarModales();
  iniciarBuscarAmigos();
  iniciarInvitarAmigoAGrupo();
  iniciarConfirmaciones();
  iniciarAvisos();
  iniciarMenusDesplegables();
  iniciarActualizacionAutomatica();
})();