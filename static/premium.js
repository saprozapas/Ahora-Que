/* ==========================================================================
   Premium: planes (/premium) y pago de demostración (/premium/pagar)

   Lo que se escribe en el formulario de pago NUNCA sale del navegador: los campos no tienen "name" y no hay
   ninguna llamada a la red. Al confirmar solo se envía al servidor el método elegido y la frecuencia.
   ========================================================================== */

(function () {

  "use strict";

  var reducir = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function $(selector, raiz) { return (raiz || document).querySelector(selector); }
  function $$(selector, raiz) { return Array.prototype.slice.call((raiz || document).querySelectorAll(selector)); }

  function miles(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, "."); }
  function pesos(n) { return "$ " + miles(n); }

  function animar(el, texto) {
    if (!el || el.textContent === texto) { return; }
    el.textContent = texto;
    if (reducir) { return; }
    el.classList.remove("prem-cambia");
    void el.offsetWidth;
    el.classList.add("prem-cambia");
  }

  // ------------------------------------------------------------------------------------------------------------
  // Frecuencia: Mensual / Anual (la comparten la pantalla de planes y la de pago)
  // ------------------------------------------------------------------------------------------------------------

  var precios = null;
  var ciclo = "mensual";
  var alCambiarCiclo = [];

  function iniciarCiclo(raizConPrecios, cicloInicial) {

    try { precios = JSON.parse(raizConPrecios.getAttribute("data-precios")); } catch (e) { precios = null; }
    ciclo = cicloInicial === "anual" ? "anual" : "mensual";

    $$("[data-ciclo-selector]").forEach(function (selector) {
      $$("[data-ciclo-op]", selector).forEach(function (boton) {
        boton.addEventListener("click", function () { fijarCiclo(boton.getAttribute("data-ciclo-op")); });
      });
    });

    fijarCiclo(ciclo, true);
  }

  function fijarCiclo(nuevo, inicial) {

    ciclo = nuevo;

    $$("[data-ciclo-selector]").forEach(function (selector) {
      selector.setAttribute("data-ciclo", ciclo);
      $$("[data-ciclo-op]", selector).forEach(function (boton) {
        boton.setAttribute("aria-checked", boton.getAttribute("data-ciclo-op") === ciclo ? "true" : "false");
      });
    });

    alCambiarCiclo.forEach(function (fn) { fn(ciclo, Boolean(inicial)); });
  }

  // ------------------------------------------------------------------------------------------------------------
  // Pantalla de planes
  // ------------------------------------------------------------------------------------------------------------

  var planes = $("[data-premium-planes]");

  if (planes) {

    iniciarCiclo(planes, "mensual");

    alCambiarCiclo.push(function (c, inicial) {
      if (!precios) { return; }
      var p = precios[c];
      var monto = $("[data-precio-monto]", planes);
      var nota = $("[data-precio-nota]", planes);
      var cta = $("[data-cta-premium]", planes);
      if (inicial) {
        if (monto) { monto.textContent = pesos(p.por_mes); }
        if (nota) { nota.textContent = p.nota; }
      } else {
        animar(monto, pesos(p.por_mes));
        animar(nota, p.nota);
      }
      if (cta) { cta.setAttribute("href", "/premium/pagar?ciclo=" + c); }
    });
  }

  // ------------------------------------------------------------------------------------------------------------
  // Pantalla de pago
  // ------------------------------------------------------------------------------------------------------------

  var pago = $("[data-pago]");

  if (!pago) { return; }

  iniciarCiclo(pago, pago.getAttribute("data-ciclo"));

  // ---- Resumen
  alCambiarCiclo.push(function (c) {
    if (!precios) { return; }
    var p = precios[c];
    animar($("[data-resumen-concepto]", pago), "Premium · " + (c === "anual" ? "anual" : "mensual"));
    animar($("[data-resumen-parcial]", pago), pesos(p.total));
    animar($("[data-resumen-total]", pago), pesos(p.total));
    var texto = $("[data-confirmar-texto]", pago);
    if (texto) { texto.textContent = "Activar Premium · " + pesos(p.total); }
    pago.setAttribute("data-ciclo", c);
    var oculto = $("#pago-enviar input[name='ciclo']");
    if (oculto) { oculto.value = c; }
  });
  fijarCiclo(ciclo, true);

  // ---- Marcas de tarjeta: cómo se detectan y qué formato tienen
  var MARCAS = {
    visa:       { nombre: "Visa",             largos: [13, 16, 19], grupos: [4, 4, 4, 4, 4], cvc: 3 },
    mastercard: { nombre: "Mastercard",       largos: [16],         grupos: [4, 4, 4, 4],    cvc: 3 },
    amex:       { nombre: "American Express", largos: [15],         grupos: [4, 6, 5],       cvc: 4 },
    discover:   { nombre: "Discover",         largos: [16, 19],      grupos: [4, 4, 4, 4, 4], cvc: 3 },
    diners:     { nombre: "Diners Club",      largos: [14, 16, 19],  grupos: [4, 6, 4, 5],    cvc: 3 },
    jcb:        { nombre: "JCB",              largos: [16, 19],      grupos: [4, 4, 4, 4, 4], cvc: 3 },
    unionpay:   { nombre: "UnionPay",         largos: [16, 17, 18, 19], grupos: [4, 4, 4, 4, 4], cvc: 3 },
    maestro:    { nombre: "Maestro",          largos: [12, 13, 14, 15, 16, 17, 18, 19], grupos: [4, 4, 4, 4, 4], cvc: 3 },
    generica:   { nombre: "Tarjeta",          largos: [13, 14, 15, 16, 17, 18, 19], grupos: [4, 4, 4, 4, 4], cvc: 3 }
  };

  function detectarMarca(d) {
    if (/^4/.test(d)) { return "visa"; }
    if (/^(5[1-5]|2(2[2-9][1-9]|2[3-9]\d|[3-6]\d\d|7[01]\d|720))/.test(d)) { return "mastercard"; }
    if (/^3[47]/.test(d)) { return "amex"; }
    if (/^(6011|65|64[4-9])/.test(d)) { return "discover"; }
    if (/^3(0[0-5]|09|[68])/.test(d)) { return "diners"; }
    if (/^35(2[89]|[3-8])/.test(d)) { return "jcb"; }
    if (/^62/.test(d)) { return "unionpay"; }
    if (/^(50|5[6-9]|6[0-9])/.test(d)) { return "maestro"; }
    return "generica";
  }

  function agrupar(d, marca) {
    var grupos = MARCAS[marca].grupos;
    var partes = [];
    var i = 0;
    for (var g = 0; g < grupos.length && i < d.length; g++) {
      partes.push(d.slice(i, i + grupos[g]));
      i += grupos[g];
    }
    return partes.join(" ");
  }

  function luhn(d) {
    var suma = 0;
    for (var i = 0; i < d.length; i++) {
      var n = parseInt(d.charAt(d.length - 1 - i), 10);
      if (i % 2 === 1) { n = n * 2; if (n > 9) { n -= 9; } }
      suma += n;
    }
    return suma % 10 === 0;
  }

  function soloDigitos(t) { return String(t || "").replace(/\D/g, ""); }

  // ---- Campos: estado visual y validación
  function campoDe(input) { return input.closest(".pago-campo"); }

  function mostrar(input, mensaje, completo) {
    var campo = campoDe(input);
    var error = $("[data-error]", campo);
    campo.classList.toggle("is-error", Boolean(mensaje));
    campo.classList.toggle("is-ok", !mensaje && Boolean(completo));
    if (error) { error.textContent = mensaje || ""; }
  }

  function sacudir(input) {
    var campo = campoDe(input);
    if (reducir) { return; }
    campo.classList.remove("is-sacude");
    void campo.offsetWidth;
    campo.classList.add("is-sacude");
  }

  // Cada validador devuelve "" si está bien o el mensaje de error.
  var V = {};

  V.numero = function (valor) {
    var d = soloDigitos(valor);
    var m = MARCAS[detectarMarca(d)];
    if (!d) { return "Escribí el número de tu tarjeta."; }
    if (m.largos.indexOf(d.length) === -1 || !luhn(d)) { return "El número de tarjeta no es válido."; }
    return "";
  };

  V.nombre = function (valor) {
    return /^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .-]{2,}$/.test(String(valor).trim()) ? "" : "Poné el nombre como figura en la tarjeta.";
  };

  V.venc = function (valor) {
    var m = /^(0[1-9]|1[0-2])\/(\d{2})$/.exec(String(valor).trim());
    if (!m) { return "Usá el formato MM/AA."; }
    var hoy = new Date();
    var anio = 2000 + parseInt(m[2], 10);
    var mes = parseInt(m[1], 10);
    if (anio < hoy.getFullYear() || (anio === hoy.getFullYear() && mes < hoy.getMonth() + 1)) { return "La tarjeta está vencida."; }
    if (anio > hoy.getFullYear() + 20) { return "Revisá el año de vencimiento."; }
    return "";
  };

  V.cvc = function (valor) {
    var marca = detectarMarca(soloDigitos($("#tarjeta-numero").value));
    var largo = MARCAS[marca].cvc;
    return new RegExp("^\\d{" + largo + "}$").test(String(valor).trim()) ? "" : "El código tiene " + largo + " dígitos.";
  };

  V.banco = function (valor) { return valor ? "" : "Elegí tu banco."; };

  V.cuenta = function (valor) {
    var n = soloDigitos(valor).length;
    return n >= 6 && n <= 15 ? "" : "El número de cuenta debe tener entre 6 y 15 dígitos.";
  };

  V.ci = function (valor) {
    var d = soloDigitos(valor);
    if (d.length < 7 || d.length > 8) { return "La cédula no es válida (ej. 1.234.567-2)."; }
    d = ("00000000" + d).slice(-8);
    var pesosCi = "2987634";
    var suma = 0;
    for (var i = 0; i < 7; i++) { suma += parseInt(d.charAt(i), 10) * parseInt(pesosCi.charAt(i), 10); }
    return parseInt(d.charAt(7), 10) === (10 - (suma % 10)) % 10 ? "" : "La cédula no es válida (ej. 1.234.567-2).";
  };

  V.contacto = function (valor) {
    var t = String(valor).trim();
    if (/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(t)) { return ""; }
    var d = soloDigitos(t);
    if (d.indexOf("598") === 0 && d.length === 11) { d = "0" + d.slice(3); }
    return /^09\d{7}$/.test(d) ? "" : "Poné el email o el celular (09X XXX XXX) de tu cuenta.";
  };

  var CAMPOS = {
    tarjeta:       [["tarjeta-numero", "numero"], ["tarjeta-nombre", "nombre"], ["tarjeta-venc", "venc"], ["tarjeta-cvc", "cvc"]],
    transferencia: [["trans-banco", "banco"], ["trans-cuenta", "cuenta"], ["trans-titular", "nombre"], ["trans-ci", "ci"]],
    mercadopago:   [["mp-contacto", "contacto"]],
    applepay:      []
  };

  var tocados = {};

  function revisar(id, regla, forzar) {
    var input = document.getElementById(id);
    var mensaje = V[regla](input.value);
    var vacio = !String(input.value).trim();
    if (forzar || tocados[id]) {
      mostrar(input, mensaje, !mensaje);
    } else {
      mostrar(input, "", !mensaje && !vacio);
    }
    return mensaje;
  }

  Object.keys(CAMPOS).forEach(function (metodo) {
    CAMPOS[metodo].forEach(function (par) {
      var input = document.getElementById(par[0]);
      if (!input) { return; }
      var evento = input.tagName === "SELECT" ? "change" : "input";
      input.addEventListener(evento, function () { revisar(par[0], par[1], false); });
      input.addEventListener("blur", function () {
        if (String(input.value).trim()) { tocados[par[0]] = true; }
        revisar(par[0], par[1], false);
      });
    });
  });

  // ---- Formato con el cursor en su lugar
  function formatearEnSitio(input, formateador) {
    var pos = input.selectionStart;
    var digitosAntes = soloDigitos(input.value.slice(0, pos)).length;
    var nuevo = formateador(input.value);
    input.value = nuevo;
    var i = 0;
    var cuenta = 0;
    if (digitosAntes > 0) {
      for (i = 0; i < nuevo.length; i++) {
        if (/\d/.test(nuevo.charAt(i))) { cuenta++; }
        if (cuenta === digitosAntes) { i++; break; }
      }
    }
    try { input.setSelectionRange(i, i); } catch (e) { /* algunos teclados no lo permiten */ }
  }

  // Borrar justo después de un espacio o de una barra borra el dígito anterior, no solo el separador.
  function saltarSeparador(input) {
    input.addEventListener("keydown", function (e) {
      if (e.key !== "Backspace" || input.selectionStart !== input.selectionEnd) { return; }
      var antes = input.value.charAt(input.selectionStart - 1);
      if (antes === " " || antes === "/") { try { input.setSelectionRange(input.selectionStart - 1, input.selectionStart - 1); } catch (x) { /* nada */ } }
    });
  }

  // ---- Vista previa de la tarjeta
  var tarjeta = $("[data-tarjeta]", pago);
  var prevNumero = $("[data-prev-numero]", pago);
  var prevNombre = $("[data-prev-nombre]", pago);
  var prevVenc = $("[data-prev-venc]", pago);
  var prevCvc = $("[data-prev-cvc]", pago);
  var prevMarca = $("[data-prev-marca]", pago);
  var marcaInput = $("[data-marca-input]", pago);
  var listaMarcas = $("[data-marcas]", pago);

  var numero = document.getElementById("tarjeta-numero");
  var nombre = document.getElementById("tarjeta-nombre");
  var venc = document.getElementById("tarjeta-venc");
  var cvc = document.getElementById("tarjeta-cvc");

  var marcaActual = "";
  var largoAnterior = 0;

  function pintarMarca(marca) {

    if (marca === marcaActual) { return; }
    marcaActual = marca;

    tarjeta.setAttribute("data-marca", marca === "generica" ? "" : marca);

    // Vista previa: sale el logo viejo y entra el nuevo
    var viejo = $("svg", prevMarca);
    var nuevo = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    nuevo.setAttribute("viewBox", "0 0 64 40");
    var uso = document.createElementNS("http://www.w3.org/2000/svg", "use");
    uso.setAttribute("href", "#marca-" + marca);
    nuevo.appendChild(uso);
    nuevo.setAttribute("class", "marca-entra");
    prevMarca.appendChild(nuevo);
    if (viejo) {
      viejo.setAttribute("class", "marca-sale");
      window.setTimeout(function () { if (viejo.parentNode) { viejo.parentNode.removeChild(viejo); } }, 340);
    }

    if (marcaInput) { marcaInput.setAttribute("href", "#marca-" + marca); }

    // Marcas aceptadas: se enciende la detectada
    $$("[data-marca-lista]", listaMarcas).forEach(function (li) { li.classList.toggle("is-activa", li.getAttribute("data-marca-lista") === marca); });
    listaMarcas.classList.toggle("hay-marca", marca !== "generica");

    // El código de seguridad cambia de largo (4 en American Express)
    cvc.setAttribute("maxlength", String(MARCAS[marca].cvc));
    cvc.setAttribute("placeholder", marca === "amex" ? "1234" : "123");
    if (soloDigitos(cvc.value).length > MARCAS[marca].cvc) { cvc.value = soloDigitos(cvc.value).slice(0, MARCAS[marca].cvc); }
    pintarCvc();
  }

  function pintarNumero() {

    var d = soloDigitos(numero.value);
    var marca = detectarMarca(d);
    var m = MARCAS[marca];
    var maximo = m.largos[m.largos.length - 1];
    d = d.slice(0, marca === "generica" ? 19 : maximo);

    pintarMarca(marca);

    var texto = agrupar(d, marca);
    numero.value = texto;

    // Vista previa: los dígitos que faltan se ven como puntos, según el formato de la marca
    var largoTotal = m.largos.indexOf(16) !== -1 || marca === "generica" ? 16 : m.largos[0];
    var molde = agrupar(new Array(largoTotal + 1).join("•"), marca);
    var chars = molde.split("");
    var escritos = texto.replace(/ /g, "").length;
    var pos = 0;
    var salida = [];
    for (var i = 0; i < chars.length; i++) {
      if (chars[i] === " ") { salida.push(" "); continue; }
      salida.push(pos < escritos ? texto.replace(/ /g, "").charAt(pos) : "•");
      pos++;
    }
    // Si hay más dígitos que el molde (tarjetas largas), se muestran todos
    if (escritos > pos) { salida = texto.split(""); }

    prevNumero.textContent = "";
    salida.forEach(function (ch, idx) {
      var span = document.createElement("span");
      span.textContent = ch;
      var esNuevo = ch !== "•" && ch !== " " && idx >= largoAnterior - 1 && texto.replace(/ /g, "").length > largoAnterior;
      if (esNuevo && !reducir) { span.className = "nuevo"; }
      prevNumero.appendChild(span);
    });
    largoAnterior = texto.replace(/ /g, "").length;
  }

  function pintarNombre() {
    prevNombre.textContent = nombre.value.trim() ? nombre.value.trim() : "Nombre y apellido";
  }

  function pintarVenc() { prevVenc.textContent = venc.value ? venc.value : "MM/AA"; }

  function pintarCvc() {
    var largo = MARCAS[marcaActual || "generica"].cvc;
    var d = soloDigitos(cvc.value);
    prevCvc.textContent = d + new Array(largo - d.length + 1).join("•");
  }

  numero.addEventListener("input", function () {
    formatearEnSitio(numero, function (v) {
      var d = soloDigitos(v);
      var marca = detectarMarca(d);
      var m = MARCAS[marca];
      return agrupar(d.slice(0, marca === "generica" ? 19 : m.largos[m.largos.length - 1]), marca);
    });
    pintarNumero();
    revisar("tarjeta-numero", "numero", false);
    // si cambió la marca, el código de seguridad se revisa de nuevo
    if (cvc.value) { revisar("tarjeta-cvc", "cvc", false); }
  });
  saltarSeparador(numero);

  nombre.addEventListener("input", function () {
    nombre.value = nombre.value.replace(/[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .-]/g, "");
    pintarNombre();
  });

  venc.addEventListener("input", function () {
    formatearEnSitio(venc, function (v) {
      var d = soloDigitos(v).slice(0, 4);
      if (d.length === 1 && parseInt(d, 10) > 1) { d = "0" + d; }
      return d.length >= 3 ? d.slice(0, 2) + "/" + d.slice(2) : d;
    });
    pintarVenc();
  });
  saltarSeparador(venc);

  cvc.addEventListener("input", function () {
    cvc.value = soloDigitos(cvc.value).slice(0, MARCAS[marcaActual || "generica"].cvc);
    pintarCvc();
  });

  // El dorso se muestra mientras se escribe el código de seguridad
  cvc.addEventListener("focus", function () { tarjeta.classList.add("is-vuelta"); });
  cvc.addEventListener("blur", function () { tarjeta.classList.remove("is-vuelta"); });

  // Inclinación y brillo que siguen al puntero
  if (!reducir && window.matchMedia("(hover: hover)").matches) {
    var interior = $(".tarjeta3d__interior", tarjeta);
    tarjeta.addEventListener("pointermove", function (e) {
      var r = interior.getBoundingClientRect();
      var x = (e.clientX - r.left) / r.width;
      var y = (e.clientY - r.top) / r.height;
      tarjeta.classList.add("is-mueve");
      tarjeta.style.setProperty("--ry", ((x - 0.5) * 16).toFixed(2) + "deg");
      tarjeta.style.setProperty("--rx", ((0.5 - y) * 12).toFixed(2) + "deg");
      tarjeta.style.setProperty("--mx", (x * 100).toFixed(1) + "%");
      tarjeta.style.setProperty("--my", (y * 100).toFixed(1) + "%");
    });
    tarjeta.addEventListener("pointerleave", function () {
      tarjeta.classList.remove("is-mueve");
      tarjeta.style.setProperty("--ry", "0deg");
      tarjeta.style.setProperty("--rx", "0deg");
    });
  }

  // Formato de los otros campos
  var cuenta = document.getElementById("trans-cuenta");
  cuenta.addEventListener("input", function () { cuenta.value = soloDigitos(cuenta.value).slice(0, 15); });

  var ci = document.getElementById("trans-ci");
  ci.addEventListener("input", function () {
    formatearEnSitio(ci, function (v) {
      var d = soloDigitos(v).slice(0, 8);
      if (d.length <= 1) { return d; }
      var cuerpo = d.slice(0, -1).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
      return cuerpo + "-" + d.slice(-1);
    });
  });

  var titular = document.getElementById("trans-titular");
  titular.addEventListener("input", function () { titular.value = titular.value.replace(/[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .-]/g, ""); });

  pintarNumero();
  pintarNombre();
  pintarVenc();
  pintarCvc();

  // ---- Métodos de pago
  var metodo = "tarjeta";
  var botonesMetodo = $$("[data-metodo]", pago);
  var confirmar = $("[data-confirmar]", pago);

  function elegirMetodo(nuevo, enfocar) {

    if (nuevo === metodo && !enfocar) { return; }
    metodo = nuevo;

    botonesMetodo.forEach(function (b) {
      var activo = b.getAttribute("data-metodo") === metodo;
      b.setAttribute("aria-selected", activo ? "true" : "false");
      b.setAttribute("tabindex", activo ? "0" : "-1");
    });

    $$("[data-panel]", pago).forEach(function (panel) {
      var activo = panel.getAttribute("data-panel") === metodo;
      panel.hidden = !activo;
      panel.classList.toggle("is-activo", activo);
    });

    confirmar.hidden = metodo === "applepay";
    var oculto = $("#pago-enviar input[name='metodo']");
    if (oculto) { oculto.value = metodo; }
  }

  botonesMetodo.forEach(function (b, i) {
    b.addEventListener("click", function () { elegirMetodo(b.getAttribute("data-metodo")); });
    b.addEventListener("keydown", function (e) {
      var delta = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!delta) { return; }
      e.preventDefault();
      var siguiente = botonesMetodo[(i + delta + botonesMetodo.length) % botonesMetodo.length];
      siguiente.focus();
      elegirMetodo(siguiente.getAttribute("data-metodo"));
    });
  });

  elegirMetodo("tarjeta", true);

  // ---- Confirmar
  var enCurso = false;

  function revisarMetodo() {
    var primero = null;
    CAMPOS[metodo].forEach(function (par) {
      tocados[par[0]] = true;
      var mensaje = revisar(par[0], par[1], true);
      if (mensaje && !primero) { primero = document.getElementById(par[0]); }
    });
    return primero;
  }

  function enviar() {
    var formulario = document.getElementById("pago-enviar");
    $("input[name='metodo']", formulario).value = metodo;
    $("input[name='ciclo']", formulario).value = ciclo;
    formulario.submit();
  }

  function pagar(boton) {

    if (enCurso) { return; }
    enCurso = true;
    boton.classList.add("is-cargando");
    boton.setAttribute("aria-busy", "true");

    window.setTimeout(function () {
      boton.classList.remove("is-cargando");
      boton.classList.add("is-listo");
      window.setTimeout(function () {
        var exito = $("[data-exito]");
        if (exito) { exito.classList.add("is-visible"); }
        window.setTimeout(enviar, reducir ? 400 : 1700);
      }, reducir ? 100 : 650);
    }, reducir ? 200 : 1500);
  }

  confirmar.addEventListener("click", function () {
    if (enCurso) { return; }
    var primero = revisarMetodo();
    if (primero) {
      sacudir(primero);
      primero.focus();
      return;
    }
    pagar(confirmar);
  });

  var botonApple = $("[data-applepay]", pago);
  if (botonApple) { botonApple.addEventListener("click", function () { pagar(botonApple); }); }

  // Enter en cualquier campo confirma
  $$(".pago-campo input", pago).forEach(function (input) {
    input.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); confirmar.click(); } });
  });

}());
