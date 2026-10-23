/* ==========================================================================
   Componentes de interfaz estilo Sereno (ver sereno-ui.css)

     1) Menú desplegable propio: se arma solo para cada <select> de la página
        (menos los que tengan data-nativo). El <select> original queda adentro,
        sincronizado: al elegir se dispara su evento "change", así el código que
        ya lo escuchaba no se entera de la diferencia.

     2) SerenoUI.autocompletar(campo, opciones): lista de sugerencias debajo de
        un campo de texto mientras se escribe.

   Todo el texto de las personas entra con textContent, nunca como HTML.
   ========================================================================== */

(() => {
  "use strict";

  let contador = 0;

  const ICONO_FLECHA =
    '<svg class="ss-flecha" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>';
  const ICONO_CHECK =
    '<svg class="ss-check" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';

  const crear = (etiqueta, clase, atributos = {}) => {
    const el = document.createElement(etiqueta);
    if (clase) el.className = clase;
    for (const [k, v] of Object.entries(atributos)) el.setAttribute(k, v);
    return el;
  };

  const sinTildes = (texto) =>
    [...String(texto || "").toLowerCase()].map((c) => c.normalize("NFD")[0]).join("");

  /* Pone una lista fija debajo de su ancla (o arriba, si abajo no entra). */
  const posicionar = (lista, ancla) => {
    const r = ancla.getBoundingClientRect();
    const margen = 6;
    const abajo = window.innerHeight - r.bottom - margen - 8;
    const arriba = r.top - margen - 8;
    const alto = Math.min(lista.scrollHeight + 2, 300);
    const haciaArriba = alto > abajo && arriba > abajo;

    lista.style.minWidth = `${r.width}px`;
    lista.style.maxWidth = `${Math.max(r.width, Math.min(480, window.innerWidth - 16))}px`;
    lista.style.left = `${Math.max(8, Math.min(r.left, window.innerWidth - lista.offsetWidth - 8))}px`;
    lista.style.maxHeight = `${Math.max(120, Math.min(300, haciaArriba ? arriba : abajo))}px`;
    lista.style.top = haciaArriba
      ? `${Math.max(8, r.top - margen - Math.min(alto, arriba))}px`
      : `${r.bottom + margen}px`;
  };

  /* ======================================================================
     1) Menú desplegable
     ====================================================================== */

  const mejorarSelect = (select) => {
    if (select.dataset.ssListo || select.multiple || select.dataset.nativo !== undefined) return;
    select.dataset.ssListo = "1";

    const n = ++contador;
    const envoltura = crear("div", "ss");
    select.parentNode.insertBefore(envoltura, select);
    envoltura.appendChild(select);

    select.classList.add("ss-nativo");
    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");

    const boton = crear("button", "ss-boton", {
      type: "button",
      id: `ss-boton-${n}`,
      role: "combobox",
      "aria-haspopup": "listbox",
      "aria-expanded": "false",
      "aria-controls": `ss-lista-${n}`,
    });
    const valor = crear("span", "ss-valor");
    boton.appendChild(valor);
    boton.insertAdjacentHTML("beforeend", ICONO_FLECHA);

    const lista = crear("ul", "ss-lista", { id: `ss-lista-${n}`, role: "listbox", tabindex: "-1" });
    lista.hidden = true;

    envoltura.append(boton, lista);

    // El nombre accesible sale de la <label> asociada (o del aria-label del select).
    const etiqueta = select.id ? document.querySelector(`label[for="${CSS.escape(select.id)}"]`) : null;
    if (etiqueta) {
      if (!etiqueta.id) etiqueta.id = `ss-etiqueta-${n}`;
      boton.setAttribute("aria-labelledby", `${etiqueta.id} ${boton.id}`);
      etiqueta.addEventListener("click", (evento) => {
        evento.preventDefault();
        boton.focus();
      });
    } else if (select.getAttribute("aria-label")) {
      boton.setAttribute("aria-label", select.getAttribute("aria-label"));
    }

    let opciones = [];   // [{ valor, texto, deshabilitada, el }]
    let activa = -1;
    let buscado = "";
    let temporizador = null;

    const construir = () => {
      lista.replaceChildren();
      opciones = [...select.options].map((o, i) => {
        const el = crear("li", "ss-opcion", { role: "option", id: `ss-${n}-${i}` });
        const texto = crear("span");
        texto.textContent = o.textContent.trim();
        el.append(texto);
        el.insertAdjacentHTML("beforeend", ICONO_CHECK);
        if (o.disabled) el.setAttribute("aria-disabled", "true");
        lista.appendChild(el);
        return { valor: o.value, texto: o.textContent.trim(), deshabilitada: o.disabled, el };
      });
    };

    const refrescar = () => {
      const elegida = select.selectedIndex;
      opciones.forEach((o, i) => o.el.setAttribute("aria-selected", String(i === elegida)));
      const actual = opciones[elegida];
      valor.textContent = actual ? actual.texto : "";
      // Una opción con valor vacío ("Cualquiera", "Todos los tipos") se ve como sugerencia.
      valor.classList.toggle("es-vacio", !actual || actual.valor === "");
      boton.disabled = select.disabled;
    };

    const marcarActiva = (i, desplazar = true) => {
      activa = i;
      opciones.forEach((o, k) => o.el.toggleAttribute("data-activa", k === i));
      if (i >= 0) {
        boton.setAttribute("aria-activedescendant", opciones[i].el.id);
        if (desplazar) opciones[i].el.scrollIntoView({ block: "nearest" });
      } else {
        boton.removeAttribute("aria-activedescendant");
      }
    };

    const abierto = () => !lista.hidden;

    const cerrar = (devolverFoco = false) => {
      if (!abierto()) return;
      lista.hidden = true;
      envoltura.removeAttribute("data-abierto");
      boton.setAttribute("aria-expanded", "false");
      marcarActiva(-1);
      document.removeEventListener("pointerdown", fuera, true);
      window.removeEventListener("resize", alMover);
      window.removeEventListener("scroll", alMover, true);
      if (devolverFoco) boton.focus();
    };

    const alMover = (evento) => {
      // Al desplazar la propia lista no hay que cerrar.
      if (evento && evento.type === "scroll" && lista.contains(evento.target)) return;
      cerrar();
    };

    const fuera = (evento) => {
      if (!envoltura.contains(evento.target)) cerrar();
    };

    const abrir = () => {
      if (abierto() || boton.disabled) return;
      lista.hidden = false;
      envoltura.setAttribute("data-abierto", "");
      boton.setAttribute("aria-expanded", "true");
      posicionar(lista, boton);
      marcarActiva(Math.max(select.selectedIndex, 0));
      document.addEventListener("pointerdown", fuera, true);
      window.addEventListener("resize", alMover);
      window.addEventListener("scroll", alMover, true);
    };

    const elegir = (i) => {
      const o = opciones[i];
      if (!o || o.deshabilitada) return;
      const cambio = select.selectedIndex !== i;
      select.selectedIndex = i;
      refrescar();
      cerrar(true);
      if (cambio) {
        select.dispatchEvent(new Event("input", { bubbles: true }));
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
    };

    const mover = (paso) => {
      let i = activa;
      do {
        i += paso;
      } while (i >= 0 && i < opciones.length && opciones[i].deshabilitada);
      if (i >= 0 && i < opciones.length) marcarActiva(i);
    };

    boton.addEventListener("click", () => (abierto() ? cerrar() : abrir()));

    boton.addEventListener("keydown", (evento) => {
      const tecla = evento.key;

      if (tecla === "ArrowDown" || tecla === "ArrowUp") {
        evento.preventDefault();
        if (!abierto()) abrir();
        else mover(tecla === "ArrowDown" ? 1 : -1);
      } else if (tecla === "Home" || tecla === "End") {
        if (abierto()) {
          evento.preventDefault();
          marcarActiva(tecla === "Home" ? 0 : opciones.length - 1);
        }
      } else if (tecla === "Enter" || tecla === " ") {
        evento.preventDefault();
        if (abierto()) elegir(activa);
        else abrir();
      } else if (tecla === "Escape") {
        if (abierto()) {
          evento.preventDefault();
          evento.stopPropagation();   // que no cierre también un diálogo que lo contenga
          cerrar(true);
        }
      } else if (tecla === "Tab") {
        cerrar();
      } else if (tecla.length === 1 && !evento.ctrlKey && !evento.metaKey && !evento.altKey) {
        // Escribir una letra salta a la primera opción que empieza así.
        buscado += sinTildes(tecla);
        clearTimeout(temporizador);
        temporizador = setTimeout(() => (buscado = ""), 600);
        const desde = Math.max(activa, 0) + (buscado.length === 1 ? 1 : 0);
        const orden = [...opciones.keys()].map((_, k) => (k + desde) % opciones.length);
        const hallada = orden.find((i) => !opciones[i].deshabilitada && sinTildes(opciones[i].texto).startsWith(buscado));
        if (hallada !== undefined) {
          if (!abierto()) abrir();
          marcarActiva(hallada);
        }
      }
    });

    lista.addEventListener("pointerdown", (evento) => evento.preventDefault());   // no quita el foco del botón
    lista.addEventListener("click", (evento) => {
      const el = evento.target.closest(".ss-opcion");
      if (el) elegir(opciones.findIndex((o) => o.el === el));
    });
    lista.addEventListener("pointermove", (evento) => {
      const el = evento.target.closest(".ss-opcion");
      if (el) marcarActiva(opciones.findIndex((o) => o.el === el), false);
    });

    // Cambios hechos desde afuera: el código que cambia el select, reset del formulario, disabled.
    select.addEventListener("change", refrescar);
    select.addEventListener("sereno:actualizar", () => {
      construir();
      refrescar();
    });
    if (select.form) select.form.addEventListener("reset", () => setTimeout(refrescar, 0));
    new MutationObserver(refrescar).observe(select, { attributes: true, attributeFilter: ["disabled"] });

    construir();
    refrescar();
  };

  /* ======================================================================
     2) Sugerencias al escribir
     ====================================================================== */

  /* Devuelve el texto con la parte que coincide con `consulta` resaltada (sin tildes ni mayúsculas). */
  const resaltar = (texto, consulta) => {
    const fragmento = document.createDocumentFragment();
    const i = consulta ? sinTildes(texto).indexOf(sinTildes(consulta)) : -1;
    if (i < 0) {
      fragmento.append(texto);
      return fragmento;
    }
    const marca = crear("mark");
    marca.textContent = texto.slice(i, i + consulta.length);
    fragmento.append(texto.slice(0, i), marca, texto.slice(i + consulta.length));
    return fragmento;
  };

  /*
    SerenoUI.autocompletar(campo, {
      buscar:     async (texto, senal) => [item, ...]   obligatorio
      describir:  (item) => { titulo, detalle?, etiqueta?, deshabilitado? }
      alElegir:   (item) => {}
      minimo:     caracteres antes de buscar (1)
      retardo:    ms de espera tras la última tecla (200)
      vacio:      texto cuando no hay resultados
      limpiar:    vaciar el campo al elegir (true)
    }
    Devuelve { cerrar, buscar } por si hace falta controlarlo desde afuera.
  */
  const autocompletar = (campo, config) => {
    const { buscar, describir, alElegir } = config;
    const minimo = config.minimo ?? 1;
    const retardo = config.retardo ?? 200;
    const vacio = config.vacio ?? "No hay resultados.";
    const limpiar = config.limpiar ?? true;

    const n = ++contador;
    const lista = crear("ul", "ac-lista", { id: `ac-lista-${n}`, role: "listbox" });
    lista.hidden = true;
    campo.insertAdjacentElement("afterend", lista);

    campo.setAttribute("role", "combobox");
    campo.setAttribute("aria-autocomplete", "list");
    campo.setAttribute("aria-expanded", "false");
    campo.setAttribute("aria-controls", lista.id);
    campo.setAttribute("autocomplete", "off");

    let items = [];
    let activa = -1;
    let secuencia = 0;
    let control = null;
    let espera = null;

    const abierta = () => !lista.hidden;

    const marcar = (i, desplazar = true) => {
      activa = i;
      [...lista.querySelectorAll(".ac-opcion")].forEach((el, k) => el.toggleAttribute("data-activa", k === i));
      const el = lista.querySelectorAll(".ac-opcion")[i];
      if (el) {
        campo.setAttribute("aria-activedescendant", el.id);
        if (desplazar) el.scrollIntoView({ block: "nearest" });
      } else {
        campo.removeAttribute("aria-activedescendant");
      }
    };

    const cerrar = () => {
      if (!abierta()) return;
      lista.hidden = true;
      campo.setAttribute("aria-expanded", "false");
      campo.removeAttribute("aria-activedescendant");
      activa = -1;
      window.removeEventListener("resize", reposicionar);
      window.removeEventListener("scroll", reposicionar, true);
    };

    const reposicionar = (evento) => {
      if (evento && evento.type === "scroll" && lista.contains(evento.target)) return;
      if (abierta()) posicionar(lista, campo);
    };

    const abrir = () => {
      if (!abierta()) {
        lista.hidden = false;
        campo.setAttribute("aria-expanded", "true");
        window.addEventListener("resize", reposicionar);
        window.addEventListener("scroll", reposicionar, true);
      }
      posicionar(lista, campo);
    };

    const estado = (texto) => {
      lista.replaceChildren();
      const li = crear("li", "ac-estado", { role: "presentation" });
      li.textContent = texto;
      lista.appendChild(li);
      items = [];
      marcar(-1);
      abrir();
    };

    const pintar = (resultado, consulta) => {
      items = resultado;
      lista.replaceChildren();

      if (!items.length) {
        estado(vacio);
        return;
      }

      items.forEach((item, i) => {
        const d = describir(item);
        const li = crear("li", "ac-opcion", { role: "option", id: `ac-${n}-${i}` });
        if (d.deshabilitado) li.setAttribute("aria-disabled", "true");

        const bloque = crear("span", "ac-texto");
        const titulo = crear("span", "ac-titulo");
        titulo.append(resaltar(d.titulo, consulta));
        bloque.appendChild(titulo);
        if (d.detalle) {
          const detalle = crear("span", "ac-detalle");
          detalle.textContent = d.detalle;
          bloque.appendChild(detalle);
        }
        li.appendChild(bloque);
        if (d.etiqueta) {
          const etiqueta = crear("span", "ac-etiqueta");
          etiqueta.textContent = d.etiqueta;
          li.appendChild(etiqueta);
        }
        lista.appendChild(li);
      });

      marcar(-1);
      abrir();
    };

    const consultar = async () => {
      const texto = campo.value.trim();
      if (texto.length < minimo) {
        cerrar();
        return;
      }

      const mia = ++secuencia;
      if (control) control.abort();
      control = new AbortController();
      if (!abierta()) estado("Buscando…");

      try {
        const resultado = await buscar(texto, control.signal);
        if (mia === secuencia) pintar(resultado, texto);
      } catch (error) {
        if (error.name === "AbortError" || mia !== secuencia) return;
        estado("No se pudo buscar. Intentá de nuevo.");
      }
    };

    const programar = () => {
      clearTimeout(espera);
      espera = setTimeout(consultar, retardo);
    };

    const elegir = (i) => {
      const item = items[i];
      if (!item || describir(item).deshabilitado) return;
      alElegir(item);
      if (limpiar) campo.value = "";
      cerrar();
    };

    campo.addEventListener("input", programar);

    campo.addEventListener("focus", () => {
      if (items.length && campo.value.trim().length >= minimo) abrir();
    });

    campo.addEventListener("blur", () => setTimeout(cerrar, 120));

    campo.addEventListener("keydown", (evento) => {
      const tecla = evento.key;
      const hay = abierta() && items.length > 0;

      if (tecla === "ArrowDown" || tecla === "ArrowUp") {
        if (!hay) {
          if (tecla === "ArrowDown") consultar();
          return;
        }
        evento.preventDefault();
        const total = items.length;
        marcar(tecla === "ArrowDown" ? (activa + 1) % total : (activa - 1 + total) % total);
      } else if (tecla === "Enter" && hay && activa >= 0) {
        evento.preventDefault();
        elegir(activa);
      } else if (tecla === "Escape" && abierta()) {
        evento.preventDefault();
        evento.stopPropagation();
        cerrar();
      } else if (tecla === "Tab") {
        cerrar();
      }
    });

    lista.addEventListener("pointerdown", (evento) => evento.preventDefault());   // el campo no pierde el foco
    lista.addEventListener("click", (evento) => {
      const el = evento.target.closest(".ac-opcion");
      if (el) elegir([...lista.querySelectorAll(".ac-opcion")].indexOf(el));
    });
    lista.addEventListener("pointermove", (evento) => {
      const el = evento.target.closest(".ac-opcion");
      if (el) marcar([...lista.querySelectorAll(".ac-opcion")].indexOf(el), false);
    });

    return { cerrar, buscar: consultar };
  };

  /* ====================================================================== */

  const mejorarTodo = (raiz = document) => {
    raiz.querySelectorAll("select").forEach(mejorarSelect);
  };

  window.SerenoUI = { mejorarSelect, mejorarTodo, autocompletar };

  const iniciar = () => {
    mejorarTodo();
    // Selects que aparezcan después (contenido armado por JavaScript).
    new MutationObserver((cambios) => {
      for (const c of cambios) {
        c.addedNodes.forEach((nodo) => {
          if (nodo.nodeType !== 1) return;
          if (nodo.matches("select")) mejorarSelect(nodo);
          else mejorarTodo(nodo);
        });
      }
    }).observe(document.body, { childList: true, subtree: true });
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();
