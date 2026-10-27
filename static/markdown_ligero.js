/* ==========================================================================
   Markdown liviano para las respuestas del asistente.

   window.renderMarkdownLigero(destino, texto, enCurso)

   Soporta lo que el asistente suele escribir: **negrita**, *cursiva*, `código`, [enlaces](https://…), títulos (# …),
   listas con "- ", "* " o "•" y numeradas ("1. "), y párrafos. Todo se arma con nodos del DOM y textContent:
   nada de lo que escribe el modelo se interpreta como HTML.

   enCurso = true mientras la respuesta todavía se está escribiendo: una negrita o cursiva sin cerrar se muestra ya
   formateada hasta el final del texto (así no aparecen los asteriscos sueltos en medio de la escritura).
   ========================================================================== */

(function () {

  "use strict";

  var URL_SEGURA = /^https?:\/\//i;

  // Texto con formato en línea → nodos dentro de `padre`.
  function inline(padre, texto, enCurso) {

    var patron = /(\*\*|__)(.+?)(?:\1|$)|(`)([^`]+)(?:`|$)|\*([^*\s][^*]*?)(?:\*|$)|\[([^\]]+)\]\(([^)\s]+)\)/g;
    var desde = 0;
    var coincidencia;

    while ((coincidencia = patron.exec(texto)) !== null) {

      var cierra = /(\*\*|__|`|\*)$/.test(coincidencia[0]) || coincidencia[0].charAt(0) === "[";
      var llegoAlFinal = coincidencia.index + coincidencia[0].length >= texto.length;

      // Un marcador que nunca se cierra solo vale mientras se está escribiendo la respuesta.
      if (!cierra && !(enCurso && llegoAlFinal)) { continue; }

      if (coincidencia.index > desde) { padre.appendChild(document.createTextNode(texto.slice(desde, coincidencia.index))); }

      var nodo;

      if (coincidencia[1]) {
        nodo = document.createElement("strong");
        inline(nodo, coincidencia[2], enCurso);
      } else if (coincidencia[3]) {
        nodo = document.createElement("code");
        nodo.textContent = coincidencia[4];
      } else if (coincidencia[5] !== undefined) {
        nodo = document.createElement("em");
        inline(nodo, coincidencia[5], enCurso);
      } else if (URL_SEGURA.test(coincidencia[7])) {
        nodo = document.createElement("a");
        nodo.href = coincidencia[7];
        nodo.target = "_blank";
        nodo.rel = "noopener noreferrer";
        nodo.textContent = coincidencia[6];
      } else {
        nodo = document.createTextNode(coincidencia[0]);
      }

      padre.appendChild(nodo);
      desde = coincidencia.index + coincidencia[0].length;
    }

    if (desde < texto.length) { padre.appendChild(document.createTextNode(texto.slice(desde))); }
  }


  function renderMarkdownLigero(destino, texto, enCurso) {

    destino.textContent = "";
    destino.classList.add("md");

    var lineas = String(texto || "").replace(/\r\n?/g, "\n").split("\n");
    var parrafo = null;   // <p> abierto
    var lista = null;     // <ul>/<ol> abierta
    var tipoLista = "";

    function cerrar() { parrafo = null; lista = null; tipoLista = ""; }

    for (var i = 0; i < lineas.length; i++) {

      var linea = lineas[i];
      var enUltima = i === lineas.length - 1;
      var coincide;

      if (/^\s*$/.test(linea)) { cerrar(); continue; }

      // Títulos: "# …", "## …", "### …" → una línea en negrita.
      if ((coincide = linea.match(/^\s{0,3}#{1,4}\s+(.*)$/))) {
        cerrar();
        var titulo = document.createElement("p");
        titulo.className = "md-titulo";
        inline(titulo, coincide[1], enCurso && enUltima);
        destino.appendChild(titulo);
        continue;
      }

      // Listas con vineta o numeradas.
      var vineta = linea.match(/^\s*(?:[-*•])\s+(.*)$/);
      var numero = vineta ? null : linea.match(/^\s*\d{1,2}[.)]\s+(.*)$/);

      if (vineta || numero) {
        var tipo = vineta ? "ul" : "ol";
        if (!lista || tipoLista !== tipo) {
          parrafo = null;
          lista = document.createElement(tipo);
          tipoLista = tipo;
          destino.appendChild(lista);
        }
        var item = document.createElement("li");
        inline(item, (vineta || numero)[1], enCurso && enUltima);
        lista.appendChild(item);
        continue;
      }

      // Texto común: líneas seguidas son un mismo párrafo con salto de línea.
      lista = null;
      tipoLista = "";
      if (!parrafo) {
        parrafo = document.createElement("p");
        destino.appendChild(parrafo);
      } else {
        parrafo.appendChild(document.createElement("br"));
      }
      inline(parrafo, linea, enCurso && enUltima);
    }
  }

  window.renderMarkdownLigero = renderMarkdownLigero;

}());
