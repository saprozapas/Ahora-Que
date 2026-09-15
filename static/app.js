/* ==========================================================================
   AHORA QUÉ — Comportamiento de la interfaz
   --------------------------------------------------------------------------
   ÍNDICE

     01. Utilidades
     02. Barra de progreso de scroll
     03. Modo noche
     04. Menú de navegación en celular
     05. Aparición de secciones al hacer scroll
     06. Barra lateral del dashboard
     07. Máscara de fecha de nacimiento
     08. Estado "enviando" en los formularios
     09. Filtros de la página Explorar
     10. Carrusel de grupos

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
     02. BARRA DE PROGRESO DE SCROLL
     ======================================================================== */

  const iniciarBarraDeProgreso = () => {

    const barra = $(".scroll-progress span");

    if (!barra) {
      return;
    }

    let pendiente = false;

    const actualizar = () => {

      const alturaScrollable =
        document.documentElement.scrollHeight - window.innerHeight;

      const avance =
        alturaScrollable > 0 ? window.scrollY / alturaScrollable : 0;

      barra.style.transform = "scaleX(" + avance + ")";

      pendiente = false;
    };

    window.addEventListener(
      "scroll",
      () => {

        if (pendiente) {
          return;
        }

        pendiente = true;
        window.requestAnimationFrame(actualizar);
      },
      { passive: true }
    );

    actualizar();
  };


  /* ========================================================================
     03. MODO NOCHE

     El tema vive en localStorage bajo la clave "ahoraque-theme" y se
     escribe en el atributo data-theme del <html>. Todo el CSS de color
     cuelga de ese atributo.
     ======================================================================== */

  const CLAVE_TEMA = "ahoraque-theme";

  const iniciarModoNoche = () => {

    const boton = $(".theme-toggle");

    if (!boton) {
      return;
    }

    const favicon = $("#theme-favicon");
    const etiqueta = $(".theme-toggle-label", boton);

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
      const radio = Math.hypot(
        Math.max(x, window.innerWidth - x),
        Math.max(y, window.innerHeight - y)
      );

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
            easing: "cubic-bezier(0.22, 1, 0.36, 1)",
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

    const header = $(".site-header");
    const boton = $(".nav-toggle");

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
     05. APARICIÓN DE SECCIONES AL HACER SCROLL

     Regla importante: el estado de reposo es VISIBLE. Solo se marca para
     animar lo que arranca debajo del primer pantallazo. Así, si el
     JavaScript no corre, la página se ve igual de completa.
     ======================================================================== */

  const iniciarAparicionAlScroll = () => {

    if (prefiereMenosMovimiento || !("IntersectionObserver" in window)) {
      return;
    }

    const candidatos = $$(
      "main section, main article, .story-card, .contact-form, .auth-form"
    );

    const limiteVisible = window.innerHeight * 0.85;

    const aAnimar = candidatos.filter(
      (elemento) => elemento.getBoundingClientRect().top > limiteVisible
    );

    if (aAnimar.length === 0) {
      return;
    }

    const observador = new IntersectionObserver(
      (entradas) => {

        entradas.forEach((entrada) => {

          if (!entrada.isIntersecting) {
            return;
          }

          entrada.target.classList.add("is-visible");
          observador.unobserve(entrada.target);
        });
      },
      { threshold: 0.12 }
    );

    aAnimar.forEach((elemento) => {
      elemento.classList.add("scroll-reveal");
      observador.observe(elemento);
    });
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

    const barra = $(".filter-bar");
    const grilla = $(".plan-index");

    if (!barra || !grilla) {
      return;
    }

    const botones = $$(".filter-chip", barra);
    const tarjetas = $$(".index-card", grilla);
    const vacio = $(".plan-index-empty", grilla);

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
     10. CARRUSEL DE GRUPOS

     Muestra los grupos de a página: dos por vez en escritorio, uno en
     celular. Usa el atributo hidden en lugar de style.display para no
     pelear con el display:flex que define el CSS.
     ======================================================================== */

  const iniciarCarruselDeGrupos = () => {

    const grilla = $("#groupsGrid");

    if (!grilla) {
      return;
    }

    const tarjetas = $$(".group-card", grilla);
    const anterior = $("#groupsPrev");
    const siguiente = $("#groupsNext");
    const paginaActual = $("#groupsCurrentPage");
    const totalDePaginas = $("#groupsTotalPages");
    const navegacion = $(".groups-navigation");

    if (!anterior || !siguiente || !paginaActual || !totalDePaginas) {
      return;
    }

    let pagina = 0;

    const tarjetasPorPagina = () => (window.innerWidth <= 650 ? 1 : 2);

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
     ARRANQUE
     ======================================================================== */

  iniciarBarraDeProgreso();
  iniciarModoNoche();
  iniciarMenuMovil();
  iniciarAparicionAlScroll();
  iniciarBarraLateral();
  iniciarFechaDeNacimiento();
  iniciarEstadoDeEnvio();
  iniciarFiltrosDePlanes();
  iniciarCarruselDeGrupos();
})();
