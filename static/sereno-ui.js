/* ==========================================================================
   Componentes de interfaz estilo Sereno (ver sereno-ui.css)

     1) Menú desplegable propio: se arma solo para cada <select> de la página
        (menos los que tengan data-nativo). El <select> original queda adentro,
        sincronizado: al elegir se dispara su evento "change", así el código que
        ya lo escuchaba no se entera de la diferencia.

     2) SerenoUI.autocompletar(campo, opciones): lista de sugerencias debajo de
        un campo de texto mientras se escribe.

     3) Selector de fecha y de hora propios: reemplazan solos a cada
        <input type="date"> y <input type="time"> (menos los que tengan data-nativo).

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

  /* ======================================================================
     3) Selector de fecha y de hora
        Reemplazan a <input type="date"> y <input type="time"> (los de cada
        navegador son difíciles de usar). El <input> real sigue en el
        formulario, oculto: mantiene el name, el valor en formato ISO ("2026-10-25",
        "20:30"), min, max y required, y se le dispara "change" al elegir.
     ====================================================================== */

  const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  const MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const DIAS_SEMANA = ["L", "M", "M", "J", "V", "S", "D"];
  const DIAS_CORTOS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
  const ICONO_CALENDARIO =
    '<svg class="ss-icono" viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/></svg>';
  const ICONO_RELOJ =
    '<svg class="ss-icono" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>';

  const dos = (n) => String(n).padStart(2, "0");
  const aIso = (d) => `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())}`;
  const deIso = (texto) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(texto || "");
    return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : null;
  };
  const sumarDias = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);

  /* El botón visible, el panel flotante y todo lo común a la fecha y la hora. */
  const armarSelector = (input, { icono, vacio, texto, construir, alAbrir }) => {
    if (input.dataset.ssListo || input.dataset.nativo !== undefined) return;
    input.dataset.ssListo = "1";

    const n = ++contador;
    const envoltura = crear("div", "ss ss-selector");
    input.parentNode.insertBefore(envoltura, input);
    envoltura.appendChild(input);

    input.classList.add("ss-nativo");
    input.tabIndex = -1;
    input.setAttribute("aria-hidden", "true");

    const boton = crear("button", "ss-boton", {
      type: "button",
      id: `ss-boton-${n}`,
      "aria-haspopup": "dialog",
      "aria-expanded": "false",
    });
    const valor = crear("span", "ss-valor");
    boton.appendChild(valor);
    boton.insertAdjacentHTML("beforeend", icono);

    const panel = crear("div", "ss-lista ss-panel", { id: `ss-panel-${n}`, role: "dialog" });
    panel.hidden = true;
    envoltura.append(boton, panel);

    const etiqueta = input.id ? document.querySelector(`label[for="${CSS.escape(input.id)}"]`) : null;
    if (etiqueta) {
      if (!etiqueta.id) etiqueta.id = `ss-etiqueta-${n}`;
      boton.setAttribute("aria-labelledby", `${etiqueta.id} ${boton.id}`);
      panel.setAttribute("aria-labelledby", etiqueta.id);
      etiqueta.addEventListener("click", (evento) => {
        evento.preventDefault();
        boton.focus();
      });
    } else if (input.getAttribute("aria-label")) {
      boton.setAttribute("aria-label", input.getAttribute("aria-label"));
      panel.setAttribute("aria-label", input.getAttribute("aria-label"));
    }

    const refrescar = () => {
      const mostrado = texto(input.value);
      valor.textContent = mostrado || vacio;
      valor.classList.toggle("es-vacio", !mostrado);
      boton.disabled = input.disabled;
      if (mostrado) boton.classList.remove("es-invalido");
    };

    const abierto = () => !panel.hidden;

    // El panel es más alto que una lista de opciones: se acomoda abajo del botón o arriba, donde entre.
    const colocar = () => {
      const r = boton.getBoundingClientRect();
      const margen = 6;
      const ancho = Math.min(panel.offsetWidth || 300, window.innerWidth - 16);
      const alto = panel.offsetHeight;
      const abajo = window.innerHeight - r.bottom - margen - 8;
      const arriba = r.top - margen - 8;
      const haciaArriba = alto > abajo && arriba > abajo;
      panel.style.left = `${Math.max(8, Math.min(r.left, window.innerWidth - ancho - 8))}px`;
      panel.style.top = haciaArriba
        ? `${Math.max(8, r.top - margen - alto)}px`
        : `${Math.max(8, Math.min(r.bottom + margen, window.innerHeight - alto - 8))}px`;
    };

    const alMover = (evento) => {
      if (evento && evento.type === "scroll" && panel.contains(evento.target)) return;
      cerrar();
    };
    const fuera = (evento) => {
      if (!envoltura.contains(evento.target)) cerrar();
    };

    const cerrar = (devolverFoco = false) => {
      if (!abierto()) return;
      panel.hidden = true;
      envoltura.removeAttribute("data-abierto");
      boton.setAttribute("aria-expanded", "false");
      document.removeEventListener("pointerdown", fuera, true);
      window.removeEventListener("resize", alMover);
      window.removeEventListener("scroll", alMover, true);
      if (devolverFoco) boton.focus();
    };

    const elegir = (nuevo) => {
      const cambio = input.value !== nuevo;
      input.value = nuevo;
      refrescar();
      cerrar(true);
      if (cambio) {
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
      }
    };

    const api = { input, panel, elegir, cerrar, colocar, refrescar };

    const abrir = () => {
      if (abierto() || boton.disabled) return;
      construir(api);
      panel.hidden = false;
      envoltura.setAttribute("data-abierto", "");
      boton.setAttribute("aria-expanded", "true");
      colocar();
      alAbrir(api);
      document.addEventListener("pointerdown", fuera, true);
      window.addEventListener("resize", alMover);
      window.addEventListener("scroll", alMover, true);
    };
    api.abrir = abrir;
    api.alturaCambio = colocar;

    boton.addEventListener("click", () => (abierto() ? cerrar() : abrir()));
    boton.addEventListener("keydown", (evento) => {
      if (evento.key === "ArrowDown" && !abierto()) {
        evento.preventDefault();
        abrir();
      }
    });
    envoltura.addEventListener("keydown", (evento) => {
      if (evento.key === "Escape" && abierto()) {
        evento.preventDefault();
        evento.stopPropagation();   // que no cierre también un diálogo que lo contenga
        cerrar(true);
      } else if (evento.key === "Tab" && abierto()) {
        // Tab saca el foco del panel: se cierra (el foco sigue su camino natural).
        setTimeout(() => {
          if (!envoltura.contains(document.activeElement)) cerrar();
        }, 0);
      }
    });
    panel.addEventListener("pointerdown", (evento) => {
      if (!evento.target.closest("button")) evento.preventDefault();
    });

    // Un campo obligatorio vacío: en vez del aviso nativo, el botón se marca y recibe el foco.
    input.addEventListener("invalid", (evento) => {
      evento.preventDefault();
      boton.classList.add("es-invalido");
      // Con varios campos vacíos el navegador avisa uno por uno: el foco va al primero.
      const formulario = input.form || document;
      if (Date.now() - (formulario.__ssInvalido || 0) > 100) boton.focus();
      formulario.__ssInvalido = Date.now();
    });
    input.addEventListener("change", refrescar);
    if (input.form) input.form.addEventListener("reset", () => setTimeout(refrescar, 0));
    new MutationObserver(refrescar).observe(input, { attributes: true, attributeFilter: ["disabled"] });

    refrescar();
  };

  /* --- Fecha: calendario del mes con atajos (Hoy, Mañana, el próximo sábado y domingo) --- */

  const mejorarFecha = (input) => {
    let vista = null;   // primer día del mes que se está mirando

    const limites = () => ({ min: deIso(input.min), max: deIso(input.max) });
    const permitido = (d) => {
      const { min, max } = limites();
      return !(min && d < min) && !(max && d > max);
    };

    const texto = (valor) => {
      const d = deIso(valor);
      if (!d) return "";
      const anio = d.getFullYear() !== new Date().getFullYear() ? ` ${d.getFullYear()}` : "";
      return `${DIAS_CORTOS[d.getDay()]} ${d.getDate()} ${MESES_CORTOS[d.getMonth()]}${anio}`;
    };

    const construir = (api) => {
      const { panel } = api;
      const hoy = new Date();
      hoy.setHours(0, 0, 0, 0);
      const elegida = deIso(input.value);
      if (!vista) {
        const base = elegida || (permitido(hoy) ? hoy : limites().min || hoy);
        vista = new Date(base.getFullYear(), base.getMonth(), 1);
      }

      panel.classList.add("sd-panel");
      panel.replaceChildren();

      // Atajos: el sábado y el domingo que vienen son los días más pedidos.
      const rapidos = crear("div", "sd-rapidos");
      const proximo = (diaSemana) => sumarDias(hoy, (diaSemana - hoy.getDay() + 7) % 7 || 7);
      [["Hoy", hoy], ["Mañana", sumarDias(hoy, 1)], ["Sáb", proximo(6)], ["Dom", proximo(0)]].forEach(([nombre, fecha]) => {
        const b = crear("button", "sd-rapido", { type: "button" });
        b.textContent = nombre;
        b.disabled = !permitido(fecha);
        b.addEventListener("click", () => api.elegir(aIso(fecha)));
        rapidos.appendChild(b);
      });

      const cabecera = crear("div", "sd-cabecera");
      const anterior = crear("button", "sd-flecha", { type: "button", "aria-label": "Mes anterior" });
      anterior.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14.5 6-6 6 6 6"/></svg>';
      const siguiente = crear("button", "sd-flecha", { type: "button", "aria-label": "Mes siguiente" });
      siguiente.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6"/></svg>';
      const titulo = crear("strong", "sd-titulo", { "aria-live": "polite" });
      titulo.textContent = `${MESES[vista.getMonth()]} ${vista.getFullYear()}`;
      cabecera.append(anterior, titulo, siguiente);

      const { min, max } = limites();
      anterior.disabled = !!min && new Date(vista.getFullYear(), vista.getMonth(), 0) < min;
      siguiente.disabled = !!max && new Date(vista.getFullYear(), vista.getMonth() + 1, 1) > max;
      anterior.addEventListener("click", () => {
        vista = new Date(vista.getFullYear(), vista.getMonth() - 1, 1);
        construir(api);
        api.panel.querySelector(".sd-dia:not(:disabled)")?.focus();
      });
      siguiente.addEventListener("click", () => {
        vista = new Date(vista.getFullYear(), vista.getMonth() + 1, 1);
        construir(api);
        api.panel.querySelector(".sd-dia:not(:disabled)")?.focus();
      });

      const grilla = crear("div", "sd-grilla", { role: "group", "aria-label": titulo.textContent });
      DIAS_SEMANA.forEach((letra) => {
        const c = crear("span", "sd-semana", { "aria-hidden": "true" });
        c.textContent = letra;
        grilla.appendChild(c);
      });
      const primero = (vista.getDay() + 6) % 7;   // la semana arranca el lunes
      for (let i = 0; i < primero; i++) grilla.appendChild(crear("span", "sd-hueco", { "aria-hidden": "true" }));
      const total = new Date(vista.getFullYear(), vista.getMonth() + 1, 0).getDate();
      for (let dia = 1; dia <= total; dia++) {
        const fecha = new Date(vista.getFullYear(), vista.getMonth(), dia);
        const b = crear("button", "sd-dia", { type: "button", "data-fecha": aIso(fecha) });
        b.textContent = String(dia);
        b.setAttribute("aria-label", `${DIAS_CORTOS[fecha.getDay()]} ${dia} de ${MESES[fecha.getMonth()]}`);
        if (aIso(fecha) === aIso(hoy)) b.classList.add("es-hoy");
        if (elegida && aIso(fecha) === aIso(elegida)) b.setAttribute("aria-pressed", "true");
        b.disabled = !permitido(fecha);
        b.addEventListener("click", () => api.elegir(aIso(fecha)));
        grilla.appendChild(b);
      }

      // Flechas: ±1 día y ±1 semana; AvPág y RePág cambian de mes.
      grilla.addEventListener("keydown", (evento) => {
        const actual = evento.target.closest(".sd-dia");
        if (!actual) return;
        const pasos = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
        let destino = null;
        if (evento.key in pasos) destino = sumarDias(deIso(actual.dataset.fecha), pasos[evento.key]);
        else if (evento.key === "PageDown" || evento.key === "PageUp") {
          const d = deIso(actual.dataset.fecha);
          destino = new Date(d.getFullYear(), d.getMonth() + (evento.key === "PageDown" ? 1 : -1), d.getDate());
        }
        if (!destino || !permitido(destino)) return;
        evento.preventDefault();
        if (destino.getMonth() !== vista.getMonth() || destino.getFullYear() !== vista.getFullYear()) {
          vista = new Date(destino.getFullYear(), destino.getMonth(), 1);
          construir(api);
        }
        api.panel.querySelector(`[data-fecha="${aIso(destino)}"]`)?.focus();
      });

      panel.append(rapidos, cabecera, grilla);

      if (!input.required) {
        const pie = crear("div", "sd-pie");
        const borrar = crear("button", "sd-borrar", { type: "button" });
        borrar.textContent = "Borrar";
        borrar.addEventListener("click", () => api.elegir(""));
        pie.appendChild(borrar);
        panel.appendChild(pie);
      }
    };

    armarSelector(input, {
      icono: ICONO_CALENDARIO,
      vacio: "Elegí un día",
      texto,
      construir: (api) => {
        vista = null;
        construir(api);
      },
      alAbrir: (api) => {
        (api.panel.querySelector('.sd-dia[aria-pressed="true"]:not(:disabled)')
          || api.panel.querySelector(".sd-dia.es-hoy:not(:disabled)")
          || api.panel.querySelector(".sd-dia:not(:disabled)"))?.focus();
      },
    });
  };

  /* --- Hora: primero la hora (24 botones), después los minutos (de 5 en 5) --- */

  const mejorarHora = (input) => {
    const texto = (valor) => (/^\d{1,2}:\d{2}/.test(valor || "") ? valor.slice(0, 5).replace(/^(\d):/, "0$1:") : "");

    const rejilla = (panel, items, columnas, clase, alElegir, elegido) => {
      const grilla = crear("div", `sh-grilla ${clase}`, { role: "group" });
      grilla.style.setProperty("--columnas", String(columnas));
      items.forEach((item) => {
        const b = crear("button", "sh-opcion", { type: "button" });
        b.textContent = item;
        if (item === elegido) b.setAttribute("aria-pressed", "true");
        b.addEventListener("click", () => alElegir(item));
        grilla.appendChild(b);
      });
      grilla.addEventListener("keydown", (evento) => {
        const botones = [...grilla.children];
        const i = botones.indexOf(document.activeElement);
        if (i < 0) return;
        const pasos = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -columnas, ArrowDown: columnas };
        if (!(evento.key in pasos)) return;
        const destino = botones[i + pasos[evento.key]];
        if (destino) {
          evento.preventDefault();
          destino.focus();
        }
      });
      panel.appendChild(grilla);
      return grilla;
    };

    const mostrarHoras = (api) => {
      const { panel } = api;
      panel.classList.add("sh-panel");
      panel.replaceChildren();
      const actual = texto(input.value);
      const titulo = crear("p", "sh-titulo");
      titulo.textContent = "Hora";
      panel.appendChild(titulo);
      const horas = Array.from({ length: 24 }, (_, h) => dos(h));
      const grilla = rejilla(panel, horas, 6, "sh-horas", (hora) => mostrarMinutos(api, hora), actual.slice(0, 2));
      if (!input.required) agregarBorrar(api);
      api.alturaCambio();
      return grilla;
    };

    const mostrarMinutos = (api, hora) => {
      const { panel } = api;
      panel.replaceChildren();
      const cabecera = crear("div", "sh-cabecera");
      const volver = crear("button", "sd-flecha", { type: "button", "aria-label": "Cambiar la hora" });
      volver.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14.5 6-6 6 6 6"/></svg>';
      volver.addEventListener("click", () => mostrarHoras(api).querySelector(".sh-opcion")?.focus());
      const titulo = crear("strong", "sd-titulo");
      titulo.textContent = `${hora}:__ — elegí los minutos`;
      cabecera.append(volver, titulo);
      panel.appendChild(cabecera);
      const minutos = Array.from({ length: 12 }, (_, i) => dos(i * 5));
      const actual = texto(input.value);
      const grilla = rejilla(panel, minutos, 4, "sh-minutos", (m) => api.elegir(`${hora}:${m}`), actual.startsWith(hora) ? actual.slice(3) : "");
      api.alturaCambio();
      (grilla.querySelector('[aria-pressed="true"]') || grilla.firstElementChild)?.focus();
    };

    const agregarBorrar = (api) => {
      const pie = crear("div", "sd-pie");
      const borrar = crear("button", "sd-borrar", { type: "button" });
      borrar.textContent = "Borrar";
      borrar.addEventListener("click", () => api.elegir(""));
      pie.appendChild(borrar);
      api.panel.appendChild(pie);
    };

    armarSelector(input, {
      icono: ICONO_RELOJ,
      vacio: "Hora",
      texto,
      construir: (api) => mostrarHoras(api),
      alAbrir: (api) => {
        (api.panel.querySelector('.sh-opcion[aria-pressed="true"]') || api.panel.querySelector(".sh-opcion"))?.focus();
      },
    });
  };

  /* ====================================================================== */

  const mejorarTodo = (raiz = document) => {
    raiz.querySelectorAll("select").forEach(mejorarSelect);
    raiz.querySelectorAll('input[type="date"]').forEach(mejorarFecha);
    raiz.querySelectorAll('input[type="time"]').forEach(mejorarHora);
  };

  window.SerenoUI = { mejorarSelect, mejorarFecha, mejorarHora, mejorarTodo, autocompletar };

  const iniciar = () => {
    mejorarTodo();
    // Selects que aparezcan después (contenido armado por JavaScript).
    new MutationObserver((cambios) => {
      for (const c of cambios) {
        c.addedNodes.forEach((nodo) => {
          if (nodo.nodeType !== 1) return;
          if (nodo.matches("select")) mejorarSelect(nodo);
          else if (nodo.matches('input[type="date"]')) mejorarFecha(nodo);
          else if (nodo.matches('input[type="time"]')) mejorarHora(nodo);
          else mejorarTodo(nodo);
        });
      }
    }).observe(document.body, { childList: true, subtree: true });
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();
